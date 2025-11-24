# account_book

一个使用 Python/Tkinter 的简易记账桌面应用。

## 功能
- 提供基础的记账界面与交互
- 本地数据保存

## 环境要求
- Python 3.10 及以上（建议）
- 平台：Windows（其他平台待验证）

## 安装与运行
```bash
# 克隆仓库
git clone https://github.com/Velocity-lake/account_book.git
cd account_book

# （可选）创建并激活虚拟环境（PowerShell）
python -m venv .venv
. .venv/Scripts/Activate.ps1

# 安装依赖（当前依赖为空，如有需要再补充）
pip install -r requirements.txt

# 运行（任选其一）
python app.py
# 或使用批处理脚本
start_app.bat
```

## 目录结构
```
account_book/
├─ app.py           # 主程序入口
├─ README.md        # 项目说明
├─ LICENSE          # 开源许可证（MIT）
├─ .gitignore       # Git 忽略规则
└─ requirements.txt # 依赖列表（当前为空）
```

## 许可
本项目使用 MIT 许可证，详见 `LICENSE` 文件。

## 贡献
欢迎提出 Issue 或提交 Pull Request 改进项目。
