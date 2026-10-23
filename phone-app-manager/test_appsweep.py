"""Tests for appsweep, using captured dumpsys output and a fake adb device.

Run:  python3 -m unittest -v test_appsweep
"""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest import mock

import appsweep

USAGE_DUMP = """\
user=0
  In-memory daily stats
  timeRange="Oct 23, 2026, 00:00 – 23:59"
  packages
    package=com.example.chat totalTimeUsed="1:02:03" lastTimeUsed="2026-10-22 18:00:00" lastTimeVisible="2026-10-22 18:00:01"
  In-memory yearly stats
  timeRange="Jan 1, 2025 – Dec 31, 2026"
  packages
    package=com.example.chat totalTimeUsed="99:00:00" lastTimeUsed="2026-01-02 09:00:00"
    package=com.example.oldgame totalTimeUsed="2:00:00" lastTimeUsed="2025-03-01 12:00:00" lastTimeForegroundServiceUsed="2026-10-01 08:00:00"
    package=com.example.never totalTimeUsed="00:00" lastTimeUsed="1970-01-01 00:00:00"
    package=com.google.android.apps.authenticator2 totalTimeUsed="00:10" lastTimeUsed="2024-11-01 10:00:00"
    package=com.example.legacy lastTime="2025-06-01 10:00:00"
"""

PACKAGE_DUMP = """\
Packages:
  Package [com.example.chat] (a1b2c3):
    firstInstallTime=2023-01-01 10:00:00
    lastUpdateTime=2026-09-01 10:00:00
  Package [com.example.oldgame] (d4e5f6):
    firstInstallTime=2024-02-02 10:00:00
  Package [com.example.newapp] (777777):
    firstInstallTime=2026-09-15 10:00:00
  Package [com.example.untouched] (888888):
    firstInstallTime=2023-05-05 10:00:00
  Package [com.google.android.apps.authenticator2] (999999):
    firstInstallTime=2022-01-01 10:00:00
"""

PACKAGES = ["com.example.chat", "com.example.oldgame", "com.example.newapp",
            "com.example.untouched", "com.example.never", "com.example.legacy",
            "com.google.android.apps.authenticator2"]
NOW = datetime(2026, 10, 23, 12, 0, 0)


class FakeDevice(appsweep.Device):
    def __init__(self, usage=USAGE_DUMP):
        super().__init__("FAKE123")
        self.usage = usage
        self.removed = []

    def model(self): return "Pixel Test"
    def now(self): return NOW
    def user_packages(self): return sorted(PACKAGES)
    def usage_dump(self): return self.usage
    def package_dump(self): return PACKAGE_DUMP
    def apk_paths(self, package): return [f"/data/app/{package}/base.apk"]
    def pull(self, remote, local): Path(local).write_text("apk")

    def uninstall(self, package, keep_data):
        self.removed.append(package)
        return "Success"


class ParsingTests(unittest.TestCase):
    def test_last_used_takes_latest_across_intervals(self):
        last = appsweep.parse_last_used(USAGE_DUMP)
        self.assertEqual(last["com.example.chat"], datetime(2026, 10, 22, 18, 0, 1))

    def test_background_service_use_is_not_counted(self):
        last = appsweep.parse_last_used(USAGE_DUMP)
        self.assertEqual(last["com.example.oldgame"], datetime(2025, 3, 1, 12, 0, 0))

    def test_epoch_means_never(self):
        self.assertNotIn("com.example.never", appsweep.parse_last_used(USAGE_DUMP))

    def test_legacy_last_time_field(self):
        self.assertEqual(appsweep.parse_last_used(USAGE_DUMP)["com.example.legacy"], datetime(2025, 6, 1, 10))

    def test_install_times(self):
        installed = appsweep.parse_install_times(PACKAGE_DUMP)
        self.assertEqual(installed["com.example.newapp"], datetime(2026, 9, 15, 10))
        self.assertEqual(len(installed), 5)

    def test_history_start(self):
        self.assertEqual(appsweep.parse_history_start(USAGE_DUMP), datetime(2024, 11, 1, 10))

    def test_protected_patterns(self):
        self.assertTrue(appsweep.is_protected("com.mybank.app", ["com.mybank.*"]))
        self.assertFalse(appsweep.is_protected("com.mybankother", ["com.mybank.*"]))

    def test_load_patterns_ignores_comments(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("# header\ncom.a.b  # trailing\n\ncom.c.*\n")
        self.assertEqual(appsweep.load_patterns(Path(f.name)), ["com.a.b", "com.c.*"])


class ClassificationTests(unittest.TestCase):
    def statuses(self, usage=USAGE_DUMP):
        apps = appsweep.inventory(FakeDevice(usage), ["com.google.android.apps.authenticator2"])
        return {a.package: a.status(NOW, 365) for a in apps}

    def test_statuses(self):
        self.assertEqual(self.statuses(), {
            "com.example.chat": "active",          # used yesterday
            "com.example.oldgame": "stale",        # last opened 2025-03
            "com.example.newapp": "active",        # installed last month, not opened yet
            "com.example.untouched": "stale",      # installed 2023, never opened, history covers a year
            "com.example.never": "unknown",        # no usage record, no install date
            "com.example.legacy": "stale",         # old-format record from 2025-06
            "com.google.android.apps.authenticator2": "protected",
        })

    def test_short_history_does_not_trust_never_opened(self):
        # Usage history only reaches back two months (e.g. phone was reset).
        short = 'package=com.example.chat lastTimeUsed="2026-08-20 09:00:00"\n'
        self.assertEqual(self.statuses(short)["com.example.untouched"], "unknown")


class CleanCommandTests(unittest.TestCase):
    def run_clean(self, *extra):
        dev = FakeDevice()
        tmp = Path(tempfile.mkdtemp())
        args = appsweep.build_parser().parse_args(
            ["clean", "--log", str(tmp / "log.jsonl"), *extra])
        out = io.StringIO()
        with mock.patch.object(appsweep, "select_devices", return_value=[dev]), redirect_stdout(out):
            code = appsweep.cmd_clean(args)
        return dev, code, out.getvalue(), tmp

    def test_dry_run_removes_nothing(self):
        dev, code, out, _ = self.run_clean()
        self.assertEqual(dev.removed, [])
        self.assertIn("Dry run", out)
        self.assertEqual(code, 0)

    def test_apply_removes_only_stale(self):
        dev, code, _, tmp = self.run_clean("--apply", "--yes")
        self.assertEqual(sorted(dev.removed), [
            "com.example.legacy", "com.example.oldgame", "com.example.untouched"])
        self.assertEqual(len((tmp / "log.jsonl").read_text().splitlines()), 3)

    def test_confirmation_declined(self):
        with mock.patch("builtins.input", return_value="no"):
            dev, _, out, _ = self.run_clean("--apply")
        self.assertEqual(dev.removed, [])
        self.assertIn("Skipped", out)

    def test_backup_before_remove(self):
        tmp = Path(tempfile.mkdtemp())
        dev, _, _, _ = self.run_clean("--apply", "--yes", "--backup", str(tmp))
        self.assertTrue((tmp / "FAKE123" / "com.example.oldgame" / "base.apk").exists())

    def test_custom_threshold(self):
        dev, _, _, _ = self.run_clean("--apply", "--yes", "--days", "600")
        self.assertEqual(sorted(dev.removed), ["com.example.oldgame", "com.example.untouched"])


if __name__ == "__main__":
    unittest.main()
