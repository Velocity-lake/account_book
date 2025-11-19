# 个人记账本（accout_book）

一个使用 Python `tkinter` 构建的桌面记账应用，支持账单记录、账户管理、导入/导出、简单截图识别等功能。

## 特性
- 记录与管理收入/支出、转账、还款等交易
- 账户管理与余额联动
- 账单导入（支付宝/微信/标准模板/电商截图简易识别）
- 数据备份与重复项去重
- 自定义可见列与菜单布局

## 环境要求
- Python 3.12+
- 操作系统：Windows/macOS/Linux
- 依赖：当前仅使用标准库，无第三方依赖

## 安装与运行
```powershell
# 创建并激活虚拟环境（Windows）
python -m venv .venv
.venv\Scripts\activate

# 如需安装依赖（当前为空，可跳过）
pip install -r requirements.txt

# 启动应用
python app.py
```
入口参考 `app.py:15`。

首次运行会在项目根目录下创建 `data/` 并生成账本文件 `data/ledger.json`。

## 配置
- 若需接入外部 OCR 或 API，请将真实密钥放入环境变量或 `.env` 文件，并提供示例 `env.example`，不要提交真实密钥。

## 目录结构
```
accout_book/
├─ app.py               # 应用入口（tkinter）
├─ ui_*.py              # 界面模块
├─ storage.py           # 数据读写与账户/交易逻辑
├─ models.py            # 数据模型
├─ importers.py         # 各平台导入逻辑
├─ import_ai.py         # 简易截图文本解析
├─ ocr_adapter.py       # OCR 适配层（可替换）
├─ xlsx_reader.py       # 轻量 XLSX 读取
├─ README.md
├─ LICENSE
├─ requirements.txt
└─ .gitignore
```

## 许可证
本项目使用 MIT 许可证，详情见 `LICENSE`。

## 贡献
欢迎提交 Issue 与 Pull Request。建议先讨论大型功能或改动方案。