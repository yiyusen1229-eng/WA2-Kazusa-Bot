# AGENTS.md · 给 AI 代理的接手须知

**先读 `other/docs/交接速览.md`（1 页）。** 需要细节再看 `other/docs/新对话交接说明.md`（32 KB，别整份读：
用 `python tools/digest.py --outline <file>` 看目录，再按节读）。

## 项目是什么

WA2 冬马和纱桌面聊天程序：Python 本地 HTTP 服务 + WebView2 无边框窗口，galgame 界面，
对话走云端 LLM，语音走本地 GPT-SoVITS。角色 = `characters/<角色>/` 一个文件夹（自包含）。

## 常用命令

```powershell
program\启动程序.bat                                  # 启动（同步 src → build_env 再开窗）
python program\tools\run_dev.py --sync-only           # 只同步代码到 build_env
cd program\build_env; $env:WA2_ASSETS_DIR="..\res\assets"
.\venv\Scripts\python.exe main.py --serve-only --port 8791   # 只起后端（自测/探针用）
python program\tools\test_char_res.py                 # 6 个自测，全绿才算过
python program\tools\ui_probe.py --url http://127.0.0.1:8791/game/index.html `
    --js setup.js --check check.js --wait 1500        # 界面探针（--js/--check 收文件路径）
python program\tools\check_assets.py                  # 素材自检
```

## 省钱规则（每次任务都适用）

1. **不要整份读文件**：先 `tools/digest.py --outline`，再只读需要的那几节。
2. **diff 先 `--stat`**，确认涉及哪些文件，再看单个文件的 diff。
3. **界面问题先看探针返回的 JSON 数字**（高度、是否可滚、是否报错），截图只在必须判断视觉时看，别连拍。
4. **一任务一会话**：新会话只喂 `交接速览.md` + 本次任务，不要把历史对话贴回来。
5. **机械活交给便宜模型**：改名、批量替换、跑测试、跑探针。

## 不许动的东西

- `characters/`、`res/assets/`、`persona/`、`worldbook/`、`sessions/`、`release/` 是本地数据，**不入库、不上传**。
- 世界书结构不改；人设/记忆书内容只留本机，文档里不抄设定细节。
- 发布流程见 `新对话交接说明.md` 第 12、13 条（先整合旧补丁再发新补丁，旧补丁保留）。
