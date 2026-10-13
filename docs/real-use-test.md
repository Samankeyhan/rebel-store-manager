# First week of real use: evening checklist

Goal: find out in the first week whether the numbers in the app agree with each other and with the real shop. Nothing here changes data; the check only reads.

Do not edit `data\shop.db` by hand (no DB browser, no SQL), and do not delete or rename it.

## Every evening (about 10 minutes)

1. **Stop working in the app** (close the browser tab; stop the API/server if it is running), so the check sees a quiet database.
2. **Run the check** in PowerShell, from the project folder (`C:\Users\Saman\rebel-store-manager`). It prints the report and also saves it:

   ```powershell
   [Console]::OutputEncoding = [Text.Encoding]::UTF8; .venv\Scripts\python -m tools.integrity_check | Tee-Object -FilePath "data\integrity-$(Get-Date -Format yyyy-MM-dd).txt"; "exit code: $LASTEXITCODE"
   ```

   The last line of the report is `OK`, `FAILED: <n> problems` or `INCOMPLETE: ...`. The exit code is 0 (OK), 1 (problems found) or 2 (it could not run, or a check could not run).
3. **See what changed since yesterday** (new `WARN` rows, changed `INFO` lines, new `FAIL` rows; the header lines are skipped):

   ```powershell
   $t = "data\integrity-$(Get-Date -Format yyyy-MM-dd).txt"; $y = "data\integrity-$((Get-Date).AddDays(-1).ToString('yyyy-MM-dd')).txt"; Compare-Object ((Get-Content $y | Select-Object -Skip 9) -match 'INFO|WARN|FAIL') ((Get-Content $t | Select-Object -Skip 9) -match 'INFO|WARN|FAIL')
   ```

   `<=` = only in yesterday's report, `=>` = only in today's. Nothing printed = no change.
4. **Compare with your own counts** (the check cannot know what is in your hands or on your shelf):
   - For each payment method: the app's dashboard / settlements screen figure vs the money you count (card-to-card receipts, gateway panel, cash). Write both numbers down.
   - Physical stock: count 3 to 5 items on the shelf (a product, a material, a packaging item) and compare with the app's stock. Write both numbers down.
5. **Send to the planning chat**: every `FAIL` and `WARN` row exactly as printed (copy the lines, do not retype), the last line of the report, and your own counts from step 4 (what the app says, what you counted, which item or method).
6. **Make a dated copy** of the database until automatic backups exist:

   ```powershell
   Copy-Item data\shop.db "data\shop-$(Get-Date -Format yyyy-MM-dd).db"
   ```

   (Copies named `data\shop-*.db` and the `data\integrity-*.txt` reports stay on this computer; git ignores them.)

## What the lines mean

- **PASS**: the numbers agree. **FAIL**: they do not; the rows under it say which table, which id, which field, what is stored, what was expected and the difference (money in whole Rial). Report every FAIL, even a difference of 1.
- **WARN**: look, but not necessarily an error. A *fee differs from the method's current rule* means that order's fee was typed by hand or the method's fee was edited later; tell me if you did not do either. *Name collisions* are two records with the same name in different spellings; they are listed every evening until you decide what to do.
- **INFO**: a note, not a problem. *Implied opening balance* lines are materials that were created with some stock before the history started; the number should stay the same every evening. If it changes, report it.
- **INFO `orders ids=[…] … legacy`**: orders that were completed before the app recorded payment dates (no payment method, no paid date); they are listed every evening. If a NEW order id ever appears in that line after go-live, report it to the planning chat.
- **SKIPPED**: that check needs a newer database than yours (it says which); nothing is wrong. Mention it once and ignore it afterwards.
- **Exit code 2** or a line starting `CANNOT RUN` or `ERROR` / `INCOMPLETE`: the tool could not read the database or could not finish. Copy the message exactly, do not run it again and again, and send it. Never "fix" the database yourself.

If the app is open and writing while the check runs, a number can change between two checks and show up as a mismatch that is not real. Run it again once the app is closed before reporting.
