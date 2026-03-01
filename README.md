<div align="center">

<img src="icon.png" alt="ComfyNexus Logo" width="160">

# ComfyNexus
### 为专业创作者而生的 ComfyUI 现代化管理平台

**“ 摆脱命令行束缚，让每一份灵感都能在稳定的环境中平稳着陆 ”**

[![Version](https://img.shields.io/badge/version-RC_0.7.0-3b82f6?style=for-the-badge)](VERSION)
[![License](https://img.shields.io/badge/license-MIT-10b981?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-6366f1?style=for-the-badge)](https://www.microsoft.com/windows)
[![Downloads](https://img.shields.io/github/downloads/Allen-xxa/ComfyNexus/total?style=for-the-badge&color=f59e0b)](https://github.com/Allen-xxa/ComfyNexus/releases)

[✨ 核心亮点](#-核心亮点) · [🚀 功能全景](#-功能全景) · [📂 场景化指南](#-场景化指南) · [❓ 常见问题](#-常见问题)

</div>

---

## ✨ 核心亮点：为什么选择我们？

> **ComfyNexus** 不仅仅是一个启动器，它是 ComfyUI 生态的“手术刀”与“盾牌”。

| | 优势说明 |
| :--- | :--- |
| **🚀 一站式治理** | 深度整合环境、版本、插件、模型，彻底告别繁琐的命令行与文件夹反复跳转。 |
| **⚡ 极客式调优** | 内置 Flux 标准、旗舰画质等多种加速预设，支持多行参数编辑，满足极致性能追求。 |
| **🛡️ 救援级保护** | 智能进程冲突检测 + 环境快照系统，让你的环境拥有“后悔药”，随时回滚。 |
| **🎨 现代化交互** | 基于 React 19 构建，毫秒级响应，支持沉浸式全屏创作与深色模式。 |

---

## 🚀 功能全景

### 🏠 首页：全状态看板
* **硬件监控**：实时追踪 CPU/内存/磁盘及 **NVIDIA GPU** 显存与温度，预防过载。
* **一键掌控**：实时显示 Python/PyTorch 版本、运行时间及端口状态。
* **快捷导航**：内置常用文件夹入口，支持自定义收藏，创作路径缩短至一次点击。

### 🖥️ 工作台：沉浸式创作
* **WebView 原生体验**：在应用内直接操作 ComfyUI，支持全屏模式与标题栏自动隐藏。
* **智能下载管理**：右键保存图片，自动记忆路径，支持 PNG/WebP 等全格式。
* **运行状态感知**：未启动时自动显示新手引导，消除“黑屏”焦虑。

### 🧩 插件与依赖：告别“红字”报错
* **三级缓存市场**：首屏加载 <100ms，支持从 GitHub 一键安装与批量更新。
* **依赖可视化分析**：依赖树高亮标记冲突，一键安装缺失包，支持国内镜像源加速。
* **环境救援模式**：**快照级备份**。在更新插件前一键存档，出问题一键读档。

### 🎨 LoRA 管理：私人模型金库
* **Civitai 深度同步**：自动抓取模型元数据、预览图及触发词，点击即可复制。
* **智能自动分类**：按 FLUX/SDXL/SD1.5 自动归档，支持重命名与自定义标签。

### 🤖 AI 助手：你的 7x24 专家
* **报错日志分析**：自动读取实时终端日志，AI 识别错误根源并提供修复步骤。
* **多模型对接**：支持 GPT-4、Claude 及本地部署模型，支持联网搜索与文件分析。

---

## 🎯 场景化指南

<details>
<summary><b>🟢 场景一：新手第一次运行 ComfyUI</b></summary>
使用 <b>扫描环境</b> 自动识别路径 -> 选择 <b>Flux 标准</b> 性能预设 -> 点击 <b>启动</b>。剩下的交给 ComfyNexus。
</details>

<details>
<summary><b>🔴 场景二：插件更新后 ComfyUI 无法启动</b></summary>
打开 <b>实时终端</b> 复制报错 -> 询问 <b>AI 助手</b>。如果无法修复，进入 <b>救援模式</b> 还原昨天的环境快照。
</details>

<details>
<summary><b>🔵 场景三：老旧显存经常 OOM (溢出)</b></summary>
在 <b>环境设置</b> 中切换至 <b>“老显卡救星”</b> 模式，应用会自动配置低显存优化参数。
</details>

---

## 📥 快速开始

### 系统要求
* **OS**: Windows 10/11 (已内置 MinGit 2.53.0)
* **Python**: 3.12+ ｜ **GPU**: NVIDIA (CUDA 支持)

### 极速安装
1. **下载** 最新 [Releases](https://github.com/Allen-xxa/ComfyNexus/releases) 压缩包。
2. **解压** 即可使用（绿色免安装）。
3. **配置** 首次启动选择你的 ComfyUI 根目录。

---

## ❓ 常见问题 (FAQ)

* **Q: 需要手动安装 Git 吗？**
    * A: **完全不需要**。内置 MinGit 处理所有版本控制任务。
* **Q: 支持多开吗？**
    * A: **支持**。你可以在环境设置里添加多个环境并分配不同端口（如 8188, 8189）。
* **Q: 插件列表一直加载中？**
    * A: 请在设置中配置 **GitHub Token**。这能让 API 访问上限从 60次/小时 提升至 5000次/小时。

---

<div align="center">

### 🤝 参与贡献
欢迎提交 [Issue](https://github.com/Allen-xxa/ComfyNexus/issues) 或 [Pull Request](https://github.com/Allen-xxa/ComfyNexus/pulls) 帮助我们做得更好。

**Made with ❤️ by ComfyNexus Team**

[⬆ 返回顶部](#comfynexus)

</div>

