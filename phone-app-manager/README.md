# appsweep: remove phone apps you haven't used in a year

`appsweep` connects to your Android phone(s) from a computer, reads when each app was last
opened, and bulk-uninstalls the ones you haven't opened in a year (or however long you choose).

- **Safe by default.** `clean` is a dry run until you add `--apply`, and asks before removing anything.
- **Protected list.** Apps listed in [`protected.txt`](protected.txt) are never touched. It ships
  with authenticators and password managers in it; add your bank apps and similar.
- **Optional APK backup** before each removal, so you can reinstall the exact version.
- **Several phones at once** with `--all-devices`.
- **Audit log.** Every removal goes into `appsweep-log.jsonl`.
- One Python file, standard library only. Needs Python 3.9+ and `adb`.

> **iPhone?** iOS doesn't let a computer read per-app usage or uninstall apps in bulk. See
> [iPhone](#iphone) below for the built-in alternative.

## Setup (once)

1. **Install adb** (Android platform-tools):
   - macOS: `brew install android-platform-tools`
   - Windows: `winget install Google.PlatformTools`
   - Linux: `sudo apt install adb` (or your distro's equivalent)
2. **Enable USB debugging on the phone:** Settings → About phone → tap *Build number* 7 times →
   back to Settings → System → Developer options → turn on *USB debugging*.
3. Plug the phone in, unlock it, and tap **Allow** on the "Allow USB debugging?" prompt.
4. Check it's visible:
   ```bash
   python3 appsweep.py devices
   ```

## Usage

```bash
# 1. See every app you installed, when you last opened it, and which ones are stale
python3 appsweep.py scan
python3 appsweep.py scan --csv my-apps.csv      # same thing as a spreadsheet

# 2. Preview what would be removed (nothing is uninstalled)
python3 appsweep.py clean

# 3. Remove them, backing up each APK first
python3 appsweep.py clean --apply --backup ./apk-backup
```

Example output:

```
R58M12ABCDE (SM-S918U): 3 app(s) unused for 365+ days
  PACKAGE                     LAST USED   INSTALLED   IDLE  STATUS
  com.example.untouched       -           2023-05-05  1267  stale
  com.example.oldgame         2025-03-01  2024-02-02   601  stale
  com.example.legacy          2025-06-01  -            509  stale

Dry run — nothing removed. Re-run with --apply to uninstall these.
```

### Options

| Option | What it does |
|---|---|
| `--days N` | Idle threshold. Default `365`. |
| `--apply` | Actually uninstall. Without it, `clean` only shows the list. |
| `--yes` | Skip the "type yes to continue" prompt (for scheduled runs). |
| `--backup DIR` | Copy each app's APK files to `DIR/<serial>/<package>/` before removing it. If the backup fails, that app is kept. |
| `--keep-data` | Keep the app's data and cache (`pm uninstall -k`), so reinstalling restores it. |
| `--protect FILE` | Use a different protected list. Default `protected.txt`. |
| `--device SERIAL` | Pick one phone when several are plugged in. |
| `--all-devices` | Run against every connected phone. |
| `--include-unknown` | Also remove apps whose idle time can't be confirmed (see below). |
| `--log FILE` | Where to write the removal log. Default `appsweep-log.jsonl`. |

## How "last used" is worked out

- Only apps **you installed** are considered (`pm list packages -3`). System and carrier apps are
  never touched.
- **Last used** comes from Android's usage statistics (`dumpsys usagestats`): the latest time the
  app was on screen. Android keeps yearly usage summaries for about two years, so a 365-day
  window is covered. Background activity (music playback, sync) doesn't count as use.
- An app with **no usage record** is judged by its install date: installed over a year ago and
  never opened means stale.
- **Statuses:** `active` (used within the window), `stale` (will be removed), `protected` (in
  your protected list), and `unknown`. An app is `unknown` when it has no usage record and the
  phone's usage history doesn't go back far enough to prove it was never opened, which is common
  after a factory reset or moving to a new phone. `unknown` apps are kept unless you pass
  `--include-unknown`.

## Reinstalling something

The easy way is the Play Store. If you used `--backup`:

```bash
adb install-multiple apk-backup/<serial>/<package>/*.apk
```

## Running it automatically

Keep the phone plugged in (or set up [wireless debugging](https://developer.android.com/tools/adb#connect-to-a-device-over-wi-fi))
and schedule a monthly run.

macOS/Linux `crontab -e`:

```cron
0 10 1 * * cd /path/to/phone-app-manager && python3 appsweep.py clean --all-devices --apply --yes --backup ./apk-backup >> appsweep.out 2>&1
```

Windows: create a monthly Task Scheduler task running the same command.

## iPhone

Apple doesn't expose app usage dates or bulk uninstall to computers, so this tool can't drive an
iPhone. What iOS offers instead:

- **Settings → App Store → Offload Unused Apps.** iOS removes apps you don't use when storage
  runs low. It keeps their data and leaves an icon, so tapping it reinstalls the app. You can't
  set the one-year threshold.
- **Settings → General → iPhone Storage** lists every app with its **Last Used** date. Sort by
  it and remove anything over a year old by hand, or tap *Offload App*.

## Tests

```bash
python3 -m unittest -v test_appsweep
```

The tests use captured `dumpsys` output and a fake device, so no phone is needed.
