#!/usr/bin/env python3
"""appsweep — find and remove Android apps you haven't opened in a year.

Talks to one or more phones over adb. Nothing is uninstalled unless you pass
--apply, and even then you are asked to confirm (unless you also pass --yes).

Usage:
    python3 appsweep.py devices
    python3 appsweep.py scan                    # inventory of every user app
    python3 appsweep.py scan --csv apps.csv     # same, saved to a spreadsheet
    python3 appsweep.py clean                   # dry run: what WOULD be removed
    python3 appsweep.py clean --apply --backup ./apk-backup
    python3 appsweep.py clean --all-devices --days 365 --apply --yes
"""

from __future__ import annotations

import argparse
import csv
import fnmatch
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

DEFAULT_DAYS = 365
DEFAULT_PROTECTED = Path(__file__).with_name("protected.txt")
DEFAULT_LOG = Path("appsweep-log.jsonl")

TIMESTAMP = r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
# Usage fields that mean "the user had this app on screen". lastTimeForegroundServiceUsed
# is deliberately excluded: background sync/music services don't count as use.
USAGE_FIELDS = ("lastTimeUsed", "lastTimeVisible", "lastTime")
USAGE_RE = re.compile(r'\b(%s)="?%s' % ("|".join(USAGE_FIELDS), TIMESTAMP))
PACKAGE_LINE_RE = re.compile(r"\bpackage=([\w.]+)")
# Android reports "never" as the epoch, sometimes shifted by the timezone.
NEVER_BEFORE = datetime(1971, 1, 1)


class AdbError(RuntimeError):
    pass


@dataclass
class App:
    package: str
    last_used: datetime | None
    installed: datetime | None
    protected: bool = False
    # Oldest moment the phone's usage history reaches back to. An app with no usage
    # record only counts as "never opened" if that history covers the whole window.
    history_start: datetime | None = None

    def idle_days(self, now: datetime) -> int | None:
        """Days since the app was last opened, or since install if never opened."""
        ref = self.last_used or self.installed
        return None if ref is None else (now - ref).days

    def status(self, now: datetime, days: int) -> str:
        if self.protected:
            return "protected"
        idle = self.idle_days(now)
        if idle is None:
            return "unknown"
        if idle < days:
            return "active"
        if self.last_used is None and (self.history_start is None or (now - self.history_start).days < days):
            return "unknown"  # never seen in usage history, but that history is too short to be sure
        return "stale"


# --------------------------------------------------------------------------- adb


class Device:
    def __init__(self, serial: str, adb: str = "adb"):
        self.serial = serial
        self.adb = adb

    def run(self, *args: str, check: bool = True) -> str:
        cmd = [self.adb, "-s", self.serial, *args]
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if check and proc.returncode != 0:
            raise AdbError(f"{' '.join(cmd)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
        return proc.stdout

    def shell(self, command: str, check: bool = True) -> str:
        return self.run("shell", command, check=check)

    def model(self) -> str:
        return self.shell("getprop ro.product.model", check=False).strip() or "unknown"

    def now(self) -> datetime:
        # Usage timestamps are in the phone's local time, so measure against its clock.
        return datetime.strptime(self.shell("date '+%Y-%m-%d %H:%M:%S'").strip(), "%Y-%m-%d %H:%M:%S")

    def user_packages(self) -> list[str]:
        out = self.shell("pm list packages -3")
        return sorted(line.split(":", 1)[1].strip() for line in out.splitlines() if line.startswith("package:"))

    def usage_dump(self) -> str:
        return self.shell("dumpsys usagestats")

    def package_dump(self) -> str:
        return self.shell("dumpsys package packages")

    def apk_paths(self, package: str) -> list[str]:
        out = self.shell(f"pm path {package}")
        return [line.split(":", 1)[1].strip() for line in out.splitlines() if line.startswith("package:")]

    def pull(self, remote: str, local: Path) -> None:
        self.run("pull", remote, str(local))

    def uninstall(self, package: str, keep_data: bool) -> str:
        flag = "-k " if keep_data else ""
        return self.shell(f"pm uninstall {flag}{package}", check=False).strip()


def connected_serials(adb: str = "adb") -> list[str]:
    if not shutil.which(adb):
        raise AdbError(f"'{adb}' not found. Install Android platform-tools and put adb on your PATH.")
    out = subprocess.run([adb, "devices"], capture_output=True, text=True).stdout
    serials = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            serials.append(parts[0])
        elif len(parts) >= 2:
            print(f"warning: {parts[0]} is '{parts[1]}' (unlock the phone and accept the USB debugging prompt)",
                  file=sys.stderr)
    return serials


# ----------------------------------------------------------------------- parsing


def _parse_ts(value: str) -> datetime | None:
    ts = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return ts if ts >= NEVER_BEFORE else None


def parse_last_used(dump: str) -> dict[str, datetime]:
    """Latest foreground-use time per package across every interval in `dumpsys usagestats`.

    The dump repeats each package under daily/weekly/monthly/yearly sections (the yearly
    bucket is kept for about two years), so taking the max covers a full year of history.
    """
    last: dict[str, datetime] = {}
    for line in dump.splitlines():
        pkg = PACKAGE_LINE_RE.search(line)
        if not pkg:
            continue
        for _field, value in USAGE_RE.findall(line):
            ts = _parse_ts(value)
            if ts and (pkg.group(1) not in last or ts > last[pkg.group(1)]):
                last[pkg.group(1)] = ts
    return last


def parse_history_start(dump: str) -> datetime | None:
    """Oldest real timestamp anywhere in the usage dump: how far back the history reaches."""
    stamps = [ts for ts in map(_parse_ts, re.findall(TIMESTAMP, dump)) if ts]
    return min(stamps) if stamps else None


def parse_install_times(dump: str) -> dict[str, datetime]:
    """firstInstallTime per package from `dumpsys package packages`."""
    installed: dict[str, datetime] = {}
    current = None
    for line in dump.splitlines():
        header = re.match(r"\s*Package \[([\w.]+)\]", line)
        if header:
            current = header.group(1)
            continue
        m = re.search(r"firstInstallTime=" + TIMESTAMP, line)
        if current and m and current not in installed:
            ts = _parse_ts(m.group(1))
            if ts:
                installed[current] = ts
    return installed


def load_patterns(path: Path | None) -> list[str]:
    if not path or not path.exists():
        return []
    patterns = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            patterns.append(line)
    return patterns


def is_protected(package: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(package, p) for p in patterns)


def inventory(device: Device, patterns: list[str]) -> list[App]:
    usage = device.usage_dump()
    last_used, history_start = parse_last_used(usage), parse_history_start(usage)
    installed = parse_install_times(device.package_dump())
    return [
        App(pkg, last_used.get(pkg), installed.get(pkg), is_protected(pkg, patterns), history_start)
        for pkg in device.user_packages()
    ]


# -------------------------------------------------------------------------- CLI


def fmt(ts: datetime | None) -> str:
    return ts.strftime("%Y-%m-%d") if ts else "-"


def print_table(apps: list[App], now: datetime, days: int) -> None:
    rows = sorted(apps, key=lambda a: -(a.idle_days(now) or -1))
    width = max([len(a.package) for a in rows] + [7])
    print(f"  {'PACKAGE':<{width}}  {'LAST USED':<10}  {'INSTALLED':<10}  {'IDLE':>5}  STATUS")
    for a in rows:
        idle = a.idle_days(now)
        print(f"  {a.package:<{width}}  {fmt(a.last_used):<10}  {fmt(a.installed):<10}  "
              f"{'-' if idle is None else idle:>5}  {a.status(now, days)}")


def write_csv(path: Path, serial: str, apps: list[App], now: datetime, days: int, append: bool) -> None:
    new_file = not append or not path.exists()
    with path.open("a" if append else "w", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["device", "package", "last_used", "installed", "idle_days", "status"])
        for a in apps:
            w.writerow([serial, a.package, fmt(a.last_used), fmt(a.installed),
                        a.idle_days(now), a.status(now, days)])


def backup_apks(device: Device, package: str, root: Path) -> Path:
    dest = root / device.serial / package
    dest.mkdir(parents=True, exist_ok=True)
    for remote in device.apk_paths(package):
        device.pull(remote, dest / Path(remote).name)
    return dest


def log_event(path: Path, **fields) -> None:
    with path.open("a") as f:
        f.write(json.dumps(fields, default=str) + "\n")


def select_devices(args) -> list[Device]:
    serials = connected_serials(args.adb)
    if not serials:
        raise AdbError("No phone connected. Plug it in with USB debugging enabled (see README).")
    if args.device:
        if args.device not in serials:
            raise AdbError(f"Device {args.device} not connected. Connected: {', '.join(serials)}")
        serials = [args.device]
    elif len(serials) > 1 and not args.all_devices:
        raise AdbError(f"Several phones connected ({', '.join(serials)}). Pass --device SERIAL or --all-devices.")
    return [Device(s, args.adb) for s in serials]


def cmd_devices(args) -> int:
    for serial in connected_serials(args.adb):
        print(f"{serial}\t{Device(serial, args.adb).model()}")
    return 0


def cmd_scan(args) -> int:
    patterns = load_patterns(args.protect)
    for i, dev in enumerate(select_devices(args)):
        now, apps = dev.now(), inventory(dev, patterns)
        stale = [a for a in apps if a.status(now, args.days) == "stale"]
        print(f"\n{dev.serial} ({dev.model()}): {len(apps)} user apps, "
              f"{len(stale)} unused for {args.days}+ days")
        print_table(apps, now, args.days)
        if args.csv:
            write_csv(args.csv, dev.serial, apps, now, args.days, append=i > 0)
    if args.csv:
        print(f"\nSaved {args.csv}")
    return 0


def cmd_clean(args) -> int:
    patterns = load_patterns(args.protect)
    failures = 0
    for dev in select_devices(args):
        now = dev.now()
        apps = inventory(dev, patterns)
        targets = [a for a in apps if a.status(now, args.days) == "stale"]
        if args.include_unknown:
            targets += [a for a in apps if a.status(now, args.days) == "unknown"]
        skipped_unknown = sum(a.status(now, args.days) == "unknown" for a in apps) if not args.include_unknown else 0

        print(f"\n{dev.serial} ({dev.model()}): {len(targets)} app(s) unused for {args.days}+ days")
        if skipped_unknown:
            print(f"  ({skipped_unknown} app(s) skipped: no usage record and the phone's usage history "
                  f"doesn't go back {args.days} days, so 'never opened' can't be confirmed; "
                  f"see --include-unknown)")
        if not targets:
            continue
        print_table(targets, now, args.days)

        if not args.apply:
            print("\nDry run — nothing removed. Re-run with --apply to uninstall these.")
            continue
        if not args.yes:
            answer = input(f"\nUninstall {len(targets)} app(s) from {dev.serial}? Type 'yes' to continue: ")
            if answer.strip().lower() != "yes":
                print("Skipped.")
                continue

        for app in targets:
            if args.backup:
                try:
                    where = backup_apks(dev, app.package, args.backup)
                    print(f"  backed up {app.package} -> {where}")
                except AdbError as e:
                    print(f"  ! backup failed for {app.package}, NOT removing it: {e}")
                    failures += 1
                    continue
            result = dev.uninstall(app.package, args.keep_data)
            ok = result.startswith("Success")
            failures += not ok
            print(f"  {'removed' if ok else 'FAILED '} {app.package}{'' if ok else '  (' + result + ')'}")
            log_event(args.log, time=datetime.now().isoformat(timespec="seconds"), device=dev.serial,
                      package=app.package, last_used=app.last_used, installed=app.installed,
                      idle_days=app.idle_days(now), result=result, keep_data=args.keep_data,
                      backup=str(args.backup) if args.backup else None)
    return 1 if failures else 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="appsweep", description=__doc__.split("\n\n")[0])
    p.add_argument("--adb", default="adb", help="path to the adb binary")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("devices", help="list connected phones")

    def common(sp):
        sp.add_argument("--device", "-s", help="serial of the phone to use (see `devices`)")
        sp.add_argument("--all-devices", action="store_true", help="run against every connected phone")
        sp.add_argument("--days", type=int, default=DEFAULT_DAYS,
                        help=f"idle threshold in days (default {DEFAULT_DAYS})")
        sp.add_argument("--protect", type=Path, default=DEFAULT_PROTECTED,
                        help="file of package patterns never to remove (default protected.txt)")

    scan = sub.add_parser("scan", help="list every user-installed app with its last-used date")
    common(scan)
    scan.add_argument("--csv", type=Path, help="also write the inventory to this CSV file")

    clean = sub.add_parser("clean", help="uninstall apps unused for --days (dry run unless --apply)")
    common(clean)
    clean.add_argument("--apply", action="store_true", help="actually uninstall (default is a dry run)")
    clean.add_argument("--yes", "-y", action="store_true", help="don't ask for confirmation")
    clean.add_argument("--backup", type=Path, help="pull each APK into this folder before removing it")
    clean.add_argument("--keep-data", action="store_true", help="keep app data and cache (pm uninstall -k)")
    clean.add_argument("--include-unknown", action="store_true",
                       help="also remove apps whose idle time can't be confirmed (no usage record and "
                            "too little usage history on the phone)")
    clean.add_argument("--log", type=Path, default=DEFAULT_LOG, help="where to append the removal log")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handler = {"devices": cmd_devices, "scan": cmd_scan, "clean": cmd_clean}[args.command]
    try:
        return handler(args)
    except AdbError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
