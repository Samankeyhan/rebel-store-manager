# Running Rebel Store Manager every day

Plain steps for Windows. Commands are for **PowerShell**, opened in the project folder (`C:\Users\Saman\rebel-store-manager`):
open the folder in File Explorer, click the address bar, type `powershell`, press Enter.

## 1. Start and stop

- **Start:** double-click **`start-rebel.cmd`** in the project folder (or in PowerShell: `.\start-rebel.cmd`).
  A window shows what it does and stays for a few seconds. The browser opens by itself at an address like `http://localhost:8000/`.
  The window also prints the **database file in use**, the **backups folder** and the **logs folder**. Read the first lines once: they must say `data\shop.db`.
- **Stop:** double-click **`stop-rebel.cmd`** (or `.\stop-rebel.cmd`). It first asks the app for a backup (if that fails it tells you and still stops).
  Closing the browser tab does **not** stop the app; it keeps running quietly until you stop it or switch off the computer.
- Start it twice by accident? The second start only opens the browser again.
- The app listens only on your own computer (`127.0.0.1`). Nobody else on the network can reach it.

If something is missing, the start window tells you exactly what and how to fix it (see section 8).

## 2. Where everything is

| What | Where |
|---|---|
| **Your data (the database)** | `data\shop.db` |
| **Backups** (daily, automatic) | `data\backups\daily-YYYY-MM-DD-HHMMSS.db` |
| Older safety copies made before an update changed the database | `data\backups\shop-YYYYMMDD-HHMMSS.db` (never deleted by the app) |
| Safety copy made by `update-rebel.cmd` (newest 10 kept) | `data\backups\pre-update\daily-….db`, and `shop-failed-update-….db` after a rolled-back update |
| Safety copy made before the app changes the database (newest 60 kept) | `data\backups\pre-migration\daily-….db` |
| What an update did, step by step | `data\logs\update-<moment>.log` (and `update-state.json` while an update runs or was interrupted) |
| **Application log** (what happened, errors) | `data\logs\app.log` (+ `app.log.1` … `.5`) |
| What the server printed while starting | `data\logs\server.out.log` |
| Build log of the screens | `data\logs\build.log` |
| Check reports (if you save them) | `data\integrity-YYYY-MM-DD.txt` |

Never edit `data\shop.db` by hand (no database tools, no renaming while the app runs). The log never contains names, amounts or what you typed.

Look at the end of the log:

```powershell
Get-Content data\logs\app.log -Tail 50
```

## 3. Backups

- The app makes **one backup per day automatically**: when it starts, then it checks every hour while it is running (a backup is made only if none exists for today), and once more when you stop it.
- It keeps the **newest 60** daily backups and deletes older ones **only after a new backup was checked and found healthy**. It never deletes the `shop-…` safety copies or anything else in the folder. If a backup fails, nothing old is deleted and the failure is logged and shown.
- **Make a backup right now:** Settings → **پشتیبان‌گیری** → **پشتیبان‌گیری اکنون**. Or in PowerShell (while the app runs; replace 8000 with the port the start window showed):

  ```powershell
  Invoke-RestMethod -Method Post http://localhost:8000/api/backups
  ```

- The same card shows the last backup (time and result), how many are kept, the folder, and the newest ones.
- A backup is a complete copy of the database made in a safe way while the app is running; it is not a copy of the file.

### Copy the backups somewhere else (do this every week)

Backups next to the database protect you from mistakes, **not** from losing the computer or the disk. Copy the folder to another drive or a cloud-synced folder regularly, for example (change `D:\RebelBackups`):

```powershell
robocopy data\backups D:\RebelBackups /E
```

(`robocopy` only adds and updates files here; it does not delete anything at the destination.) The app does not upload anything anywhere.

## 4. Restore a backup (by hand, step by step)

Only if the database is damaged or you must go back to an earlier day. **Everything entered after that backup is lost.**

1. **Stop the app:** `.\stop-rebel.cmd`.
2. **Keep the broken file under a new name** (do not delete it):

   ```powershell
   Rename-Item data\shop.db shop-broken-2026-10-14.db
   ```

   (use today's date)
3. **Choose the backup** you want: `Get-ChildItem data\backups\daily-*.db | Sort-Object Name | Select-Object -Last 5` lists the newest. Copy it in as the new database (replace the file name):

   ```powershell
   Copy-Item data\backups\daily-2026-10-14-083000.db data\shop.db
   ```

4. **Start the app:** `.\start-rebel.cmd`. Check that the first lines say `data\shop.db`.
5. **Check the numbers agree with each other:**

   ```powershell
   .venv\Scripts\python -m tools.integrity_check
   ```

   The last line must be `OK` (lines marked `WARN` or `INFO` are notes, not failures; see `docs/real-use-test.md`).
6. Look at the dashboard and the last orders. When you are sure, the `shop-broken-…db` file can be kept for a while or deleted.

## 5. Prove that a restore works (do this once, on a COPY)

Nothing here touches your real data: the practice database lives in its **own folder** (`data\restore-test\`). Never put a practice copy directly in `data\`, because its backups and logs would be written into your real `data\backups`; the start script refuses that.

```powershell
New-Item -ItemType Directory data\restore-test
Copy-Item (Get-ChildItem data\backups\daily-*.db | Sort-Object Name | Select-Object -Last 1).FullName data\restore-test\shop.db
.venv\Scripts\python -m tools.integrity_check --db data\restore-test\shop.db
```

The last line should be `OK`. To also look at it in the app:

```powershell
$env:REBEL_DB = "$PWD\data\restore-test\shop.db"
.\start-rebel.cmd
```

The window prints `...\restore-test\shop.db` as the database in use. Look around, then stop it and go back to the real one:

```powershell
.\stop-rebel.cmd
Remove-Item Env:REBEL_DB
Remove-Item -Recurse -Force data\restore-test
```

(`Remove-Item Env:REBEL_DB` matters: while that variable is set, the start script uses the practice copy.)

## 6. Update the app (`update-rebel.cmd`)

Double-click **`update-rebel.cmd`** (or `.\update-rebel.cmd`). One command does everything, and goes back by itself if anything fails. The window stays open at the end (press a key).

It asks you once: *"The app will close now. Is anyone entering data right now? Type YES to continue; anything else cancels."* Anything but `YES` cancels and changes nothing. (`--yes` skips the question.)

What it does, in this order, and it stops at the first problem:

1. **Checks the folder:** it is on the branch `main`, no file was changed or added by hand (untracked files count), `.venv` exists, and the internet works. It shows the new commits and the new `migrations\*.sql`. Nothing new: it says "up to date" and ends.
2. **Checks the database** (`tools.integrity_check`). A `FAIL` or a check that could not run (exit code 1 or 2) stops the update: it will not update a database that already has problems. A `WARN` never stops it.
3. **Closes the app** (it makes the daily backup first). It refuses if the pid file names something that is not this app, or if the database is locked.
4. **Makes a verified backup** in `data\backups\pre-update\` (the newest 10 are kept there; nothing else is ever deleted there) and writes the old version, the backup name and its sha256 into `data\logs\update-<moment>.log`.
5. `git pull --ff-only`. 6. Installs Python packages (only if `requirements.txt` changed), runs `npm ci` (only if `package-lock.json` changed), builds the screens.
7. **Updates the database** in a fresh process, so the new code does it. 8. Checks the database again.
9. **Starts the app** and waits until it answers.

If step 5, 6, 7, 8 or 9 fails, it **goes back by itself**: `git reset --hard` to the old version, the pre-update backup is copied over `data\shop.db` and checked (sha256), the old screens are built, the old app is started. A failed `git pull` that changed nothing only starts the app again. If the new version would not start, the failed (already migrated) database is kept as `data\backups\pre-update\shop-failed-update-<moment>.db` for the planning chat. If the app answers healthy anyway (it was only slow), nothing is undone.

The last message says `Updated to <version>` (done), `Nothing was changed` (refused), or `Rolled back to <version>` (rolled back). All messages and the log are in English. Exit code 0 = done, 1 = refused or rolled back, 2 = could not run (for example no internet, or the rollback itself failed: then follow section 6a with the numbers printed in the window).

**Things to know**
- **The updater that runs is always the previous version:** it is loaded before `git pull` replaces the files. A fix to the updater takes effect on the update after the one that brings it.
- **Changed or untracked files, or another branch:** it refuses at step 1 and changes nothing (it never stashes, deletes, overwrites or switches branch). Ask the planning chat.
- **First time on a laptop that has no `update-rebel.cmd` yet** (the old way, once): write down the version first (`git rev-parse HEAD`), then `.\stop-rebel.cmd`, copy `data\shop.db` somewhere safe (for example `Copy-Item data\shop.db data\shop-before-update-tool.db`), `git pull`, `.\start-rebel.cmd --rebuild`, `.venv\Scripts\python -m tools.integrity_check`. If this first update fails: `git reset --hard <the version you wrote down>`, `.\start-rebel.cmd --rebuild`. The database is not touched by that update; the first update that changes the database goes through `update-rebel.cmd`.
- **Try it first on a copy:** `.venv\Scripts\python -m tools.update_app --rehearse data\restore-test\real\shop.db` copies that database into `data\restore-test\rehearsal-<moment>\`, runs the check, the migrations and the check again, and compares the figures before and after (rows per table, profit and loss, every material and product, settlement totals). Any difference is a failure. It never touches git, the app, `data\shop.db`, `data\backups` or `data\logs`, and it refuses a file inside `data\` (outside `data\restore-test`).

## 6a. Manual rollback (a problem found AFTER the app has been used)

<span style="color:red">**Everything entered since the update is lost.**</span> The backup was made before the update; whatever you typed afterwards (sales, purchases, expenses) exists only in the current database. Do this only if you must. Keep the current file (it is renamed, not deleted), so the planning chat can still look at it.

1. `.\stop-rebel.cmd`
2. Find the old version and the backup in the update log: `Get-Content (Get-ChildItem data\logs\update-*.log | Sort-Object Name | Select-Object -Last 1).FullName` (lines `old HEAD ...` and `backup ... sha256 ...`).
3. `Rename-Item data\shop.db shop-after-update-2026-10-22.db` (use today's date)
4. `Copy-Item data\backups\pre-update\<the backup named in the log> data\shop.db`
5. `git reset --hard <old HEAD from the log>`
6. `.\start-rebel.cmd --rebuild`, then `.venv\Scripts\python -m tools.integrity_check` (the last line must be `OK`).

## 6b. The update was interrupted (power cut, closed window)

While an update runs, `data\logs\update-state.json` says how far it got, and the log `data\logs\update-<moment>.log` has one `STEP n/9 ...` line per step. If the state file exists, **a new update refuses to start**; run:

```powershell
.venv\Scripts\python -m tools.update_app --recover
```

It reads the state file and undoes what the update did, then starts the app. The last `STEP` line in the log tells where it stopped:

| Last step reached | What happened | What `--recover` does |
|---|---|---|
| 1 or 2 | nothing was changed (no state file) | nothing to recover: start the app with `start-rebel.cmd` |
| 3 or 4 | the app was closed; maybe a backup was made | only starts the app |
| 5 | the pull may have run | puts the code back if it moved; the database was not touched; starts the app |
| 6, 7 or 8 | packages, screens or the database may have changed | restores the database from the pre-update backup (checked), puts the code back, rebuilds the old screens, starts the app |
| 9 | the new version was starting | if the app answers healthy: nothing to undo; otherwise the same as 6-8 |

`--recover` refuses when the app is running (stop it first), when the update process is still alive, and when the update had **finished** (the app was started and used): then only the manual rollback (6a) is left.

## 7. What starts how (for the curious)

`start-rebel.cmd` runs `python -m tools.run_app`: it picks a free port (8000 first), starts **one** server process that serves both the screens and the data (the data lives under `/api`), waits until it answers, and opens the browser. The browser remembers things (an unfinished stocktake, the currency choice) **per address including the port**; if the port changes from one day to the next, the start window tells you.

Developers can still run the old two-server way (`npm run dev` in `frontend\` plus `uvicorn api.main:app` with `REBEL_DB` set to a **copy**); that is not for daily use.

## 8. When something is wrong

| The window says | Do this |
|---|---|
| "The Python environment was not found" | In PowerShell: `python -m venv .venv` then `.venv\Scripts\pip install -r requirements.txt`; double-click start again. |
| "Python packages are missing" | `.venv\Scripts\pip install -r requirements.txt` |
| "Node.js is needed once to build the screens" | Install the **LTS** version from <https://nodejs.org> (accept the defaults), close the window, double-click start again. Node is only needed to build the screens, not to run the app. |
| "Building the screens failed" | Open `data\logs\build.log` and send the last lines to the planning chat. |
| "No free port between 8000 and 8099" | Restart the computer, or find what uses the ports: `netstat -ano \| findstr :8000`. Send the message to the planning chat. |
| "REBEL_DB points to a file that does not exist" | A leftover setting: `Remove-Item Env:REBEL_DB`, then start again. |
| "REBEL_DB … inside the real data folder" | Put the practice copy in its own folder (section 5). |
| "The server did not start" | The window prints the last log lines. Open `data\logs\server.out.log` and `data\logs\app.log` and send them to the planning chat. |
| "not running or not ours" (when stopping) | Nothing was stopped, on purpose: the recorded process is not this app any more. If the app still answers in the browser, close the python.exe it started from Task Manager. |
| The browser says the site cannot be reached | The app is not running: double-click start. |

**A port is busy:** the start script skips busy ports and the ranges Windows reserves for itself, and takes the next free one (8001, 8002 …). It prints which ones it skipped.

## 9. Do not

- Do not edit `data\shop.db` by hand, and do not put practice copies directly in `data\`.
- Do not delete `data\backups` files "to tidy up" (the app keeps the newest 60 itself); the `shop-…` copies and the `pre-update` and `pre-migration` folders are your safety net after updates.
- Do not run two copies of the app on the same database.
- Do not run the go-live reset (section 10) on the real database more than once, and never while the app runs.

## 10. Go-live reset (once, before the first real sale)

Turns the test database into a clean one: all test orders, purchases, production, expenses, postage payments, settlements, payouts and stock movements are removed, stock goes to 0, product unit costs become "unknown" (the stocktake asks for them), invoice numbers restart (the first sale is `INV-000001`), the duplicate payment method DigiPay / digipay becomes one, and the audit log is archived and cleared. Products, materials (with their recipes, kits and categories), suppliers, partners, payment methods and settings stay as they are. SERVICE materials keep their unit cost.

**It can be done only once.** Afterwards the tool refuses to erase that database again (it would be real data), and says "already reset" if nothing has been entered yet.

1. **Clear the stocktake draft in every browser you use.** Open the app, go to «شمارش موجودی», and use the clear-draft button (the draft lives in the browser, per address and port; an old draft would come back with old counts, and nothing on the server stops that).
2. **Move the old invoice PDFs away** (the project's `invoices\` folder and your Downloads folder): the new invoices get the same names (`invoice_INV-000001.pdf` ...). The tool only counts and warns; it never deletes them.
3. **Stop the app:** `.\stop-rebel.cmd`. The tool refuses to run while it can see the app running (pid file, ports 8000 to 8099) or while the database is locked.
4. **Look first (changes nothing):**

   ```powershell
   .venv\Scripts\python -m tools.go_live_reset
   ```

   It rehearses the reset on a copy in memory and prints, per table, the rows before and after, the payment method merge, the counters and the result of the integrity checks. Nothing is written.
5. **Do it:**

   ```powershell
   .venv\Scripts\python -m tools.go_live_reset --apply
   ```

   It makes a verified backup first (`data\backups\pre-go-live\daily-YYYY-MM-DD-HHMMSS.db`; the app never cleans up that folder), then asks you to type `RESET shop.db`; anything else cancels. Then everything happens in one step: if any part fails, nothing changes. The old audit log is saved as `data\backups\audit-archive-golive-<moment>.jsonl`. At the end it runs the integrity check; the last line must be `OK`, with no `WARN`, `FAIL` or `INFO` lines (`d3` says SKIPPED, as always).
   Options: `--product-unit-cost zero` (instead of "unknown"), `--reset-service-costs` (also set SERVICE material costs to 0). Exit code 0 = done, 1 = refused or rolled back (nothing changed), 2 = could not run.
6. **Start the app** (`.\start-rebel.cmd`), enter the opening stock in «شمارش موجودی», then run `.venv\Scripts\python -m tools.integrity_check`. In the stocktake, type the unit cost on **every** gain: for a product the screen asks for it, for a **material it does not**, and a material gain without a cost stays at cost 0.
7. **If something is wrong** right after: stop the app and restore the `pre-go-live` backup by hand, exactly as in section 4 (copy that file in as `data\shop.db`).

Practice first on a copy in its own folder, for example `data\restore-test\golive\shop.db` (see section 5), with `--db data\restore-test\golive\shop.db`; its backup and archive then go next to the copy, never into your real `data\backups`.
