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

## 6. After an update (`git pull`)

The screens you see are built from the code; after new code arrives they must be built again (it takes one to two minutes and needs Node.js):

```powershell
.\stop-rebel.cmd
git pull
.\start-rebel.cmd --rebuild
```

If you forget `--rebuild`, the start window says "NOTICE: the screens were built from an older version". The database is updated automatically at start (a safety copy `shop-YYYYMMDD-HHMMSS.db` is made first). Afterwards run `.venv\Scripts\python -m tools.integrity_check`.

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
- Do not delete `data\backups` files "to tidy up" (the app keeps the newest 60 itself); the `shop-…` copies are your safety net after updates.
- Do not run two copies of the app on the same database.
