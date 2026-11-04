# ComfyNexus 现状架构（Container 级）

**受众**：项目维护者，以及接手 Phase 1 执行方案的 agent。
**目的**：给整改项一个可定位的落点，避免「安全问题」停留在文字描述层面。
**视图状态**：全部为 **current-state**，无目标态、无建议。
**图源**：`current-architecture.structurizr.dsl`（本文件是它的说明，不是事实来源）。

## 阅读顺序

1. `Landscape` — ComfyNexus 与它托管/依赖的外部系统各有几个。
2. `SystemContext` — 用户与外部系统如何跨过产品边界。
3. `Containers` — **本文件重点**：一个 Python 进程内部的责任单元与信任边界。

用 Qoder 的 Structurizr DSL 查看器打开 `.structurizr.dsl` 即可看三个视图；查看器只做预览，DSL 源文件为准。

## 一句话架构

Windows 绿色免安装桌面应用：**单个 Python 进程**（`main.py:378`）用 pywebview/WebView2 开窗口，窗口里加载**本机回环 Flask 服务**托管的 React SPA，SPA 的业务调用**不走 HTTP**，而是走 pywebview 的 `window.pywebview.api` 内联桥；被托管的 ComfyUI 是**另一个独立进程**。

## 五个结构性事实

### 1. 进程边界只有两个（外加更新器）

- `ComfyNexus.exe`：一个 Python 进程持有桌面壳、Flask 线程、桥、领域服务、各类后台线程（`main.py:597-598, 805-817, 1203`）。
- `ComfyUI`：由 `comfyui_process.py:362` 以 `subprocess.Popen` 启动的独立进程，默认 `127.0.0.1:8188`（`comfyui_process.py:40`）。
- `ComfyNexusUpdater_v1.0.exe`：onefile 独立进程，仅在更新时被拉起（`update_controller.py:258-286`）。

意义：不存在「前端直连后端 API」的微服务拓扑；把安全面想成「HTTP 服务面」会漏掉真正的通道（桥）。

### 2. 两条通信通道，信任属性完全不同

| 通道 | 协议 | 暴露范围 | 鉴权 |
|:---|:---|:---|:---|
| SPA → 桥（389 方法） | `window.pywebview.api`，WebView2 内联 | 仅窗口内 JS | 无（依赖「页面是我自己加载的」这一前提） |
| SPA/任意来源 → 回环服务 | HTTP，`127.0.0.1:{5000 起自动探测}` | 本机任意进程 + 任意浏览器页面 | 无 |

回环服务只托管静态文件与媒体预览（`http_server.py:97-279` 的 8 组路由），**不含业务 API**。这一点决定了它的影响面是「读文件」而不是「调用能力」。

### 3. 桥是事实上的信任边界

`src/bridge/api.py` 是 7705 行、389 个方法的单一门面（实测 `wc -l` 与 `grep -c "def "`），聚合 11 个控制器（`src/bridge/controllers/`，实测文件数）。其中存在接收任意文件路径或 URL 的方法（如 `api.py:2367` 写 `model_paths.yaml`、`api.py:2717` 按路径读日志、`api.py:3262` 打开任意目录）。这些能力**只对窗口内 JS 开放**，因此它们本身不是远程入口，而是「一旦前端被注入即等于本机文件操作」的放大面。

### 4. 数据落在三类位置

- SQLite `data/ai_assistant.db`（`src/core/ai/database.py:15`）——会话与 AI 配置，`api_key` 以 `encrypted:` 前缀存 Fernet 密文。
- 明文 JSON 配置 `backend/config`（开发）/ `exe 同级 config`（打包）（`src/utils/paths.py:166-197`）——`autoUpdate` 默认 `false`（`settings_manager.py:47`）。
- 本机密钥文件 `data/secrets/ai_fernet.key`（`secret_store.py:44, 62`）——首用生成、原子写、`icacls /inheritance:r` 只授权当前用户（`secret_store.py:71-116`），已被 `source-code/.gitignore:16` 的 `data/` 覆盖。
  **注意状态**：`secret_store.py` 是**未提交的新文件**，不在基线 `88bdb15` 中。HEAD 上加密密钥写死在 `config_manager.py:23`，所谓「按机器密钥」在基线上尚不存在（详见 `risk-register.md` R-12）。

### 5. 后台并发是常驻线程，不是进程池

Flask 服务线程（`http_server.py:289-301`）、插件市场后台预取（`main.py:640-647`）、监控采集 1s 轮询（`monitor_collector.py:47, 58, 155`）、WebView 健康检查与窗口重置线程（`main.py:1088, 1179`）、ComfyUI 日志读取线程。全部与主进程同生共死，无独立伸缩单元。

## 外部依赖清单

ComfyUI（托管）、AI 服务商 API、GitHub（raw `version.json` / Release 资源 / 插件仓库 / API）、PyPI 及镜像、Civitai、搜索引擎（DuckDuckGo 默认可用，Google/Tavily 需密钥，`README.md:110`）。

## 假设与未知

| 项 | 状态 | 说明 |
|:---|:---|:---|
| 后端以 HTTP/WebSocket 主动调用 ComfyUI 控制面 | **未找到证据** | 代码里只有进程启动、端口探活（`comfyui_process.py:537` 类调用）、日志读取；`ws://` 仅出现在讯飞星火 provider。故模型未画该边，**不要**据此假设存在 ComfyUI API 客户端 |
| 前端 iframe 直连 ComfyUI | **high** | `WorkspaceFrame.tsx:6, 35, 190-193` 明确跨域 iframe + `postMessage` |
| 打包产物的最终文件布局 | **medium** | 依 `.spec` 与 `main.py:548-556` 路径回落逻辑推得，未实机跑完整构建验证 |
| `dist` 内 SPA 与 `_MEIPASS` 的实际解析优先级 | **medium** | `main.py:548-556` 三档回落，未逐一执行 |
| AI provider 各自的协议细节 | **medium** | 依目录结构 + `README.md:109`，未逐个 provider 读实现 |

## 局限

视图停在 Container 级。`src/core/` 下 20+ 子包被归并成一个「领域服务层」容器——这是**有意的抽象选择**，不是遗漏：Phase 1 整改的落点全部能在 Container 级定位，下钻只会增加维护成本。若某条整改项需要组件级定位，应单独为该子包出 L3 视图。
