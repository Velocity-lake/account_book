## 目标

* 导出功能不再生成 `.ps` 文件，只生成同名的 `PNG` 与 `PDF` 两种格式

* 保持现有“导出全部图表”与打包压缩行为；提高用户可用性与跨平台兼容性

## 涉及位置

* `ui_dashboard.py:1103-1121` 函数 `export_canvas`

* `ui_dashboard.py:1127-1147` 函数 `export_all_charts`

* 依赖目录：`storage.py:441` 的 `get_export_dir()` 不变

## 实现方案

* 在 `export_canvas` 中移除写入 `.ps` 的逻辑；改为生成 `PNG` 与 `PDF`

* 首选高保真路径（如果系统支持）：

  * `ps_data = canvas.postscript(colormode='color', width=canvas.winfo_width(), height=canvas.winfo_height())`（不落盘）

  * 使用 `Pillow` 打开 `ps_data`（需要系统有 Ghostscript 支持 PS/EPS）后，保存 `fname_png` 与 `fname_pdf`

* 失败时自动降级为屏幕捕获路径（无外部依赖）：

  * 通过 `ImageGrab.grab(bbox=(canvas.winfo_rootx(), canvas.winfo_rooty(), ...))` 截取画布区域

  * 保存为同名 `PNG`，并用 `Pillow` 将该位图写入 `PDF`

* 返回值改为仅包含生成的 `PNG/PDF` 路径，并在成功提示中仅显示这两种格式

* `export_all_charts` 维持循环导出逻辑，收集 `PNG/PDF` 路径并打包；压缩包仍命名为 `charts_{模式}_{期间}_{时间戳}.zip`

## 代码级改动要点

* 新增导入：`from PIL import Image, ImageGrab` 与 `import io`

* 移除 `.ps` 相关文件路径与 `messagebox` 文案中的 `.ps`

* 增加对 `canvas.update_idletasks()` 的调用以确保几何信息准确

* 错误处理沿用现有 `try/except`，在两条路径都失败时给出错误提示

## 兼容性与依赖

* 保持现有 `Pillow` 依赖

* 当系统安装了 `Ghostscript` 时，优先使用矢量转栅格，图像更清晰

* 未安装 `Ghostscript` 时自动回退到屏幕截取，保证一定可用性

## 验证

* 运行应用，点击“导出全部图表”，检查导出目录：应生成每个图 `*.png` 与 `*.pdf`，不再出现 `.ps`

* 打开压缩包，确认包含所有 `PNG/PDF`

* 目视检查清晰度：有 Ghostscript 时清晰度更佳；无则为屏幕分辨率

## 注意事项

* 屏幕截取要求窗口未被其他窗口遮挡；为获得最佳效果，导出前确保窗口前置

* 若后续希望统一为更高保真且无外部依赖，可考虑将图表改为 `matplotlib` 绘制并用 `savefig('png/pdf')` 导出

