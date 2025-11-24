## 我的理解
- 你希望在账单列表中一键进入“批量录入”模式：自动打开一个 Excel 文件，让你在其中填写/粘贴多行账单。
- 当你关闭 Excel 后，程序自动把这些行按标准模板导入为新账单（默认是“追加导入”，不覆盖历史），并完成资产余额联动、分类校验与来源标记。
- 不要求依赖额外大型库，优先用现有代码与标准库实现；在 Windows 场景尽量做到“关闭 Excel 即自动导入”。

## 可行方案
- 方案A（推荐，零依赖）：导出标准模板并打开 Excel，后台线程轮询检测文件写入时间与 `EXCEL.EXE` 进程；确认 Excel 关闭且文件稳定后，自动调用现有 `importers.import_standard_xlsx` 追加导入。
- 方案B（精确监听，需要依赖）：使用 `pywin32` 通过 COM 打开 Excel，监听工作簿关闭事件再触发导入；优点是准确，缺点是新增依赖与环境要求。
- 方案C（半自动，无依赖）：打开 Excel 后，在页面新增“我已关闭并完成编辑”按钮，你点击后再导入；优点稳定简单，缺点不是完全自动。

## 推荐默认实现（方案A）
- 在账单列表工具栏新增按钮“Excel批量录入”。
- 当点击按钮：
  - 生成当天临时模板文件（例如 `temp/batch_entry_YYYYMMDD_HHMM.xlsx`），表头采用当前标准模板：`交易时间/金额/消费类别/所属类别/账户/转入账户/转出账户/备注`。
  - 用系统默认 Excel 打开该文件（Windows 用 `os.startfile`）。
  - 启动后台监测：
    - 轮询文件 `mtime`，当连续一段时间未变化且系统中不存在活跃的 `EXCEL.EXE` 进程（基于 `tasklist` 解析）即认为已关闭并保存。
    - 触发 `importers.import_standard_xlsx(path, account_names)` 进行“追加导入”，为每条记录设置 `record_time=now` 与 `record_source="Excel批量录入"`。
  - 导入完成后弹出统计信息（成功/跳过/疑似重复等），并 `refresh()` 刷新列表。

## 改动位置
- `ui_bill_list.py:22 build_ui`：在工具栏区域新增 `ttk.Button(text="Excel批量录入", command=self.open_excel_batch_entry)`（参考现有 `导入并覆盖`/`导入账单`/`导出筛选CSV` 按钮，位置建议靠右）。
- `ui_bill_list.py` 新增方法：
  - `open_excel_batch_entry()`：创建临时模板并打开 Excel，启动监测线程；监测结束后调用导入并刷新。
  - 复用现有 XLSX 生成逻辑（项目中已有多处 `_write_xlsx` 简易写法与“下载标准模板”逻辑，避免引入第三方库）。
- 复用与调用点：
  - `importers.import_standard_xlsx`（`importers.py`）进行解析和标准化；
  - `get_account_names`、`apply_transaction_delta`、`save_state`（`storage.py`）完成资产联动与持久化；
  - `xlsx_reader.read_xlsx`（`xlsx_reader.py`）已支持首行表头读取与 Excel 序列日期。

## 导入规则与校验
- 模板列必须包含：`交易时间`（或 `格式化时间`）、`金额`、`消费类别`、`所属类别`、`账户`、`转入账户`、`转出账户`、`备注`（与现有标准模板一致）。
- 金额解析与时间解析、分类合法性、账户存在性，沿用 `import_standard_rows` 的校验；必要时自动新增分类（已有逻辑：`add_category`）。
- 记账来源统一记为 `Excel批量录入`，记账时间为当前时间；资产联动通过 `apply_transaction_delta`。

## 交互细节
- 打开模板后你可以新增/粘贴任意行；保存并关闭 Excel 即自动导入（方案A）。
- 若 Excel 残留后台进程导致“自动判断关闭”不准确，可在超时后弹出提示，引导使用“手动确认按钮”（方案C 兼容）。
- 支持失败与跳过条目统计，并在导入后刷新列表与页脚统计。

## 你是否同意
- 若你同意采用“方案A（零依赖自动导入）”，我将按上述改动位置实现，并保证与现有风格一致。
- 若你更偏好“方案B（COM精确监听）”或“方案C（半自动确认）”，也可以切换，默认我先做方案A。
- 请回复你选择的方案或直接确认“方案A”，我即可开始修改程序。