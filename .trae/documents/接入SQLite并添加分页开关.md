## 数据库结构
- 文件路径：`data/ledger.db`
- 表：
  - `transactions(id TEXT PRIMARY KEY, time TEXT, amount REAL, category TEXT, ttype TEXT, account TEXT, to_account TEXT, from_account TEXT, note TEXT, record_time TEXT, record_source TEXT)`
  - `accounts(name TEXT PRIMARY KEY, balance REAL, type TEXT, note TEXT, bank TEXT, last4 TEXT, limit REAL, status TEXT, bill_day INTEGER, repay_day INTEGER, repay_offset INTEGER)`
  - `categories(scene TEXT, name TEXT, PRIMARY KEY(scene, name))`
  - `category_rules(scene TEXT, keyword TEXT, category TEXT, PRIMARY KEY(scene, keyword, category))`
  - `record_sources(name TEXT PRIMARY KEY)`

## 索引与约束
- 交易索引：`transactions(time)`, `transactions(record_time)`, `transactions(amount)`, `transactions(ttype)`, `transactions(category)`, `transactions(account)`
- 组合索引：`transactions(ttype, category)`、可选 `(account, time)` 支撑常见筛选+排序
- 主键唯一约束保证数据一致性

## 迁移与初始化
- 首次启用 SQLite 时：
  - 初始化表与索引
  - 从现有 `data/ledger.json` 读取并一次性导入 `transactions`、`accounts`、`categories`、`category_rules`、`record_sources`
  - 写入 `prefs.storage_backend = "sqlite"`
- 保留 JSON 文件用于备份/导出；备份机制不变

## 存储后端开关
- `storage.py` 新增后端选择：
  - 若 `prefs.storage_backend == "sqlite"` 使用 DB 分支；否则维持 JSON 分支
  - 不改动调用方函数名：`load_state/save_state/get_transaction/add_transaction/update_transaction/remove_transaction`

## 查询接口
- 新增 `storage.query_transactions(filters, limit=None, offset=None)`：
  - 支持筛选字段：年份、月份、`ttype`、`category`、全文 `term`、金额条件（`amt_op`,`amt_val`）、列过滤（账户相关等）
  - 排序：按当前列（如时间/金额）与方向生成 `ORDER BY`
- 新增聚合接口：`storage.aggregate_sums(filters)` 返回收入/支出/转账合计

## UI 改造（最小入侵）
- `ui_bill_list.py`：
  - 数据来源改为 `query_transactions`（当 `use_pagination=False` 不传分页参数，一次性渲染；开启分页时传 `limit/offset`）
  - 汇总统计改为 `aggregate_sums`
- `ui_dashboard.py`：列表数据与批量操作仍走现有 CRUD；如有大表展示，同步接入 `query_transactions`（保持行为一致）
- 保留现有排序按钮与列过滤逻辑，只是将排序/筛选下推到 SQL

## 设置项
- 在 `SettingsPage` 增加两项：
  - 存储后端：`SQLite`（默认）/`JSON`（回退用），写入 `prefs.storage_backend`
  - 分页模式开关：`prefs.use_pagination`（默认 False），开启后账单列表与仪表盘分页显示（如每页 200 条），关闭时一次性渲染当前筛选全集

## 验证与回滚
- 验证：
  - 大数据筛选/排序响应时间（秒级）
  - 批量增删改与账户余额联动一致性
  - 选中统计正确性
- 回滚：设置页切回 `JSON` 即回到旧后端；保留导出/备份能力

## 兼容性与性能
- 事务包裹批量写入，失败回滚
- 定期可执行 `VACUUM`/`PRAGMA integrity_check`（保留为内部工具按钮或自动）
- 索引覆盖常见查询路径，必要时按实际使用再加组合索引

请确认按该方案实施；确认后我将开始代码改造、迁移并验证。