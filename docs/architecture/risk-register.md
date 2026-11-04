# 架构风险登记 · Phase 1 范围

**基线**：`fix/security-hardening` @ `88bdb15`（= `chore/baseline`，与 `main` = `ed49d2a` 的合并基线一致）。
**基线 ≠ 工作区**：本登记锚定提交 `88bdb15`。会话期间工作区被并发改动（14 个已跟踪文件 + 未跟踪 `secret_store.py`，集中在密钥存储），故凡涉密钥存储的结论均显式区分 HEAD 与工作区两种状态，见 R-12。执行前先 `git status` 确认在途内容归属。
**范围**：安全加固、仓库卫生、CI 门禁、文档准确性。**不含**后端 API 层拆分、UI 重构、依赖升级、git 历史重写。
**配套**：`current-architecture.structurizr.dsl`（红框元素 `mediaSrv`、`updater` 即风险面）、`risk-map.dot`。

严重度 = 影响 × 可达性；置信度按 `architecture-contract.md` 的 high/medium/low 分档。所有「证据」栏的 file:line 均经本人读码核对，`实测` 标记者见 `current-architecture.evidence.md` 探针记录。

---

## 一、已提交的缓解 · 请勿重复整改

先立此条，避免执行 agent 把已修好的东西再改一遍。**下表全部是 HEAD `88bdb15` 已提交的事实**。

| Phase 1 预案项 | 现状 | 证据 |
|:---|:---|:---|
| 密钥日志脱敏 | 已实现 `mask_api_key()`，前端侧亦以 `'***'` 掩码 | `src/core/ai/security_utils.py:13`（实测存在于 HEAD）、`frontend/src/stores/useAPIConfigStore.ts:916,1004` |
| 运行时数据目录不入库 | `source-code/.gitignore:16` 的 `data/` 已覆盖 `data/secrets/ai_fernet.key` | 实测 `git check-ignore -v` → 命中 `source-code/.gitignore:16`；该规则在 HEAD 即存在 |
| 应用自动更新默认关闭 | `autoUpdate` 默认 `False`，与 `README.md:151` 表述一致 | `src/core/settings_manager.py:47`（未被在途改动触及） |
| README 单一事实来源 | 已确立并声明维护规则 | `README.md:218`、`source-code/README更新规范.md` |

**一处「疑似风险」经核实排除**：`git config` 中 `filter.lfs.*` 且 `filter.lfs.required=true` 属**用户全局配置**，仓库内无 `.gitattributes`、无 LFS 跟踪对象（实测 `ls .gitattributes` → 不存在）。不应作为整改项，也不要在仓库里新增 LFS 配置。

---

## 一·补 · 基线密钥：在途改动 ≠ 已完成

### R-12 · HEAD 仍使用写死在源码里的固定 Fernet 密钥 · 严重 / high 置信

**证据**：`git show HEAD:source-code/backend/src/core/ai/config_manager.py` 实测第 23 行 `_ENCRYPTION_KEY = b'ZmDfcTF7_…'`、第 26 行 `self._cipher = Fernet(self._ENCRYPTION_KEY)`；`git cat-file -e HEAD:source-code/backend/src/core/ai/secret_store.py` 失败——替代方案**不在基线中**。

**工作区状态**：存在一份**未提交**的修复。新增未跟踪模块 `src/core/ai/secret_store.py`，配套改动 `config_manager.py`(+184 行)、`ai_service.py`、`models.py`、`ai_controller.py`、`frontend/src/stores/useAPIConfigStore.ts`、`APIConfigFormView.tsx`、`types/bridge.ts`、`useAPIConfigStore.test.ts`、`source-code/.gitignore`(+2 行 `data/secrets/`)。它做对了：按机器生成密钥、原子写入、`icacls /inheritance:r /grant:r {principal}:F`、旧密钥幂等迁移（`secret_store.py:4-16, 71-116, 134-183`）。

**影响**：固定密钥写在公开仓库源码里，任何拿到源码或安装包（PyInstaller 产物可反解）的人都能解密各机器上 `ai_assistant.db` 里的 `api_key` 密文——加密在此退化为混淆。

**因此本项的性质从「需实现」变为「需收口」**：确认这份在途改动的来源与意图、审查、作为独立提交进入基线、并验证迁移路径。把它当已完成项跳过，等于让基线继续带硬编码密钥发布。

**Phase 1 归属**：AI API-key storage/migration（预案首项）。

**验收**：
1. `git show HEAD:…config_manager.py | grep _ENCRYPTION_KEY` 无命中；
2. 在途改动作为**独立提交**收口，不与 R-01/R-09 等混提；
3. 离线迁移用例：旧格式密文 + 旧密钥 → 明文 → 新密钥重加密 → `reencrypt_required` 翻假；
4. 文档需明示：已泄露的固定密钥无法追回历史暴露，用户若要彻底干净须重设 key。

---

## 二、本地 HTTP 服务面

### R-01 · 回环静态路由可读取本机任意文件 · 严重 / high 置信 · **实测**

**证据**：`source-code/backend/src/utils/http_server.py:234-242` —— 兜底路由 `@app.route('/<path:path>')` 直接 `file_path = self.static_dir / path` 后 `send_file(str(file_path))`，未经 `safe_join`/`realpath` 校验。文件虽在 `:11` 导入了 `send_from_directory`，但**全文无一处使用**（实测 `grep -n "send_from_directory"` 仅命中导入行）。

**实测结论**：`/../`、`%2e%2e/`、`..%2f` 三种写法与**绝对路径注入**均返回 `200` 并读到 static 目录外的文件。此前「Werkzeug 是否会先规整掉 `..`」的疑问已排除——不会。

**影响**：任意本机进程、以及用户浏览器里的任意网页，可通过 `http://127.0.0.1:{port}` 读取该 Python 进程权限范围内的**任何文件**（配置 JSON、SQLite 库、密钥文件、用户文档）。属信息泄露，非代码执行。

**Phase 1 归属**：local HTTP hardening → static-path traversal。

**验收**：`/<path:path>` 与其余 5 处 `dir / name` 拼接路由（`:110, 141, 199, 224, 239`）全部改为 `safe_join`/显式根目录前缀校验；新增确定性离线用例：上述四类请求必须 `404/403` 而非 `200`。

### R-02 · CORS 反射任意来源 · 高 / high 置信 · **实测**

**证据**：`http_server.py:85-86` —— `CORS(self.app)` 无任何参数，flask-cors 默认对全部路由放开全部来源。

**实测结论**：带 `Origin: https://evil.example.com` 的请求返回 `Access-Control-Allow-Origin: https://evil.example.com`（`Access-Control-Allow-Credentials` 未设置）。

**影响**：与 R-01 组合后，**用户浏览器的任意网页**即可完成对本机任意文件的读取——不需要本地恶意程序，也不需要 CSRF。这是把 R-01 从「本机进程间问题」升格为「远程可利用」的乘数。

**Phase 1 归属**：local HTTP hardening → CORS。

**验收**：显式 `origins=` 白名单（本应用自身回环来源），并证明跨来源预检被拒。

### R-03 · 回环服务无鉴权、端口自 5000 起顺序可预测 · 中 / high 置信

**证据**：`http_server.py:19-44`（`find_available_port(5000, 100)`，逐个 `bind('127.0.0.1', port)`）、`:300`（`make_server('127.0.0.1', self.port, …)`）、`:324`。8 组路由均无任何 token/来源校验（`:97-279`）。

**影响**：进一步降低 R-01/R-02 的利用成本（攻击者可从 5000–5100 小范围枚举）。绑定 `127.0.0.1` 本身是正确的，不构成外网暴露——不要把「改为随机高位端口」当成主要修复，那只是降噪。

**Phase 1 归属**：local HTTP hardening → loopback binding（现状已满足 loopback 一项）。

---

## 三、更新与下载链路

### R-04 · 更新器解压无路径穿越防护 · 严重 / high 置信

**证据**：`source-code/backend/updater/updater.py:599`（`_extract_update`）、`:641`（逐成员遍历）、`:653`（`target_path = target_dir / target_member`）、`:657`（`open(target_path, 'wb')`）。全程无 `..`/绝对路径/`resolve()`/`is_relative_to` 校验（实测 `grep -n "resolve()\|is_relative_to\|sanitiz"` 于该文件无命中）。

**影响**：恶意或被替换的更新包可将文件写入应用目录**之外**的任意路径（启动目录、计划任务目录等），属本机代码执行前置条件。

**关键放大点**：`updater/updater.py` 全文 `grep -c "sha256\|hashlib\|file_hash"` = **0**，即更新器进程**自身不做任何完整性校验**；它只信任主程序传来的 `zip_path`（`src/core/updater/update_controller.py:280`）。

**Phase 1 归属**：updater zip-slip。

**验收**：成员名规范化后必须落在目标根目录内，越界即整体拒绝；离线构造一个含 `../` 成员的 zip，断言未写出任何文件。

### R-05 · 下载校验 fail-open：远端未提供 hash 时静默跳过 · 中 / high 置信

**证据**：`src/core/updater/update_downloader.py:138`（`if expected_hash:`）与 `:149`（`logger.info("…无预期 hash，跳过验证")`）；流式下载同样条件化：`:451`、`:601`（`sha256_hash = hashlib.sha256() if file_hash else None`）。控制器侧 `:178-179` 亦为「有 hash 才校验」。

**现状缓解**：正常发布链路**确实带 hash** —— 根 `version.json:6` 存在 `file_hash`，由 `.github/workflows/update-version.yml`（`release: types: [published]`，`:4,8`）生成。因此这是**降级路径**风险，而非日常缺失。

**影响**：一旦 `version.json` 缺失 `file_hash` 字段（人工失误、上游仓库变更、或 `main` 分支该文件被改写），下载会**无告警地**跳过完整性校验，且与 R-04 串联后直接落到任意写。

**Phase 1 归属**：hash validation。

**验收**：无 hash 时**拒绝**安装（而非跳过），并给出用户可见错误；补一条离线用例断言 `expected_hash` 为空路径的行为。

### R-06 · 更新源硬编码上游仓库，与本 fork 发布链路错位 · 中 / high 置信

**证据**：`src/core/updater/update_checker.py:16` —— `VERSION_JSON_URL = https://raw.githubusercontent.com/Allen-xxa/ComfyNexus/main/version.json`，`download_url` 亦指向 `github.com/Allen-xxa/…`（根 `version.json:4`）。本仓库远端为 `origin = https://github.com/qiqStrong/ComfyNexus.git`（实测 `git remote -v`）。

**已处置（2026-11-02）**：全仓库 `Allen-xxa` 引用已替换为 `qiqStrong`，共 22 处，覆盖更新源、数据源
（`comfyui_api_nodes.json` / `pytorch_mapping.json` / `comfyui_releases.json`）、前端 GitHub 跳转与
`version.json` 的 `download_url`。该风险从「源错位」降级为「仍需人工发布对应 release 资产」。

**影响**：本 fork 的 `.github/workflows/update-version.yml` 会写自己仓库的 `version.json`，但客户端永远读上游的。若用户手动开启更新检查，得到的是**上游构建产物**，会覆盖 fork 的本地改动。

**现状缓解**：`autoUpdate` 默认 `False`（`settings_manager.py:47`），且 `README.md:151` 已声明默认关闭——这条文档表述与代码一致，已核对。

**Phase 1 归属**：安全基线（供应链一致性）。

**验收**：更新源指向与实际发布仓库一致，或在 UI/文档中明示「本 fork 不提供更新」并禁用该路径。**决策项，需维护者拍板**，不属于可直接自动修复的范围。

### R-07 · MinGit 下载解压：无完整性校验 + 无穿越防护 · 中 / high 置信

**证据**：`src/utils/mingit_downloader.py:873`（`_extract_zip`）、`:914`（`target_path = dest_dir / target_member`）、`:920`（`open(target_path,"wb")`）；同文件 `grep "sha256\|hash"` 仅命中 `:20` 的 `_hashlib` 类型导入，即**无实际校验**。下载 URL 固定：`:58` `https://github.com/git-for-windows/git/releases/download/v{version}/MinGit-{version}-64-bit.zip`。

**缓解**：来源为固定官方 host + HTTPS，故 R-04 的「远端内容可替换」前提在此路径上弱得多；主要残余是穿越防护缺失。

**Phase 1 归属**：updater zip-slip（同类模式一并收口）。

**验收**：与 R-04 共用同一套安全解压实现，不留第二份。

---

## 四、信任边界

### R-08 · 桥对路径/URL 参数无白名单 · 中 / high 置信（纵深防御，非独立入口）

**证据**：`src/bridge/api.py` 中接收任意路径或 URL 的方法，逐条核对行号：`write_model_paths_yaml(comfyui_path, content)` `:2367`、`read_log_file(file_path)` `:2717`、`open_folder(path)` `:3262`、`open_url(url)` `:1407`；另有 `validate_folder_path` `:3274`、`save_preset_to_file` `:1770`、`dependency_install_whl` `:5647`、`marketplace_install_plugin(github_url, …)` `:4979` 等。

**必须准确理解可达性**：桥**只对 WebView2 窗口内的 JS 开放**，不经 HTTP 暴露（业务 API 不走回环服务，见 `current-architecture.md` 第 2 节）。因此它**不是**远程攻击面，而是「一旦 SPA 侧发生代码注入，即等价于本机文件读写 + 打开目录 + 安装 whl」的放大面。定级为中而非严重正是基于此。

**Phase 1 归属**：可在 Phase 1 收口，也可与桥拆分一并排入后续阶段——**但不要在 Phase 1 动桥的结构**（属重构，越界）。

**建议的最小动作**：对纯路径参数增加根目录约束校验，不触碰方法签名与分层。

---

## 五、CI 与工程治理

### R-09 · 无有效 CI 质量门禁 · 高 / high 置信

**证据**（三条独立事实）：
1. 仓库根 `.github/workflows/` 仅 4 个文件：`sync_pytorch_versions.yml`、`update-version.yml`、`update_comfyui_release.yml`、`update_nodes.yml`——实测 `grep -lE "pytest|npm (run )?test|eslint"` 结果为**空**，即全部不跑测试或 lint，都是定时/数据同步类。
2. 真正的 lint 作业在 `source-code/.github/workflows/lint.yml`。GitHub **只读取仓库根**的 `.github/`，而本仓库是单 git 根（实测 `git ls-files` 同时列出两处路径），故该工作流**永远不会被触发**。同目录的 `source-code/.github/workflows/update-version.yml` 同理失效，且与根目录同名文件重复。
3. 构建管线里唯一的测试是非阻断的编码探针：`build_scripts/构建.ps1:171-190` —— `:177` 只跑 `backend/tests/test_utf8_encoding.py`，`:181` 失败时 `Write-Warning-Custom "UTF-8 编码测试失败，但继续构建"`，`:183-184` 异常也只告警；`build_scripts/快速构建.ps1:45-47` 调用构建时同时带 `-SkipTests -SkipClean`，直接跳过整个步骤 3。

   附注：`build_scripts/` 下**不存在** `quick_build.ps1`（实测目录清单），只有中文名脚本；探索阶段曾误报该文件，已更正。

**影响**：后端 100+ 测试文件（`backend/tests/`）、`tox.ini`、`run_tests.py` 全部**没有执行者**。任何回归只能靠人工本地发现。这不是「缺一个功能」，而是 Phase 1 其余各项**无法被守住**——修好的 traversal 与 zip-slip 没有任何机制防止被改回去。

**Phase 1 归属**：minimal CI quality gate（本项是该目标唯一缺失的实现）。

**验收**：根 `.github/workflows/` 下存在工作流，至少 (a) 迁移 `lint.yml` 内容到根目录并删除 `source-code/.github/`，(b) 新增后端 `pytest` 作业，(c) 构建脚本对测试失败改为阻断或显式区分「快速构建」与「发布构建」。

---

## 六、仓库卫生

### R-10 · 构建产物与运行时数据混入版本控制 · 中 / high 置信

**证据**（计数为实测 `git ls-files`）：跟踪文件共 1151；其中 `.pyc` **10 个**（含 `backend/__pycache__/*.pyc`、`build/build_exe/localpycs/*.pyc`）；`source-code/dist/` 11 个 + `source-code/build/build_exe/` 14 个（`.toc`、`.pyz`、`.pkg`、`base_library.zip`、`xref-build_exe.html`、`warn-build_exe.txt`）；`source-code/data/` 整目录被 `source-code/.gitignore:16` 的 `data/` 忽略，**但 8 个文件仍被跟踪**（`core_nodes.json`、`system_prompts.json`、`snapshot_metadata.json`、`prompt/*`、`workflows/*_metadata.json`）。

**当前工作区即处于脏状态**：`git status --short` 实测有 5 个 `.pyc` 显示为 `M`（会话开始时只有这 5 个；随后又出现 9 个源文件改动与 4 个未跟踪文件，见 R-12 与分叉台账）。这会让任何「工作区干净」前置条件失效，也是本次会话开始时 git 快照标注「working-tree cleanliness unknown」的原因。

**影响**：`.gitignore` 与跟踪状态并存 = 状态漂移；每次本地运行都会产生噪声 diff，掩盖真实改动；`data/` 下跟踪文件与运行时写入同名文件，行为随环境变化。

**Phase 1 归属**：repository hygiene。

**验收**：`git ls-files | grep -c '\.pyc$'` 为 0；`dist`/`build` 无跟踪文件；`data/` 的忽略与跟踪二选一，且明确保留哪些为种子数据（注意：这是**有意的 git 移除操作**，须按检查点流程执行，不可与功能改动混在同一提交）。

### R-11 · 构建脚本含破坏性步骤 · 中 / high 置信

**证据**：`build_scripts/构建.ps1` 步骤 2 的清理（由 `:141` `if (-not $SkipClean)` 守卫）——`:148` `Remove-Item -Path $BuildOutputDir -Recurse -Force`（`:46` 定义为 `build_scripts/打包产物_$Version`）、`:155` 删 `$TempDistDir`（`:35` 定义为 `source-code/dist`，即**前端构建输出目录，也正是 R-10 中被 git 跟踪的那 11 个文件所在处**）、`:314` 删 `updater_dist`。

另：`build_scripts/构建runtime包.ps1:100,354` 亦有 `Remove-Item $tempDir -Recurse -Force`，但其目标是临时工作目录，不构成仓库内容风险，列出仅为完整。

`source-code/build_exe.spec`（与 `build_exe_debug.spec` 同行号）在**构建时改写开发环境 venv**：`:193-205` 定位并 patch venv 内已安装的 `webview/platforms/winforms.py`、`:185` `os.remove` 其 `.bak` 备份、`:265` `shutil.rmtree(__pycache__)`。

**影响**：打包不只是「产出」，还会**就地修改开发环境**且难以回退；被改写的 site-packages 源码不受版本控制，构建不可复现。而 `-SkipClean` 与删除 `source-code/dist` 的组合，使「跟踪的产物」与「每次构建抹掉它」同时成立（R-10 × R-11）。

**Phase 1 归属**：hygiene 边缘项；venv 改写属构建可复现性问题，**建议记为 Phase 2**，Phase 1 只需把「破坏性清理」在文档与脚本提示中标明，避免执行 agent 误判为可随意运行。

---

## 七、优先级建议（供执行方案排序）

| 顺序 | 项 | 理由 |
|:---|:---|:---|
| 0 | **R-12 密钥修复收口** | 工作区已有正确实现但未提交；不收口则基线继续带硬编码密钥发布，且与后续提交互相纠缠 |
| 1 | **R-09 CI 门禁** | 其余各项的守门机制；且 `lint.yml` 迁移是纯文件位置修正，成本最低 |
| 2 | **R-01 + R-02 同批修** | 组合成远程可读任意文件；已有实测用例可直接转成回归测试 |
| 3 | **R-04 + R-07 共用一个安全解压实现** | 同一缺陷模式，两处实例，避免修一半 |
| 4 | **R-05 fail-open 改 fail-closed** | 小改动，且现有 `version.json` 已带 hash，不会打断正常发布 |
| 5 | **R-10 卫生收口** | 恢复「工作区干净」前置条件，让 1–4 可被验收 |
| 6 | R-06 决策项 | 需维护者先定 fork 是否自供更新，**不要由 agent 自行选边** |
| 7 | R-03 / R-08 | 降噪与纵深防御，可并入相应批次 |
| — | R-11 venv 改写 | 建议移入 Phase 2，避免与 Phase 1 范围混淆 |

## 八、需要维护者决策的开放项

1. **在途改动归属（最紧急）**：工作区那份密钥存储改造是谁、何时、以何意图发起的？要收进 Phase 1 首个提交，还是先 `git stash`/另开分支隔离？另有 3 个前端残留 `source-code/frontend/.tmp-fe-baseline.json`、`.tmp-fe-after.json`、`.tmp-report.cjs`（均未被忽略），需确认是否可删。
2. **R-12**：固定 Fernet 密钥已公开在仓库历史中，历史记录无法追回；需决定是否要求用户重设 key。
3. **R-06**：本 fork 是否自建更新源，还是明确宣告「不提供自动更新」。
4. **R-10**：`source-code/data/` 下 8 个被跟踪文件是**种子数据**（应保留跟踪并从 `data/` 忽略规则中显式豁免）还是**运行时残留**（应移除跟踪）。
5. **探针脚本**是否固化为仓库回归测试（本次刻意未入库以保持 Phase 1 范围）。
