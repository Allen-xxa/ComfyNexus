<div align="center">

<img src="icon.png" alt="ComfyNexus Logo" width="120" height="120">

# ComfyNexus

**ComfyUI 的现代化启动器和管理工具**

一站式 ComfyUI 管理平台，让 AI 创作更简单、更高效

[![Version](https://img.shields.io/badge/version-RC_0.7.0-blue.svg)](VERSION)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

[功能特性](#-功能特性) • [快速开始](#-快速开始) • [常见问题](#-常见问题)

</div>

---

## ✨ 为什么选择 ComfyNexus？

| 🎯 一站式管理 | ⚡ 智能优化 | 🛡️ 智能保护 | 🎨 现代界面 |
|:---:|:---:|:---:|:---:|
| 环境、版本、插件，一个应用全搞定 | 内置多种性能预设，极客模式支持自定义参数 | 自动检测进程冲突，防止端口占用和启动失败 | 精美的深色主题，流畅的交互体验 |

---

## 🚀 功能特性

### 🏠 首页 — 控制中心

一目了然掌握所有信息，快速启动创作之旅。

- 📊 **实时监控** — CPU、内存、磁盘、GPU 使用率
- 🎮 **一键启动** — 快速启动/停止 ComfyUI
- 🌟 **创作者推荐** — 精选优质创作者和资源

---

### 🖥️ 工作台 — 无缝创作

在应用内直接使用 ComfyUI，无需切换窗口。

- 🔗 **内嵌界面** — ComfyUI 无缝集成
- 🖼️ **图片下载** — 右键保存，自动记忆路径
- 📺 **全屏模式** — 沉浸式创作体验

---

### 🧩 插件管理 — 轻松扩展

管理已安装的 ComfyUI 插件，保持插件最新。

- 📦 **插件市场** — 发现和安装优质插件
- 🔄 **一键更新** — 单个或批量更新
- 🌿 **分支切换** — 灵活切换版本分支
- ⚡ **极速加载** — 首屏 < 100ms，三级缓存架构

---

### 📦 依赖管理 — 环境无忧

一站式管理 ComfyUI 环境的 Python 包。

- 🔧 **PyTorch 安装** — 自动检测 CUDA 版本
- 📋 **依赖扫描** — 自动检测核心和插件依赖
- ⚠️ **冲突分析** — 可视化依赖树，快速定位问题
- 💾 **救援模式** — 环境快照创建和恢复

---

### ⚙️ 环境设置 — 灵活配置

管理 ComfyUI 环境配置，支持多环境切换。

- 🗂️ **多环境管理** — 添加、删除、快速切换
- 🚀 **加速配置** — 内置预设（Flux 标准、旗舰画质、老显卡救星）
- 🔮 **极客模式** — 高级用户自定义启动参数
- 📁 **模型路径** — Checkpoint、LoRA、VAE 等路径配置

---

### 🎨 LoRA 管理 — 模型库管家

一站式管理您的 LoRA 模型库。

- 📂 **自动分类** — 按 FLUX、SDXL、SD1.5 分类浏览
- 🌐 **Civitai 集成** — 自动获取元数据和预览图
- 📋 **触发词复制** — 一键复制触发词
- 🏷️ **自定义标签** — 灵活管理模型信息

---

### 🔧 核心管理 — 版本控制

ComfyUI 核心版本管理，轻松切换和更新。

- 📌 **版本切换** — 稳定版/开发版一键切换
- 🌿 **分支管理** — 支持切换 Git 分支
- 📜 **版本历史** — 浏览所有可用版本

---

### 🤖 AI 助手 — 智能对话

智能对话助手，支持多模型配置管理。

- 🎛️ **多模型支持** — OpenAI、Claude、本地模型等
- 💬 **对话级配置** — 每个对话独立选择模型
- 🔍 **联网搜索** — 支持联网获取信息

---

### 🛡️ 进程保护 — 智能检测

智能检测和处理 ComfyUI 进程冲突。

- 🔍 **自动扫描** — 启动前检测冲突进程
- 🎯 **精准识别** — 端口冲突检测
- 🧹 **一键清理** — 结束僵尸进程

---

## 📥 快速开始

### 系统要求

- **操作系统**: Windows 7 或更高版本
- **Python**: 3.12 或更高版本
- **显卡**: 支持 NVIDIA GPU（推荐）

### 安装步骤

1. **下载** — 从 [Releases](https://github.com/your-repo/ComfyNexus/releases) 下载最新版本
2. **解压** — 解压到任意目录
3. **运行** — 双击 `ComfyNexus.exe` 启动
4. **配置** — 首次启动时设置 ComfyUI 路径

> 💡 **提示**: ComfyNexus 内置 MinGit，无需单独安装 Git

---

## 🎯 使用场景

<details>
<summary><b>新手入门</b></summary>

1. 打开 ComfyNexus，进入「环境设置」
2. 点击「扫描环境」，自动识别已安装的 ComfyUI
3. 选择一个环境，应用内置的「Flux 标准」预设
4. 返回首页，点击「启动 ComfyUI」
5. 进入「工作台」，开始创作

</details>

<details>
<summary><b>多环境管理</b></summary>

1. 在「环境设置」中添加多个环境
2. 为每个环境设置不同的别名和端口
3. 在顶部导航栏快速切换环境
4. 每个环境的配置独立保存

</details>

<details>
<summary><b>性能优化</b></summary>

1. 进入「环境设置」→「加速配置」
2. 根据显卡性能选择合适的预设：
   - **高端显卡** (RTX 4090/4080) → 旗舰画质
   - **中端显卡** (RTX 3060/4060) → Flux 标准
   - **低端显卡** (GTX 1660/2060) → 老显卡救星
3. 高级用户可切换到极客模式自定义参数

</details>

---

## ❓ 常见问题

<details>
<summary><b>需要安装 Git 吗？</b></summary>

**不需要**。ComfyNexus 内置了 MinGit 2.53.0，无需单独安装 Git。

</details>

<details>
<summary><b>可以同时运行多个环境吗？</b></summary>

**可以**，但需要为每个环境配置不同的端口。

</details>

<details>
<summary><b>切换版本会影响已有的工作流吗？</b></summary>

**一般不会**，但建议在切换前备份重要的工作流文件。

</details>

<details>
<summary><b>如何安装插件？</b></summary>

进入「插件市场」，搜索想要的插件，点击「安装」按钮即可。

</details>

<details>
<summary><b>GitHub API 请求限制怎么办？</b></summary>

在「系统设置」中配置 GitHub Personal Access Token，请求限制从 60次/小时 提升到 5000次/小时。

</details>

---

## 🤝 参与贡献

ComfyNexus 是一个开源项目，欢迎您的参与！

- 🐛 [报告 Bug](https://github.com/your-repo/ComfyNexus/issues)
- 💡 [提出建议](https://github.com/your-repo/ComfyNexus/issues)
- 🌍 翻译界面
- 💻 提交代码

---

## 📄 开源协议

本项目采用 [MIT 许可证](LICENSE)。

---

## 💖 致谢

感谢以下项目的支持：

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) — 强大的 Stable Diffusion GUI
- [pywebview](https://pywebview.flowrl.com/) — 轻量级 WebView 容器
- [React](https://react.dev/) — 用户界面库
- [Tailwind CSS](https://tailwindcss.com/) — CSS 框架
- [Shadcn/ui](https://ui.shadcn.com/) — UI 组件库

---

<div align="center">

**让 AI 创作更简单**

Made with ❤️ by ComfyNexus Team

[⬆ 返回顶部](#comfynexus)

</div>

