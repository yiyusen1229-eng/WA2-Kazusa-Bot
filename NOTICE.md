# 第三方内容说明 / Notice on Third-Party Content

**本文件不属于许可证的一部分。**

[MIT License](LICENSE) 覆盖本仓库内的**源代码与文档**。

## 一、仓库里没有素材

本仓库**只包含代码与文档**，不包含、不分发：

| 类别 | 是否在仓库 | 说明 |
|---|---|---|
| 图片、立绘、CG、背景、图标 | ❌ | 由使用者自行接入 |
| 音频、语音、BGM、音效 | ❌ | 由使用者自行接入 |
| 字体、字模图集 | ❌ | 由使用者自行接入 |
| 模型权重（对话 / 翻译 / 语音） | ❌ | 全部通过外部服务或本地目录调用 |
| 任何作品的角色、剧本、台词 | ❌ | 仓库不含任何作品内容 |

## 二、责任边界

- 本项目是**界面框架**：它只定义「资源怎么放、文字怎么渲染、窗口怎么控制、接口怎么调」。
- **放什么资源进这个框架，是使用者自己的选择和行为。**
- 资源从哪来、是否有权使用、是否符合当地法律与软件许可，**由使用者自行负责**。
- 本项目不提供素材下载、不提供素材获取手段、不推荐任何具体的素材来源。

## 三、模型与外部服务

| 组件 | 性质 |
|---|---|
| 对话模型 | 通过 OpenAI 兼容接口调用，模型由使用者自行选择与配置 |
| 翻译模型 | 同上，可选；不配置则不做翻译 |
| TTS | 需提供 `文本 → wav` 的本地或远程服务；权重与音色由使用者自行准备 |

本项目**不训练模型**，仓库不含任何权重，也不转让或托管他人权重。

## 四、兼容与下架

若权利方认为本项目的任何部分不妥（包括文档中的任何示例描述），
请通过 issue 联系，会立即调整或移除相关部分。

---

# Notice on Third-Party Content

**This file is not part of the license.** The MIT License covers the **source code and
documentation** in this repository.

This repository contains **code and documentation only**. It does not include or distribute
any images, audio, fonts, model weights, or content from any work.

This project is a **UI framework**: it defines how resources are loaded, how text is rendered,
how the window is controlled, and how services are called. What resources a user places into
it — and whether they have the right to use them — is entirely the user's responsibility.

This project does not train models, does not host weights, and does not provide or point to
any source of third-party assets.
