# 用例清单（核心 / 边界 / 降级）

> 规矩：**不追求覆盖率，追求「改完敢发布」**。一键跑：
>
> ```powershell
> python program\tools\run_smoke.py            # 全部（含在线冒烟，约 5 秒）
> python program\tools\run_smoke.py --no-live  # 只跑离线 / 静态
> python program\tools\run_smoke.py --cat 边界  # 只跑一类
> ```
>
> 表里的「自动化」列写脚本名；标「手动」的发版前必须自己点一遍。
> 新增用例：脚本放进 `program/tools/`（`test_*.py` / `test_*.js`）→ 在 `run_smoke.py` 的
> `STEPS` 里登记 → 本文档加一行。

## 核心（每次改动都要绿）

| 编号 | 场景 | 期望 | 自动化 |
|---|---|---|---|
| K1 | 角色资源定位 | 人设 / 世界书 / 记忆书 / 立绘 / 语音都能找到，缺了报得出来 | `test_char_res.py` |
| K2 | 角色包导出 / 导入 | 44 项：只带五类资源、路径穿越与体积上限被拒 | `test_char_pack.py` |
| K3 | 密钥与日志脱敏 | 24 项：掩码、环境变量优先、日志不含 `sk-` | `test_secret.py` |
| K4 | 记忆书界面 | 20 项：常驻只读、条目可删、删除只影响本轮注入 | `test_memory_view.py` |
| K5 | 存档 schema | 29 项：写版本、老档迁移、新档拒绝、坏档不覆盖 | `test_session_schema.py` |
| K6 | 运行状态 | 17 项：正常退出标记、强杀留标记、崩溃日志 | `test_runstate.py` |
| K7 | 缓存守卫 | 19 项：0 字节 / 半截 PNG / 坏 JSON 一律删掉重生成 | `test_cache_io.py` |
| K8 | 素材自检 | 13 项：清单、缺图、占位报告 | `test_assets_report.py` |
| K9 | 语音响度归一化 | 28 项：-20dBFS 正弦 → -20 LUFS、推到 -16、峰值保护 | `test_audio_gain.py` |
| K10 | 调试账本 | 35 项：结构、只读、不写正文 | `test_diag.py` |
| K11 | 参数表 | 51 项：区间 + 语义 + 文档与代码一致 | `test_params.py` |
| K12 | 演出状态机 | 23 项：重播 / 流式 / 浮层 / 切角色仲裁 + 快速连点 | `test_perf.js` |
| K13 | 交叉淡化 | 24 项：双层交替、收尾搬图、关过渡直接切 | `test_fade.js` |
| K14 | 启动 + 只读接口 | 起无模型服务：`/api/ping`、`/api/debug/state`、`/api/scene/list`、`/api/voice/ok`、`/api/log/bundle`、`/api/text` 都通 | `run_smoke.py`（在线） |
| K15 | 真实对话一轮 | 有回复、有情绪标记、面板能看到本轮分段 | 手动 |
| K16 | 存 → 读档 → 继续 | 时期 / 衣服 / 场景 / 记忆快照都回来 | 手动 |
| K17 | 切角色 | 名字、立绘、语音、存档目录整套换掉 | 手动 |
| K18 | 退出后重启 | `run_state.json` 干净，不弹「上次没有正常退出」 | 手动 |
| K19 | 诊断包 | `logs/wa2_diag_*.zip` 能打开、有 README、无密钥 / 用户目录 / 对话查询串；默认不含 `conversation.json` | `test_logpack.py`（+ 在线冒烟真调一次） |
| K20 | 性能采样 | `logs/perf-<日期>.csv` 表头只写一次、每 N 轮一行、`WA2_PERF=0` 关掉、写不进去也不抛 | `test_perf_sample.py` |
| K21 | 常驻记忆书两段化 | 没有 `standing.json` 时回落老文本；阶段变化后台刷一次摘要；fixed 不被程序改写；失败保留旧版 | `test_standing.py` |
| K22 | 演出/切片配置 | 没配置文件 → 默认值（且等于代码常量）；正常覆盖生效；超范围夹边界、类型不对回默认、未知键忽略、坏 JSON 全默认，每种都带 warning；切角色读对应文件 | `test_perfcfg.py`（+ `test_perfcfg.js` 验前端 `/api/performance` 拉取与 toast） |
| K25 | 剧情检索 | df 按文档去重（idf 不为负）；闲聊（今天好冷/我饿了）不检索；带剧情锚点才检索；常见词组成的问句能退档命中；k / max_chars 生效；只看账不含正文 | `test_story_rag.py` |
| K26 | 回复标签解析 | `<emotion>` 正常拆；拼错的 `</emomotion>` 不漏进台词；**没有标签时按台词形态猜情绪（毒舌/撒娇/哭腔/soft/问句），没线索才 calm，来源记在 `LAST_EMO_SOURCE`**；**明显难过的句子被标成 calm/毒舌时纠成哭腔（别的标签一律尊重模型）**；**双语块 `<ja>/<zh>` 拆得开、标签不漏进台词、单语/写坏也不炸，`looks_zh` 能分辨中文与日语**；scene/outfit/action/thinking 都能拆；`ja_clean` 只留第一行、去尾巴、人称改「あたし」 | `test_text_parse.py`（42 项） |
| K23 | 素材热重载 | 第一次只记基线；文件变了等签名稳定才触发；gen +1、勾子都调；某个勾子失败别的照跑；关掉不动作；角色目录变化 kinds=character；线程可停 | `test_hotreload.py`（+ `test_hotreload.js` 验前端轮询与重画） |
| K24 | 素材向导 | 缺立绘按衣服聚合、缺场景按 id、语音 0 字节/没参考音频、文本三件套未导入；补齐后各步 ok；每步可跳过 | `test_wizard.py`（+ 真机探针看 `data-uitxt`） |
| K27 | 窗口接口归属 | `python main.py` 起时真身是 `__main__`：`main.py` 顶部把 "main" 别名指过去；`api_window.py` 经 `winutil._main_module()` 取窗口，不直接 `import main`；`_main_module()` 在有窗口/没窗口两种情况下都挑得对。**防「全屏 / 最大化点了没反应」——接口回 200 但 error 里写着 `module 'main' has no attribute '_WINDOW'`** | `test_window_api.py`（真机验证另见 `other/docs/踩坑记录` 第十条） |
| K28 | 数据清理入口 | 概览 8 个清理项体积算得对（运行时缓存只算三份、日志只算 app-*.log）；清缓存保留今天正在写的日志、不碰存档与角色内容、未知 key 不算失败；导出 zip 有 manifest / README、跳过 `.bak`、不带素材、默认不带对话、`sk-` 已脱敏、turns>0 才带 sessions；删角色四种拒绝（确认名不对 / 当前角色 / id 带 `..` / 不存在），成功时整目录挪进 `characters/_deleted/` 且清掉 `cache/<角色>/` | `test_cleanup.py`（59 项） |

## 边界（极端输入不炸，行为仍可预期）

| 编号 | 场景 | 期望 | 自动化 |
|---|---|---|---|
| B1 | 长会话 100 轮 | 估算 / 预算 / 原文起点 / 条目渲染都不崩 | `test_boundary.py` |
| B2 | 长会话 500 轮 | 同上，且原文段不超过预算的 1.3 倍 | `test_boundary.py` |
| B3 | 缓存满 | 条目超上限只留最近 N 条，progress 只留一条 | `test_boundary.py` |
| B4 | 素材缺失 | 立绘画不出来 → 空串走兜底；`..` / 盘符 / 绝对路径被拒 | `test_boundary.py` |
| B5 | 快速连点重播 | 连点 20 次仍回到 IDLE，计数表不残留 | `test_perf.js` |
| B6 | 坏缓存文件 | 0 字节 / 半截 PNG / 坏 JSON → 删掉重生成 | `test_cache_io.py` |
| B7 | 坏场景目录 | `cg/index.json` 不是 JSON → 空目录，不抛 | `test_boundary.py` |
| B8 | 前端拆分不退化 | `check_split.py` 告警数 ≤ 基线（现在 91），**只许降不许升** | `run_smoke.py`（静态） |
| B9 | 语法门禁 | 后端 36 个 `.py`、前端 44 个 js/css 都能解析 | `test_py_syntax.py` / `test_ui_syntax.js` |
| B10 | 日志过期清理 | 超过保留天数的日志删掉、正在写的那个不删、崩溃现场只留 10 份 | `test_logpack.py` |
| B11 | 像素测量 | 合成图（已知行距 / 首峰 / 槽位宽 / 宽高比）：+2px 平移判「只有平移」、放大 2% 判形变、黑边裁掉、噪声图不硬给数 | `test_measure_ui.py` |

## 降级（依赖不可用时还能继续玩）

| 编号 | 场景 | 期望 | 自动化 |
|---|---|---|---|
| D1 | 语音没有参考音频 | 不合成、返回 None，界面只显示文字 | `test_degrade.py` |
| D2 | 语音服务没就绪 | 立刻返回 None，不抛、不卡住那一步 | `test_degrade.py` |
| D3 | 响度算不出来 | 坏 wav / 未知格式原样放行（增益 0） | `test_degrade.py` |
| D4 | 场景匹配失败 | `match` 返回 `{}`，背景不动，日志记一句 | `test_degrade.py` |
| D5 | 原作检索不可用 | 没索引 / 角色关了检索 → 注入空串 | `test_degrade.py` |
| D6 | 关系判定超时 / 返回怪东西 | 保留原阶段、轮数照记，下一轮还能再判 | `test_degrade.py` |
| D7 | 云端连不上 | 返回错误文案，界面不崩、输入框恢复 | 手动（断网发一句） |
| D8 | 音频设备被拔 | 暂停 → 重建 → 续播；续不上提示重播 | 手动（#7） |

## 发版前手动过一遍

1. `program\启动程序.bat`：标题栏、背景、立绘、字模、按钮音效、窗口按钮
2. 语音真出声（要 GPT-SoVITS）：一句日文，响度归一化后不炸、不削波
3. 存档缩略图；读档后时期 / 衣服 / 场景对不对
4. 拔耳机 / 切蓝牙：BGM 和语音能续上
5. 菜单关掉「演出过渡」再看换背景：应该是硬切，不再有淡入
6. 切角色：压黑 → 换人 → 淡回，期间点不动

## 加用例的规矩

- 只测**会坏的地方**：解析、预算、降级、安全边界；不测样式像素（那交给 `ui_probe`）
- 必须能**离线跑**：不联网、不开窗口、不读本地角色数据（要数据就自己造临时目录）
- 有随机/时间因素的用例，断言写「关系」不写「绝对值」（比如 ≥ / ≤ / 单调）
