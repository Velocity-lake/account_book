I will update the "Download Standard Template" feature to ensure consistency between the generated template and the import logic, and improve the user experience with better error messages and UI hints.

### Plan

1.  **Refactor `importers.py`**:
    -   Define a global constant `STANDARD_TEMPLATE_COLUMNS` containing `["交易时间", "金额", "消费类别", "所属类别", "账户", "转入账户", "转出账户", "备注"]`.
    -   Update `import_standard_rows` to use this constant for validation.
    -   Improve the `ValueError` message to explicitly list missing columns AND all required columns when validation fails.

2.  **Update `ui_main.py`**:
    -   **Update `download_template`**: Import and use `STANDARD_TEMPLATE_COLUMNS` from `importers.py` to generate the Excel file. This ensures the template always matches the importer's expectations.
    -   **Update `build_sidebar`**: Add a warning label "请勿修改模板列名和结构" (Do not modify template structure) below the "Download Standard Template" button.
    -   **Update `_show_error_dialog`**: Add logic to detect "missing column" errors. If detected, add a "重新下载模板" (Re-download Template) button to the error dialog that triggers the download flow.

3.  **Verification**:
    -   Download the new template and verify it contains the "消费类别" column.
    -   Attempt to import the new template to ensure success.
    -   Simulate a "missing column" error (by importing a bad file) to verify the improved error message and the "Re-download" button in the dialog.
