// ComfyNexus 现状架构基线（C4 Container 级）
// 生成日期: 2026-11-01 · 分支: fix/security-hardening @ 88bdb15
// 证据规则: 每个元素/关系的 properties 带 sourceRefs 与 confidence。
//   confidence=high 直接代码/配置证据；medium 多处信号一致但无直接确认；low 由命名或目录结构推断。
//   本文件是事实来源；渲染图与 Markdown 均为其派生说明。
// 状态规则: properties 里的 state 区分 committed 与 uncommitted。
//   基线 88bdb15 与工作区在会话期间发生分叉（密钥存储改造在途未提交），
//   凡 state 含 "uncommitted" 的元素只描述工作区，不代表基线已具备该能力。

workspace "ComfyNexus" "ComfyUI 本地管理平台 · 现状架构基线（Container 级）" {

  model {

    user = person "ComfyUI 创作者" "在 Windows 上使用 ComfyNexus 托管并调优本地 ComfyUI" {
      location "Local"
    }

    comfyui = softwareSystem "ComfyUI" "被托管的独立 Python 应用，默认监听 127.0.0.1:8188" {
      tags "ExternalSystem"
      properties {
        state "current"
        confidence "high"
        sourceRefs "source-code/backend/src/core/process/comfyui_process.py:40"
      }
    }

    aiProviders = softwareSystem "AI 服务商 API" "OpenAI / Ollama / 讯飞星火 / 火山引擎 / 智谱GLM / iFlow / xflow 等，OpenAI 兼容协议" {
      tags "ExternalSystem"
      properties { state "current" confidence "high" sourceRefs "README.md:109" }
    }

    github = softwareSystem "GitHub" "插件仓库、Release 资源、raw version.json、GitHub API（Token 提升配额）" {
      tags "ExternalSystem"
      properties { state "current" confidence "high" sourceRefs "source-code/backend/src/core/updater/update_checker.py:16" }
    }

    pypi = softwareSystem "PyPI 及镜像源" "依赖安装与缺失依赖修复，支持国内镜像 fallback" {
      tags "ExternalSystem"
      properties { state "current" confidence "medium" sourceRefs "README.md:93" }
    }

    civitai = softwareSystem "Civitai" "LoRA 模型元数据、预览图与触发词来源" {
      tags "ExternalSystem"
      properties { state "current" confidence "medium" sourceRefs "README.md:104" }
    }

    nexus = softwareSystem "ComfyNexus" "绿色免安装的 Windows 桌面应用（PyInstaller onedir）" {

      shell = container "桌面壳进程" "单实例互斥 + 预检 + 创建窗口 + 启动各后台线程；一个 Python 进程持有除 ComfyUI 外的一切" "Python 3.12 / pywebview / WebView2(EdgeChromium)" {
        tags "OwnProcess"
        properties {
          state "current"
          confidence "high"
          sourceRefs "source-code/backend/main.py:378, 597-598, 805-817, 1203"
        }
      }

      spa = container "前端 SPA" "React 19 双入口（主窗口 + 浮动窗口），经 pywebview 桥调用后端；构建产物 dist 由回环 HTTP 服务提供" "TypeScript 5.9 / Vite 7 / zustand 5 / react-router 7 / i18next" {
        tags "Frontend"
        properties {
          state "current"
          confidence "high"
          sourceRefs "source-code/frontend/package.json, source-code/frontend/vite.config.ts:15-17, source-code/frontend/src/utils/pywebview.ts"
        }
      }

      mediaSrv = container "回环静态/媒体服务" "Flask + werkzeug make_server，绑定 127.0.0.1、端口自 5000 起自动探测；仅托管 SPA 静态文件与图片/视频媒体，不提供业务 API" "Flask 3.1 / flask-cors 6.0 / werkzeug 3.1" {
        tags "Loopback", "RiskSurface"
        properties {
          state "current"
          confidence "high"
          sourceRefs "source-code/backend/src/utils/http_server.py:19-44, 86, 97-279, 300"
        }
      }

      bridgeApi = container "pywebview 桥门面" "单一 Api 类 7705 行 / 389 个方法，聚合 11 个 bridge 控制器暴露给前端 JS" "Python" {
        tags "TrustBoundary"
        properties {
          state "current"
          confidence "high"
          sourceRefs "source-code/backend/src/bridge/api.py (wc -l=7705, def=389), source-code/backend/src/bridge/controllers/ (11 控制器), source-code/backend/main.py:817"
        }
      }

      coreSvc = container "领域服务层" "环境/进程/插件/市场/工作流/LoRA/资产库/依赖/监控/救援/版本/设置/Git 等核心逻辑" "Python" {
        properties {
          state "current"
          confidence "high"
          sourceRefs "source-code/backend/src/core/"
        }
      }

      updater = container "独立更新器进程" "ComfyNexusUpdater_v1.0.exe（onefile），由主程序以 argv[zip, target, main_exe] 拉起，执行备份→解压→清理→回滚" "Python / PyInstaller onefile" {
        tags "OwnProcess", "RiskSurface"
        properties {
          state "current"
          confidence "high"
          sourceRefs "source-code/backend/updater/updater.py:484, 599-680, source-code/backend/updater/updater.spec:75-99, source-code/backend/src/core/updater/update_controller.py:258-286"
        }
      }

      sqliteDb = container "AI 会话与配置库" "SQLite：对话、话题、AI 配置（api_key 以 encrypted: 前缀 Fernet 密文存放）" "SQLite" {
        tags "Datastore"
        properties {
          state "current"
          confidence "high"
          sourceRefs "source-code/backend/src/core/ai/database.py:15"
        }
      }

      cfgStore = container "配置与运行时目录" "settings.json / default_config.json / environments.json / lora_config.json / preset_index.json；开发 backend/config，打包 exe 同级 config。autoUpdate 默认 false" "JSON 明文文件" {
        tags "Datastore"
        properties {
          state "current"
          confidence "high"
          sourceRefs "source-code/backend/src/utils/paths.py:166-197, source-code/backend/src/core/settings_manager.py:47"
        }
      }

      keyStore = container "本机 Fernet 密钥文件" "data/secrets/ai_fernet.key，首次使用生成，原子写入 + icacls 断开继承仅授权当前用户；已被 .gitignore 覆盖。注意：实现体 secret_store.py 仅存在于未提交工作区，基线 88bdb15 仍用写死的固定密钥" "File" {
        tags "Datastore", "Secret"
        properties {
          state "current (uncommitted working tree only)"
          confidence "high"
          sourceRefs "source-code/backend/src/core/ai/secret_store.py:4-16, 44, 62-71, 134-183 (UNTRACKED), source-code/.gitignore:16"
          baselineRefs "git show 88bdb15:source-code/backend/src/core/ai/config_manager.py -> line 23 _ENCRYPTION_KEY hardcoded"
        }
      }
    }

    // ===== L1 上下文 =====
    user -> nexus "操作与管理本地 ComfyUI 环境"
    user -> comfyui "在工作台 iframe 内直接进行节点式创作"
    nexus -> comfyui "启动/停止进程、读日志、探活端口"
    nexus -> aiProviders "对话与图像/文档分析请求（HTTPS）"
    nexus -> github "拉取插件、Release 与 version.json"
    nexus -> pypi "安装与修复 Python 依赖"
    nexus -> civitai "抓取 LoRA 元数据与预览图"

    // ===== L2 容器内部 =====
    shell -> mediaSrv "在守护线程内创建并持有" {
      properties { confidence "high" sourceRefs "source-code/backend/main.py:597-598, source-code/backend/src/utils/http_server.py:289-301" }
    }
    shell -> spa "以 WebView2 窗口加载 http://127.0.0.1:{auto-port}" {
      properties { confidence "high" sourceRefs "source-code/backend/main.py:805-817 (url=...get_url() 在 807)" }
    }
    mediaSrv -> spa "HTTP GET 提供 index.html 与 /<path:path> 静态文件、媒体预览" "HTTP (sync)" {
      properties {
        confidence "high"
        sourceRefs "source-code/backend/src/utils/http_server.py:234-261"
        note "SPA 兜底路由会把未命中路径回落到 index.html"
      }
    }
    spa -> bridgeApi "调用 389 个方法（业务 API 主通道）" "window.pywebview.api，WebView2 内联通信（sync），非 HTTP、无鉴权、无来源校验" {
      properties {
        confidence "high"
        sourceRefs "source-code/frontend/src/services/bridge.ts, source-code/frontend/src/api/dependencyApi.ts (头注释: 通过 pywebview JS Bridge 通信), source-code/backend/src/bridge/api.py"
      }
    }
    bridgeApi -> coreSvc "委派领域操作" "in-process" {
      properties { confidence "high" sourceRefs "source-code/backend/src/bridge/controllers/" }
    }
    coreSvc -> sqliteDb "读写会话/话题/AI 配置" "SQL" {
      properties { confidence "high" sourceRefs "source-code/backend/src/core/ai/database.py:15" }
    }
    coreSvc -> cfgStore "读写设置与环境配置（明文 JSON）" "file" {
      properties { confidence "high" sourceRefs "source-code/backend/src/utils/paths.py:166-197" }
    }
    coreSvc -> keyStore "取/建 Fernet 密钥以加解密 api_key" "file" {
      properties { confidence "high" sourceRefs "source-code/backend/src/core/ai/secret_store.py:162-183" }
    }
    coreSvc -> updater "以独立进程拉起，传入 zip/目标目录/主 exe 路径" "subprocess" {
      properties { confidence "high" sourceRefs "source-code/backend/src/core/updater/update_controller.py:280-286" }
    }
    coreSvc -> github "检查更新并下载更新包（stream）" "HTTPS" {
      properties { confidence "high" sourceRefs "source-code/backend/src/core/updater/update_checker.py:16, 149-153, source-code/backend/src/core/updater/update_downloader.py:433" }
    }
    coreSvc -> comfyui "Popen 启动托管进程并解析 --port" "subprocess" {
      properties { confidence "high" sourceRefs "source-code/backend/src/core/process/comfyui_process.py:362, 1382-1397" }
    }
    spa -> comfyui "跨域 iframe 直连 http://127.0.0.1:8188，postMessage 同步设置" "HTTP/WebSocket (由 ComfyUI 自身提供)" {
      properties {
        confidence "high"
        sourceRefs "source-code/frontend/src/components/workspace/WorkspaceFrame.tsx:6, 35, 190-193"
      }
    }
    coreSvc -> aiProviders "provider 适配器转发对话/流式响应" "HTTPS（讯飞星火另用 WebSocket 流式）" {
      properties { confidence "medium" sourceRefs "README.md:109 与 src/core/ai/providers/ 目录结构" }
    }

  }

  views {

    systemLandscape "Landscape" "L0/L1 全景：产品与被托管、被集成的外部系统" {
      include *
      autolayout {
        rankdir LR
        nodesep 60
        ranksep 180
      }
    }

    systemContext nexus "SystemContext" "系统上下文：ComfyNexus 边界与外部参与者" {
      include *
      autolayout {
        rankdir LR
        nodesep 70
        ranksep 200
      }
    }

    container nexus "Containers" "容器视图：单进程桌面应用内部的部署/职责单元" {
      include *
      autolayout {
        rankdir TB
        nodesep 70
        ranksep 160
      }
    }

    styles {

      element "Person" {
        shape person
        background #1168bd
        fontColor #ffffff
      }

      element "Software System" {
        background #1168bd
        fontColor #ffffff
      }

      element "ExternalSystem" {
        shape RoundedBox
        background #8c8c8c
        fontColor #ffffff
      }

      element "OwnProcess" {
        background #2563eb
        fontColor #ffffff
      }

      element "Frontend" {
        shape WebBrowser
        background #0a6ed1
        fontColor #ffffff
      }

      element "Loopback" {
        shape WebBrowser
        background #1e88e5
        fontColor #ffffff
      }

      element "TrustBoundary" {
        background #7c3aed
        fontColor #ffffff
      }

      element "Datastore" {
        shape Database
        background #2f855a
        fontColor #ffffff
      }

      element "Secret" {
        shape Folder
        background #b7791f
        fontColor #000000
      }

      element "RiskSurface" {
        borderColor #d33
        borderWidth 3
      }

    }

  }

}
