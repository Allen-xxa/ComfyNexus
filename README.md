<div align="center">

<img src="banner.png" alt="ComfyNexus">

<h1>ComfyNexus</h1>

<p><strong>为专业创作者而生的 ComfyUI 现代化管理平台</strong></p>

<p>
  <a href="https://github.com/Allen-xxa/ComfyNexus/releases">
    <img src="https://img.shields.io/github/v/release/Allen-xxa/ComfyNexus?style=flat-square&color=3b82f6" alt="Version">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-green?style=flat-square" alt="License">
  </a>
  <a href="https://www.microsoft.com/windows">
    <img src="https://img.shields.io/badge/platform-Windows-6366f1?style=flat-square" alt="Platform">
  </a>
  <a href="https://github.com/Allen-xxa/ComfyNexus/releases">
    <img src="https://img.shields.io/github/downloads/Allen-xxa/ComfyNexus/total?style=flat-square&color=f59e0b" alt="Downloads">
  </a>
</p>

<p>
  <a href="#-核心亮点">核心亮点</a> •
  <a href="#-功能全景">功能全景</a> •
  <a href="#-快速开始">快速开始</a> •
  <a href="#-常见问题">常见问题</a>
</p>

<!-- 录屏演示位置：将下方图片链接替换为你的 GIF 演示视频 -->
<img src="demo.gif" alt="Demo" width="800">

</div>

---

## ✨ 核心亮点

> **ComfyNexus** 不仅仅是一个启动器，它是 ComfyUI 生态的"手术刀"与"盾牌"。

- 🚀 **一站式治理** — 深度整合环境、版本、插件、模型、工作流，彻底告别繁琐的命令行与文件夹反复跳转
- ⚡ **极客式调优** — 内置 Flux 标准、旗舰画质等多种加速预设，支持多行参数编辑，满足极致性能追求
- 🛡️ **救援级保护** — 智能进程冲突检测 + 环境快照系统，让你的环境拥有"后悔药"，随时回滚
- 🎨 **现代化交互** — 基于 React 19 构建，毫秒级响应，支持沉浸式全屏创作、深色模式与国际化

---

## 🚀 功能全景

### 🏠 首页

- **ComfyUI 状态卡片** — 实时显示运行状态、运行时间、端口占用、Python/PyTorch 版本
- **文件夹快捷栏** — 内置常用目录入口，支持自定义收藏
- **创作者推荐** — 精选 ComfyUI 生态优质创作者与资源

### 🖥️ 工作台

- **WebView 原生体验** — 在应用内直接操作 ComfyUI 界面
- **全屏模式** — 一键进入沉浸式全屏，标题栏自动隐藏
- **智能图片下载** — 右键保存图片，自动记忆路径

### 📟 实时终端

- **日志实时推送** — ComfyUI 进程输出实时同步
- **Traceback 智能识别** — 自动捕获 Python 异常堆栈，高亮显示

### 🔄 核心版本管理

- **稳定版/开发版切换** — 自由切换 ComfyUI 版本
- **分支管理** — 一键切换分支或回退到指定提交
- **Git 权限修复** — 一键检测并修复 Git 仓库权限问题

### 🧩 插件管理

- **已安装插件一览** — 展示名称、分支、版本、更新状态
- **一键更新** — 单个或批量更新，更新前自动备份
- **分支切换** — 在不同分支间自由切换
- **启用/禁用** — 快速启用或禁用插件，无需删除
- **依赖变化追踪** — 自动检测依赖变化，标记未查看的更新

### 🏪 插件市场

- **列表缓存与后台预取** — 首次拉取后本地缓存，重复打开不再每次联网（具体加载耗时未做过基准测试，不承诺数值指标）
- **一键安装** — 从 GitHub 仓库一键安装插件
- **安装前依赖检查** — 自动检测依赖冲突，提前预警
- **推荐插件** — 精选优质插件推荐列表

### 📦 依赖管理

- **依赖树可视化** — 以树形结构展示所有 Python 依赖
- **冲突检测** — 自动检测版本冲突，高亮标记严重程度
- **缺失依赖一键安装** — 支持国内 PyPI 镜像源加速

### 🛟 救援模式

- **环境快照备份** — 一键创建快照，可选择备份范围
- **智能回滚** — 一键恢复到任意历史快照
- **进程安全检查** — 回滚前自动检测 ComfyUI 运行状态

### 🎨 LoRA 管理

- **模型自动扫描** — 自动识别模型文件与格式
- **Civitai 深度同步** — 自动抓取模型元数据、预览图及触发词
- **智能分类** — 按 FLUX/SDXL/SD1.5 等架构自动归档

### 🤖 AI 助手

- **多模型对接** — 内置 OpenAI、xflow、iFlow、自定义 OpenAI 兼容服务、讯飞星火、火山引擎、智谱 GLM、Ollama 本地模型等接入方式；Claude 需通过兼容 OpenAI 接口的中转服务接入
- **联网搜索** — AI 可实时检索互联网信息（DuckDuckGo 默认可用；Google、Tavily 需在设置中填入密钥后启用）
- **深度思考模式** — 通过追加引导提示让模型展开更深入的推理分析
- **文件与图片分析** — 上传文档或图片，AI 直接分析
- **报错日志分析** — AI 识别错误根源并提供修复步骤
- **话题管理** — 支持新建、切换与重命名对话话题，并可按首条消息自动生成标题

### 🔗 工作流管理

- **工作流导入解析** — 导入 JSON 文件，自动解析节点与连接
- **插件依赖检测** — 自动识别工作流所需的第三方插件
- **缺失插件一键安装** — 一键批量安装缺失插件

### 📝 提示词管理

- **提示词库** — 创建和管理常用提示词模板
- **分类树结构** — 以树形结构组织，支持多级分类

### 🖼️ 资产库

- **输出图片浏览** — 瀑布流展示生成作品
- **层级整理** — 分类与资产库中的本地文件夹一一对应，归类即移动文件；侧边栏按层级浏览与面包屑回溯
- **NSFW 过滤** — 内置 ONNX 模型自动识别
- **批量操作** — 支持批量选择、删除、移动、分类

### 📊 监控中心

- **CPU/GPU 监控** — 实时追踪温度、使用率、功耗
- **内存/磁盘监控** — 实时显示使用量与剩余空间
- **网络监控** — 实时显示上传/下载速率

### 🌐 环境管理

- **多环境支持** — 创建和管理多个 ComfyUI 环境
- **性能预设** — 内置 Flux 标准、旗舰画质、老显卡救星等预设
- **自定义参数** — 支持多行参数编辑

### ⚙️ 系统设置

- **GitHub/PyPI 镜像加速** — 解决国内网络访问问题
- **代理设置** — 支持 Git、pip、AI 请求等全链路代理
- **模块管理** — 自定义启用/禁用功能模块，侧边栏支持拖拽排序
- **更新检查** — 默认关闭，当前设置界面未提供"应用自动更新"开关（插件更新另有开关），不会在后台自动拉取或替换程序

---

## 📥 快速开始

### 系统要求

| 项目 | 要求 |
|:---|:---|
| 操作系统 | Windows 10/11 |
| Git | 无需预先安装：首次启动会引导你下载便携版 MinGit 或指定已有 Git |
| Python | 应用本体绿色免安装（运行环境已内置）；你托管的 ComfyUI 需要自己的 Python 环境，应用会检测并显示其版本 |
| GPU | NVIDIA（CUDA 支持） |

### 安装步骤

1. **下载** 最新 [Releases](https://github.com/Allen-xxa/ComfyNexus/releases) 压缩包
2. **解压** 即可使用（绿色免安装）
3. **启动** 运行 `ComfyNexus.exe`，首次启动选择你的 ComfyUI 根目录

---

## ❓ 常见问题

<details>
<summary><b>需要手动安装 Git 吗？</b></summary>

**不需要预先安装**。首次启动时 ComfyNexus 会进入引导流程：自动下载便携版 MinGit（当前版本 2.53.0.2），或者直接指定你电脑上已有的 Git，之后所有版本控制操作都走它。
</details>

<details>
<summary><b>支持多开吗？</b></summary>

**支持**。你可以在环境设置里添加多个环境并分配不同端口（如 8188, 8189），实现多实例并行运行。
</details>

<details>
<summary><b>AI 助手支持哪些模型？</b></summary>

接入方式包括 xflow API 聚合平台（推荐，模型全且价格低）、OpenAI、iFlow、任意兼容 OpenAI 接口的自定义服务、智谱 GLM、讯飞星火、火山引擎，以及 Ollama 本地模型。
Claude 系列没有原生接入方式，需要通过兼容 OpenAI 接口的中转服务（例如聚合平台）配置。
Ollama 本地模型采用分阶段超时策略：允许模型按需冷加载，生成过程中只在长时间无新内容时中断。
</details>

<details>
<summary><b>插件列表一直加载中？</b></summary>

请在设置中配置 **GitHub Token**。这能让 API 访问上限从 60 次/小时 提升至 5000 次/小时。
</details>

<details>
<summary><b>国内网络访问 GitHub 太慢怎么办？</b></summary>

在系统设置中配置 **GitHub 镜像加速** 和 **PyPI 镜像源**，支持多镜像源自动 fallback。
</details>

---

<div align="center">



</div>

---

**Last verified**: 2026-11-01（本文件为产品功能介绍的唯一来源；条目均对照实际代码/脚本核实，维护规则见 `source-code/README更新规范.md`）
