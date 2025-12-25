I have identified the cause of the issue. The application uses a dual-storage system (JSON file + SQLite database). The "Bill List" reads from SQLite for performance, but the "Import Bill" function (and several others) only updates the JSON file and the in-memory list, bypassing the SQLite database update. This causes the imported data to be saved to the file but not appear in the list.

Here is the plan to fix this issue and ensure data consistency:

1.  **Enhance Storage Module (`storage.py`)**
    *   Add a `add_transactions_bulk(state, transactions)` function to efficiently insert multiple transactions into both the state list and the SQLite database.
    *   Add a `clear_all_transactions(state)` function to clear transactions from both the state list and the SQLite database (needed for "Import and Override").

2.  **Fix Import Logic in Main Window (`ui_main.py`)**
    *   Update `_handle_import_rows` to use the new `add_transactions_bulk` function instead of manually appending to the list.
    *   Update `import_ai_images` to use `add_transactions_bulk`.

3.  **Fix Logic in Bill List (`ui_bill_list.py`)**
    *   Update `import_override` to use `clear_all_transactions` followed by `add_transactions_bulk`.
    *   Update `import_standard_xlsx_file` and `_watch_and_import_xlsx` to use `add_transactions_bulk`.
    *   Update `on_record_for_row` (Right-click -> Record for this day) to use the existing `add_transaction` helper instead of manual append.

4.  **Fix Record Page (`ui_record_page.py`)**
    *   Update `save_transaction` to use `add_transaction` instead of manual append, ensuring new records appear immediately in the Bill List.

This approach fixes the reported "Import" issue and also prevents similar issues in "Record Bill" and "Smart Import".