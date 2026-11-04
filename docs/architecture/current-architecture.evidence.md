# 现状架构 · 证据表

配套 `current-architecture.structurizr.dsl`。每条给出 **验证方式**，区分「亲自读码」「实测」「复核后采纳」。

**验证方式图例**
- `读码` — 本人直接打开该文件并核对该行内容。
- `实测` — 离线运行确定性探针得到运行时行为（见文末）。
- `复核` — 最初由探索子代理报告，本人再读码确认（子代理有两处结论被推翻，见 `plan-and-route.md`）。
- `聚合` — 由 `wc -l` / `grep -c` / `ls` / `git ls-files` 得到的计数。

## 节点证据

| 节点 | sourceRefs（仓库根相对路径） | 置信度 | 验证方式 |
|:---|:---|:---|:---|
| 桌面壳进程 `shell` | `source-code/backend/main.py:378`（`main()`）、`597-598`、`805-817`、`1203` | high | 读码 + grep 锚点 |
| 前端 SPA `spa` | `source-code/frontend/package.json`、`source-code/frontend/vite.config.ts:15,17`（`base:'./'`、`outDir:'../dist'`） | high | 读码 |
| 回环服务 `mediaSrv` | `source-code/backend/src/utils/http_server.py:19-44`（端口自 5000 探测）、`86`（`CORS(self.app)`）、`97-279`（8 组路由）、`300`（`make_server('127.0.0.1', …)`） | high | 读码 + 实测 |
| 桥门面 `bridgeApi` | `source-code/backend/src/bridge/api.py`（`wc -l`=7705、`grep -c "def "`=389）、`src/bridge/controllers/`（11 控制器）、`main.py:817`（`js_api=api`） | high | 聚合 + 读码 |
| 领域服务 `coreSvc` | `source-code/backend/src/core/` | high | 读码（目录职责按文件名与调用点归并） |
| 独立更新器 `updater` | `source-code/backend/updater/updater.py:484,599-680`、`updater/updater.spec:75-99`、`src/core/updater/update_controller.py:258-286` | high | 读码 + 复核 |
| SQLite 库 `sqliteDb` | `source-code/backend/src/core/ai/database.py:15`（`DB_PATH = get_data_dir()/"ai_assistant.db"`） | high | 读码 |
| 配置目录 `cfgStore` | `source-code/backend/src/utils/paths.py:166-197`（开发 `backend/config` / 打包 `exe 同级 config`）、`src/core/settings_manager.py:47`（`"autoUpdate": False`） | high | 读码 |
| 本机密钥 `keyStore` | `src/core/ai/secret_store.py:4-16, 44, 62, 71-116`（`icacls /inheritance:r /grant:r {principal}:F`）、`134-183`（原子写）；忽略规则 `source-code/.gitignore:16` | high（**仅工作区**） | 读码 + 实测 `git check-ignore`；`git cat-file -e HEAD:…secret_store.py` 失败 → **不在基线** |
| ComfyUI `comfyui` | `src/core/process/comfyui_process.py:33`（`subprocess.Popen` 类型）、`40`（`self.port=8188`）、`362`（启动）、`537`/`1415`（`sock.connect_ex(('127.0.0.1', port))` 探活）、`1382-1397`（端口解析） | high | 读码 + 复核 |
| GitHub 等外部系统 | `src/core/updater/update_checker.py:16`（`VERSION_JSON_URL`）、`149-153`；`README.md:93,104,109-110` | high / medium | 读码；Civitai、PyPI 仅依 README 表述 → medium |

## 关系证据

| 关系 | sourceRefs | 置信度 | 验证方式 |
|:---|:---|:---|:---|
| `shell → mediaSrv` 创建并持有 | `main.py:597-598`、`http_server.py:289-301` | high | 读码 |
| `shell → spa` WebView 加载 `get_url()` | `main.py:807`（`url=http_server.get_url()`）、`324`、`630-631` | high | 读码 |
| `mediaSrv → spa` 静态文件与兜底 | `http_server.py:234-261`（`file_path = self.static_dir / path` → `send_file(str(file_path))`，`242`） | high | 读码 + 实测 |
| `spa → bridgeApi` 业务主通道 | `frontend/src/services/bridge.ts`、`frontend/src/api/dependencyApi.ts` 头注释「通过 pywebview JS Bridge 与 Python 后端通信」、`api.py` 方法表 | high | 复核 + 读码 |
| `spa → comfyui` 跨域 iframe | `frontend/src/components/workspace/WorkspaceFrame.tsx:6`（「不再需要反向代理，iframe 直接加载 ComfyUI」）、`35`（「跨域 iframe，无法直接访问 contentDocument」）、`190-193`（`src={url}`）、`43-70/150-166`（`postMessage`） | high | 读码 |
| `coreSvc → updater` 进程拉起 | `src/core/updater/update_controller.py:280`（`cmd=[updater_exe, zip_path, target_dir, main_exe]`）、`258-271` | high | 读码 |
| `coreSvc → github` 下载更新包 | `update_checker.py:16,149-153`、`update_downloader.py:433,550`（`requests.get`） | high | 读码 |
| `coreSvc → sqliteDb` / `cfgStore` / `keyStore` | `ai/database.py:15`、`utils/paths.py:166-197`、`ai/secret_store.py:162-183` | high | 读码 |
| `coreSvc → comfyui` 进程管理 | `comfyui_process.py:362`、`1382-1397` | high | 读码 |
| `coreSvc → aiProviders` 协议细节 | `README.md:109` + `src/core/ai/providers/` 目录 | medium | 未逐个 provider 读实现 → 显式降级 |

## 实测记录（离线，无网络）

环境：项目自带 venv `source-code/backend/.venv`，`flask 3.1.3` / `werkzeug 3.1.9` / `flask-cors 6.0.5`（`requirements.txt:8-9` 声明 `flask>=3.0.0`、`flask-cors>=4.0.0`）。
方法：在临时目录复刻 `http_server.py` 的路由注册方式（`CORS(app)` 无参 + `/<path:path>` → `static_dir / path` → `send_file`），用 Flask test client 发请求；仓库内的秘密文件放在 static 目录**之外**。

| 探针 | 结果 |
|:---|:---|
| 带 `Origin: https://evil.example.com` 请求 `/` | `Access-Control-Allow-Origin: https://evil.example.com`（反射任意来源）；`Access-Control-Allow-Credentials` 未设置 |
| `/../secrets/settings.json` | `200`，读到 static 目录外文件 |
| `/%2e%2e/secrets/settings.json` | `200`，同上（编码点号同样可达） |
| `/..%2fsecrets/settings.json` | `200`，同上（编码分隔符同样可达） |
| 绝对路径注入（`/C:/…/secrets/settings.json`） | `200`，读到任意绝对路径文件 |
| `/gallery/asset/../secrets/settings.json` | `200`（`asset_id` 为单段 `<string>`，穿越深度受限；实测该路由单段可达） |
| `/%2E%2E/%2E%2E/…`（全大写编码） | `200` 但回落 `index.html`，未读文件 → 说明并非所有编码变体都命中，结论按实测逐条列出，不外推 |

探针脚本运行于仓库外临时目录，**未入库**为测试资产。上述结论已用于 `risk-register.md` 的 R-01/R-02 定级。

## 计数类事实

| 事实 | 值 | 命令 |
|:---|:---|:---|
| 仓库跟踪文件总数 | 1151 | `git ls-files \| wc -l` |
| 被跟踪的 `.pyc` | 10 | `git ls-files \| grep -c '\.pyc$'` |
| 被跟踪的 `source-code/dist` + `build` 产物 | 25（11 + 14） | `git ls-files \| grep -E '^source-code/(dist\|build)/' \| wc -l` |
| 根 `.github/workflows` | 4 个，全部无 test/lint 步骤 | `grep -lE "pytest\|npm (run )?test\|eslint" .github/workflows/*.yml` → 空 |
| 非根 workflow 目录 | `source-code/.github/workflows/{lint.yml,update-version.yml}` | `git ls-files \| grep workflows/` |
| `data/` 目录 | 整目录被忽略，但 8 个文件已被跟踪 | `git ls-files \| grep '^source-code/data/'` |

## 基线与工作区的分叉台账

会话期间工作区被并发修改。以下即 `git diff --name-only HEAD` 与 `git ls-files --others` 的实测结果，供执行者判断归属，**不属本架构文档的产出**。

| 状态 | 文件 | 差异规模 |
|:---|:---|:---|
| 已跟踪·已改 | `source-code/backend/src/core/ai/config_manager.py` | +184 行（改用 `secret_store`） |
| 已跟踪·已改 | `…/ai/ai_service.py`、`…/ai/models.py`、`…/bridge/controllers/ai_controller.py` | 7 / 26 行 / 未计 |
| 已跟踪·已改 | `source-code/frontend/src/stores/useAPIConfigStore.ts`、`components/ai/APIConfigFormView.tsx`、`types/bridge.ts`、`__tests__/unit/stores/useAPIConfigStore.test.ts` | 72 行（store）/ 其余未计 |
| 已跟踪·已改 | `source-code/.gitignore` | +2 行（新增 `data/secrets/` 显式忽略） |
| 已跟踪·已改 | 5 个 `__pycache__/*.pyc`（`backend/`、`src/`、`src/core/config/` 下） | 二进制噪声，见 R-10 |
| **未跟踪·新** | `source-code/backend/src/core/ai/secret_store.py` | 基线中不存在 |
| 未跟踪·残留 | `source-code/frontend/.tmp-fe-baseline.json`、`.tmp-fe-after.json`、`.tmp-report.cjs` | 来路不明，需确认后处置 |

**核对命令**（可复跑）：

```bash
git show HEAD:source-code/backend/src/core/ai/config_manager.py | grep -n "_ENCRYPTION_KEY"
git cat-file -e HEAD:source-code/backend/src/core/ai/secret_store.py && echo in-HEAD || echo not-in-HEAD
git diff --name-only HEAD
git ls-files --others --exclude-standard
```
