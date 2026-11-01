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
| `ui_probe.py` | 用真实 WebView2 打开界面、跑 JS、截图（自测用） | 改完界面要验证「JS 真的跑了」时 |

## 自测：ui_probe.py

改前端必须验证**执行路径**，不是「文件里有这行代码」。这个探针开一个真的 WebView2
窗口（和正式程序同一个引擎），可以用 JS 点按钮、读状态，还能截图。

```powershell
# 终端 1：起后端（日志里会打印端口）
cd program\build_env; .\venv\Scripts\python.exe main.py --serve-only

# 终端 2：跑一段 JS 并截图
python tools\ui_probe.py --url http://127.0.0.1:8771/game/index.html `
    --js setup.js --check check.js --wait 1200 --shot out.png
```

- `--js` 打开后先执行（点按钮、改状态）
- `--wait` 等多久（给 fetch / 动画留时间）
- `--check` 等待后再执行一次（读结果）
- `--shot` 截图（Win32 PrintWindow，抓窗口真实画面）

两个 JS 文件都以 `return <可 JSON 化的值>` 结尾，结果会打印出来。
坑：同一段 JS 里**改完 class 立刻读 `getComputedStyle().opacity` 会拿到过渡前的值**，
要量结果就放到 `--check` 里，等过渡跑完再读。

## 约定

- 脚本一律从 `program/` 为根做相对路径，不要写死绝对路径
- 会写文件的脚本，输出都落在 `res/` 或 `cache/` 下，不要污染 `src/`