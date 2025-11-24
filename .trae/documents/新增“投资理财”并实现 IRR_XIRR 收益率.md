## 我对你需求的理解
- 在“投资理财”模块中，拥有一套与主菜单“账单列表”完全一致的列表样式与交互，但其数据源为独立数据库（不与主账本混用），便于单独管理投资相关账单。
- 你将录入或导入历史的买入、卖出明细，以及当前估值；系统按这些现金流计算每个理财账户的 XIRR（非等间隔 IRR 年化收益率）。
- 买入用“转入到该理财账户”表达；卖出用“从该理财账户转出”表达；转入和转出的另一方账户可以为空。

## 数据与存储设计（独立账本）
- 新建“投资账本”文件（与主账本分离）：
  - 单用户：`data/invest_ledger.json`
  - 多用户开启时：`data/users/<user_id>/invest_ledger.json`
- 文件结构：
  - `accounts`: 投资账户列表（仅用于分组与展示），形如 `{name, note}`
  - `transactions`: 投资账单列表，字段与主账单保持一致以复用 UI：`{id, time, amount, category, ttype, account, to_account, from_account, note, record_time, record_source}`
  - `valuations`: 每个账户的估值字典，形如 `{account_name: {date: "YYYY-MM-DD", value: float}}`
- `storage.py` 增加投资账本读写：
  - `get_invest_ledger_path(user_id=None)` / `set_invest_ledger_path(path)`
  - `load_invest_state()` / `save_invest_state(state)`
  - 辅助：`get_invest_account_names(state)`, `add_invest_account(state, account)`, `remove_invest_account(...)`。
  - 不影响主账本余额计算（投资账本不做 `apply_transaction_delta` 资产联动）。

## 现金流到 IRR 的换算规则
- 分组口径：以“投资账户”分组，计算每个账户的 XIRR。
- 现金流符号约定：
  - 买入（`ttype == "转账"` 且 `to_account == 投资账户`）：记为负现金流（投资人支出）。
  - 卖出/赎回/分红（`ttype == "转账"` 且 `from_account == 投资账户`）：记为正现金流（投资人收入）。
  - 允许 `from_account` 或 `to_account` 为空；根据是否与投资账户匹配来判定方向。
- 终止现金流：若账户设置了当前估值 `{value, date}`，在计算时追加一条终止正现金流 `(date, +value)`。
- 计算方法：
  - 在 `utils.py` 实现 `xnpv(rate, cash_flows)` 与 `xirr(cash_flows)`（牛顿迭代 + 二分法兜底，确保鲁棒）。
  - 需要至少一正一负现金流，否则返回空值。

## UI 页面与交互
- 侧边栏新增“投资理财”入口（`ui_main.py:62–82`），图标在 `ui_icons.py:12–24` 增加 `'invest'`。
- 新增页面 `ui_investments.py`（模块首页）：
  - 表格列：`账户名、累计投入、累计回款、当前市值、盈亏、ROI、XIRR（年化）、持有天数`。
  - 操作区：新增/删除账户、设置估值、打开“投资账单列表”。
- 新增 `ui_invest_bill_list.py`：
  - 样式与交互完全复用 `ui_bill_list.py`（列、筛选、排序、右键菜单等），但数据源改为 `load_invest_state()` 与 `save_invest_state()`。
  - 新增导入模板与导出功能（独立于主账本）。
  - 新增“批量改为转账”仍可用；并保留“批量修改账户/转入/转出账户”等，以便快速规范买入/卖出记录。
- `ui_main.py`：在 `self.pages` 增加 `"invest"`，提供 `show_investments()` 与从投资页面打开独立账单列表的入口。

## 导入与录入
- 支持以标准模板 CSV/XLSX 导入投资账单，字段与主账单一致；你只需把“买入/卖出”映射为上述“转账”的方向。
- 手动录入支持：新增投资交易对话框，字段同主账单（可复用既有对话框的布局与校验）。

## 计算展示与边界
- IRR 以百分比显示，两位小数（如 `12.34%`）；遇到迭代失败或现金流不足，显示 `—`。
- 汇总区显示该账户：累计投入（负流绝对和）、累计回款、当前市值、盈亏与 ROI。
- XIRR 基准日期取第一笔现金流日期；持有天数以第一笔至估值日期（或最后现金流日期）。

## 修改范围
- 新文件：`ui_investments.py`, `ui_invest_bill_list.py`。
- 修改文件：`storage.py`, `ui_main.py`, `ui_icons.py`, `utils.py`。
- 不引入第三方库，算法纯 Python。

## 待你确认的点
- 是否同意：使用独立投资账本文件与独立“投资账单列表”页面，样式与主账单一致。
- 买入/卖出用“转账”方向判定现金流符号的规则是否符合你的习惯？
- 是否需要在投资首页展示账户维度的汇总指标（ROI/XIRR/持有天数等）并提供入口打开账单列表？

你回复“同意”后，我将按此方案修改程序、联调并验证。