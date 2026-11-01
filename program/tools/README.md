# tools/

维护脚本。除 `run_dev.py`（`启动程序.bat` 调用）外，都是**手动运行**的，不参与程序启动。

| 脚本 | 作用 | 什么时候用 |
|---|---|---|
| `run_dev.py` | 同步 `src/` → `build_env/` 并启动程序 | 每次开发运行（被 bat 调用） |
| `bake_ui_text.py` | 把固定文案渲染成 `res/assets/ui/text/*.png` | 改了界面文案之后 |
| `build_exe.py` | 用 PyInstaller 打包 | 发版 |
| `build_portable.py` | 打绿色版目录 | 发版 |
| `build_story_index_v2.py` | 从剧本构建检索索引 `story_index.json` | 换了剧本数据 |
| `check_assets.py` | 检查素材是否齐全 | 换机器 / 缺素材时 |
| `make_placeholder_assets.py` | 生成占位素材（纯色块） | 没有游戏素材也想跑起来 |
| `preview_assets.py` | 预览素材与坐标 | 调界面坐标 |
| `setup_assets.py` | 下载可自动获取的部分素材 | 首次部署 |

## 约定

- 脚本一律从 `program/` 为根做相对路径，不要写死绝对路径
- 会写文件的脚本，输出都落在 `res/` 或 `cache/` 下，不要污染 `src/`