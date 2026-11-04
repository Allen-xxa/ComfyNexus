# 架构基线：范围、路由与证据计划

生成日期：2026-11-01 · 分支：`fix/security-hardening`（= `chore/baseline` = `88bdb15`）
产出方式：`architecture-visualization:explore` 路由 → `system-modeler` + `c4model`（现状建模）、`risk-quality-reviewer`（风险评审）

> **基线漂移警告（先读这条）**
> 本文档所有结论锚定提交 `88bdb15`。但**在本次会话进行期间，工作区被另一个写入者改动**：14 个已跟踪文件与 HEAD 不一致（其中 5 个是 `__pycache__/*.pyc` 噪声），另有 1 个未跟踪新模块 `source-code/backend/src/core/ai/secret_store.py`，以及 3 个前端临时脚本 `.tmp-fe-baseline.json` / `.tmp-fe-after.json` / `.tmp-report.cjs`。
> 改动集中于 **AI 服务商密钥存储**（`config_manager.py` +184 行、`ai_service.py`、`models.py`、`ai_controller.py`、`useAPIConfigStore.ts`、`APIConfigFormView.tsx`、`bridge.ts` 及一个前端测试文件）。
> 因此：凡涉及密钥存储的结论，本文档**区分「HEAD 基线」与「工作区未提交」**两种状态，不混为一谈。执行整改前必须先确认这份在途改动是否要收进同一批次。


## 受众与决策问题

| 受众 | 需要回答的问题 |
|:---|:---|
| 项目维护者（本人） | Phase 1 整改项在架构里的**落点**分别在哪，哪些已经完成 |
| 接手执行方案的 agent | 进程/端口/数据流的**边界**在哪，改动会影响哪些容器 |
| 评审者 | 每条安全主张是否有可复核的 file:line 证据 |

## 范围

**范围内**：`source-code/backend`（Python 主进程、updater、打包脚本）、`source-code/frontend`（React SPA）、仓库根的 CI/文档/卫生状态。视图层级到 **C4 Container（L2）**，不下钻到 component/L4。

**范围外**（遵循 Phase 1 非目标，不改代码、不提重构）：后端 API 层拆分、UI 重构、依赖升级、git 历史重写。

## 路由记录

`explore` 场景表命中两条，未选其他：

1. **「这个仓库现在是什么架构？」** → `system-modeler`（结构与边界）+ `c4model`（Structurizr DSL 作为可维护图源）。
2. **「这架构风险大不大？」** → `risk-quality-reviewer`，复用上面的模型作为基线。

未走 `dependency-impact-analyzer` / `evolution-planner`：本次问题不是「改动会影响谁」也不是「目标态怎么演进」，而是「现状 + 现状的风险登记」。

格式选择依 `diagram-output-formats.md`：C4 视图用 Structurizr DSL；风险网络用 Graphviz DOT。

## 证据计划与覆盖度

| 证据类型 | 来源 | 状态 |
|:---|:---|:---|
| code | `main.py`、`src/utils/http_server.py`、`src/bridge/api.py`、`src/core/**`、`updater/**` | 已读并逐条定位行号 |
| config | `vite.config.ts`、`package.json`、`requirements.txt`、`*.spec`、`settings_manager.py` | 已读 |
| build/CI | `build_scripts/构建.ps1`、`.github/workflows/*` | 已读，含执行分支判定 |
| 运行时行为 | 本地 Flask test client 探针（CORS 头、路径穿越） | **已实测**，见下 |
| document | `README.md`（`88bdb15` 确立的单一事实来源）、`CLAUDE.md` | 已读，代码为准 |

**探针说明**：安全类主张不采信推断。我用项目自带 venv（`flask 3.1.3` / `werkzeug 3.1.9` / `flask-cors 6.0.5`）复刻了 `http_server.py` 的路由注册方式，在内存临时目录上离线运行，实测出：

- `Access-Control-Allow-Origin: https://evil.example.com`（反射任意 Origin）；
- `/../secrets/settings.json`、`/%2e%2e/secrets/settings.json`、`/..%2fsecrets/settings.json`、绝对路径注入 —— 四者均返回 `200` 且读到 static 目录**之外**的文件。

探针脚本跑在仓库外临时目录，未作为测试资产入库（避免把 Phase 1 范围扩成测试工程）。若要把它固化成回归测试，属独立任务。

## 建模过程中的三条结论修正（重要）

侦察子代理的初步结论经本人读码核对后修正如下，记录在此以免风险登记误导执行：

1. **「API Key 用写死在源码里的固定 Fernet 密钥加密」——对 HEAD 成立，对工作区已不成立。**
   - HEAD `88bdb15`：`git show HEAD:...config_manager.py` 实测第 23 行仍有 `_ENCRYPTION_KEY = b'ZmDf…'`，第 26 行 `Fernet(self._ENCRYPTION_KEY)`；`secret_store.py` **不在 HEAD 中**。
   - 工作区（未提交）：新增 `src/core/ai/secret_store.py`，改为首次使用时 `Fernet.generate_key()` 生成**按机器密钥**，落盘 `data/secrets/ai_fernet.key`，原子写入 + `icacls /inheritance:r /grant:r {principal}:F`，并带旧密钥幂等迁移（`reencrypt_required`）。
   - 结论：**这不是「已完成项」，而是「在途未收口的改动」**。Phase 1 若把它当已修复而跳过，等于让基线继续带着硬编码密钥发布。
2. ~~「updater 下载不校验 hash」~~ → 分两层：`update_downloader.py:138-149` 确实**在远端未提供 hash 时跳过校验**（fail-open），但发布链路实际会带 hash——根 `version.json:6` 有 `file_hash`，且 `.github/workflows/update-version.yml` 由 release 事件生成。因此这是**降级路径**风险，不是常态缺失。该文件未被在途改动触及，结论对 HEAD 与工作区同样成立。
3. ~~「`quick_build.ps1:111-113` 默认带 `-SkipTests`」~~ → `build_scripts/` 下**不存在** `quick_build.ps1`（实测目录清单），实际是 `快速构建.ps1:45-47` 同时带 `-SkipTests -SkipClean`。同类：清理临时 dist 的行号是 `构建.ps1:155` 而非 `:156`。

## 已知局限

- 视图停在 Container 级；`src/core/**` 内部 20+ 子模块只按目录职责归并，未逐一验证每个子包的边界（`src/bridge/controllers/` 11 个控制器已实测文件数）。
- ComfyUI 与主程序的**运行期交互协议**（除进程启动、端口探活、日志读取之外）未在代码中找到 HTTP/WebSocket 客户端调用，故模型里画成「进程管理 + 前端 iframe 直连」，不臆造控制面。
- 前端 → ComfyUI iframe 的 `postMessage` 协议细节未展开。
- `.workbuddy-ai/`、`backup/` 等非产品目录未纳入模型。
