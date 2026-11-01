# 素材与第三方内容归属说明 / Notice on Third-Party Assets

**本文件不属于许可证的一部分，只说明版权归属与责任边界。**

[MIT License](LICENSE) 仅覆盖本仓库内的**源代码与文档**。

## 一、本仓库不包含、不分发的东西

| 类别 | 归属 | 是否在仓库中 |
|---|---|---|
| 《WHITE ALBUM 2》角色、剧本、台词 | Leaf / Aquaplus | ❌ 不包含 |
| 立绘、CG、UI 图集、背景图 | Leaf / Aquaplus | ❌ 不包含 |
| 语音、BGM、音效 | Leaf / Aquaplus | ❌ 不包含 |
| 汉化补丁的字体图集与字形映射 | 汉化组 | ❌ 不包含 |
| `Touma_Kazusa` GPT-SoVITS 音色权重 | 该权重的训练者 | ❌ 不包含、不转存、不镜像 |
| 翻译模型（Hy-MT2 等） | 模型作者 | ❌ 不包含 |
| 游戏本体 | Leaf / Aquaplus | ❌ 不包含 |

## 二、语音模型的边界（重要）

- 本项目使用的**和纱音色 TTS 权重（`Touma_Kazusa`）不是本项目训练的**，
  是第三方作者训练并公开分享的权重。
- 本项目在该环节**只做调用方**：把文本发给本地的 GPT-SoVITS 服务，取回音频播放。
- 本项目**不提供该权重的下载**，不转存、不镜像、不二次分发。
- 该权重的训练、来源、使用范围与授权问题，均由该权重的训练者与使用者各自负责，
  与本项目无关。

## 三、本项目的义务声明

- **不提供绕过版权保护的任何手段**：仓库中不含解密、反调试、DRM 绕过相关内容
- **不提供素材下载**：运行所需素材需用户自行从正版游戏中提取
- **非商业**：本项目不销售、不接受付费分发
- **可下架承诺**：若权利方认为本项目的任何部分不妥，通过 issue 联系后会立即处理

## 四、MIT 许可证覆盖范围

MIT 覆盖：`program/src/` 下的源代码、`program/tools/` 下的脚本、`other/docs/` 下的文档、根目录文档。

MIT **不覆盖**：上表列出的任何第三方内容（它们不在本仓库中）。

---

# Notice on Third-Party Assets

**This file is not part of the license.** It only clarifies copyright ownership and responsibility boundaries.

The MIT License covers the **source code and documentation** in this repository.

Not included, not distributed:

- All characters, script, dialogue, sprites, CGs, UI atlases, backgrounds, voice, BGM, SFX
  from *WHITE ALBUM 2* — copyright **Leaf / Aquaplus**
- The fan-translation font atlas and glyph mapping — copyright its authors
- The `Touma_Kazusa` GPT-SoVITS voice weights — **trained by a third party, not by this project**.
  This project only *calls* a local TTS service; it does not host, mirror, or redistribute
  those weights.
- Translation models (Hy-MT2 etc.)
- The game itself

This project does not provide any means to bypass copy protection, does not distribute
game assets, and is non-commercial.
