> 适用范围：ComfyNexus 桌面端（`source-code/backend` + `source-code/frontend`）的日常回归与发版前验收。维护方式：功能、门禁或基线变化时同步更新本文对应章节，并在文末版本记录追加一行。

# ComfyNexus 标准测试方案

| 项 | 内容 |
|---|---|
| 文档名称 | ComfyNexus 标准测试方案 |
| 版本 | v1.0 |
| 基线日期 | 2026-11-04 |
| 适用产品 | ComfyNexus（Windows 桌面端） |
| 配套文档 | [测试用例索引](testCase/README.md)、[问题模板索引](issue/README.md) |

## 版本记录

| 版本 | 日期 | 变更说明 |
|---|---|---|
| v1.0 | 2026-11-04 | 首版：按当前单机环境、现有自动化能力与 `quality.yml` 门禁编写 |

## 一、文档目的

为 ComfyNexus 的日常改动、发版前验收和缺陷回归提供一套**当前环境可执行**的测试依据，明确：

- 测什么、不测什么；
- 用哪些层次的手段测；
- 什么条件可以进入测试、什么结果才算通过；
- 发现问题后如何分级、记录和关闭。

本文不承担项目管理职责，不包含人员排期、工时估算和硬件采购内容。

## 二、项目概述

ComfyNexus 是 ComfyUI 的 Windows 管理平台，采用「单 Python 进程 + WebView2 界面」结构：

| 层 | 技术 | 位置 |
|---|---|---|
| 桌面宿主 | Python 3.12 + pywebview（EdgeChromium/WebView2） | `source-code/backend/main.py` |
| 本地服务 | Flask 回环静态服务（127.0.0.1，5000 起探测） | `source-code/backend/src/utils/http_server.py` |
| 前端 | Vite 7 + React 19 + TypeScript + TailwindCSS + Zustand + i18next | `source-code/frontend` |
| 前后端通道 | `window.pywebview.api`（`source-code/backend/src/bridge/api.py` 公共方法自动暴露） | 仅窗口内 JS 可调用 |
| 媒体通道 | Flask `/gallery/thumbnail/<id>`、`/gallery/asset/<id>` 等只读路由 | 回环 HTTP |
| 外部进程 | ComfyUI 子进程（默认 127.0.0.1:8188）、更新器 onefile | 由后端拉起 |

核心业务模块：资产库（Gallery）、提示词库（Prompt）、工作流（Workflow）、系统设置、自动更新、窗口与图标、AI Key 安全、启动日志。

## 三、测试目标

| 目标 | 可度量口径 |
|---|---|
| 主流程可用 | P0 用例执行率 100%、通过率 100%；P1 用例通过率 ≥ 95% |
| 类型安全 | `npx tsc --noEmit` 0 error（阻断项） |
| 后端逻辑正确 | `pytest tests/unit` 全部通过（阻断项），允许既有 skip |
| 质量不倒退 | ESLint、vitest 失败数不高于本文记录基线（报告项） |
| 数据不丢 | 扫描、保存、更新、密钥迁移相关 P0 用例全部通过 |
| 缺陷闭环 | 发版前 S1/S2 未关闭数为 0 |

## 四、测试参考文档

| 来源 | 用途 |
|---|---|
| [《一篇完整的测试方案怎么写》](https://blog.csdn.net/cae_520_ww/article/details/130968828)（已抓取） | 本文章节骨架：目的、概述、目标、范围、环境、规模、方法、准出、交付、风险 |
| [《七大测试用例设计方法与案例分析》](https://blog.csdn.net/ouihsiad/article/details/125768506)（已抓取） | 用例设计方法：等价类、边界值、判定表、场景法、错误推测、因果图、正交表 |
| `docs/architecture/current-architecture.md` | 进程边界、通道与模块职责 |
| `.github/workflows/quality.yml` | 阻断项与报告项的唯一事实来源 |
| `docs/test/testCase/README.md` | 用例编号、字段与优先级定义 |
| `docs/test/issue/README.md` | 缺陷分类、分级与流转 |

## 五、测试范围

### 5.1 测试范围

| 模块 | 覆盖内容 | 用例文件 |
|---|---|---|
| 资产库 | 扫描（增量/全量）、筛选排序、分类树、批量操作、影院模式、详情面板、缩略图/原图路由、导入导出、转提示词库 | `01-资产库.md` |
| 提示词库 | 增删改查、分类、搜索排序、收藏、复制、导入导出、图片、从资产库转入 | `02-提示词库.md` |
| 工作流 | 导入导出、列表/文件夹、批量、预览、节点统计、插件解析 | `03-工作流.md` |
| 设置与自动更新 | 设置读写、主题/语言/窗口、代理、Git、检查/下载/校验/应用更新 | `04-设置与自动更新.md` |
| 安全与密钥 | Key 掩码、加密落盘、迁移、密钥文件损坏、CORS、路径穿越 | `05-安全与密钥.md` |
| 窗口、图标与启动 | 冷启动、单实例、窗口状态、托盘、图标回退、启动日志 | `06-窗口图标与启动.md` |
| 通用 UI 与布局 | 路由、主题、i18n、404、Toast/Dialog、缩放布局、全屏 chrome | `07-通用UI与布局.md` |

### 5.2 不测范围（明确排除）

| 不测项 | 原因 |
|---|---|
| ComfyUI 本体、模型推理质量、采样效果 | 外部项目，本项目只做进程管理与页面承载 |
| 插件市场第三方插件内容与安全性 | 内容由第三方提供，仅验证列表/安装流程 |
| Linux / macOS / 移动端 | 产品仅支持 Windows |
| 多浏览器、多分辨率、多显卡矩阵 | 当前只有单台工作站，无真机矩阵 |
| 高并发、压测、长时间疲劳测试 | 单用户桌面应用，无并发入口 |
| 安装包代码签名、公证、发布渠道合规 | 不在本轮范围 |
| 网络运营商差异、真实第三方 API 可用性 | 只能做失败分支与 mock 验证 |
| 依赖安装的最终网络结果 | 受镜像/网络影响，只验证流程与错误提示 |
| 数据库级性能与大数据量基准 | 资产库为 JSON 全量读写，仅做规模冒烟 |
| 未提交/未合入改造的半成品功能 | 以工作区可运行状态为准，缺陷按问题模板登记 |

## 六、测试环境与现有条件

### 6.1 实际环境

| 项 | 实际值 |
|---|---|
| 操作系统 | Windows 11 专业工作站版（单机） |
| 显卡 | RTX 6000D（计算卡，无视频输出；桌面显示由核显/主板输出） |
| Python | 3.12.3（`source-code/backend/.venv`，必须 3.12） |
| Node / npm | 本机 v23.9.0 / 10.9.2；CI 使用 Node 20 |
| 后端服务 | 127.0.0.1，5000–5099 自动探测可用端口 |
| ComfyUI | 127.0.0.1:8188（由后端拉起，不在线时相关功能应降级） |
| 前端开发模式 | `http://localhost:4173`（Vite 监听 `::1`；不要用 `127.0.0.1:4173`） |
| 浏览器自动化 | Playwright `channel: 'msedge'`；首屏截图前等待 ≥ 11 秒 |
| 测试机 | 无独立测试机，与开发机同机 |
| 测试人员 | 无专职测试人员，采用「用户提需求与验收 / Agent 实现与自查」 |

### 6.2 启动前提

| 前提 | 检查方式 |
|---|---|
| 后端依赖已装（含 setuptools，GPUtil 需要 distutils） | `pip show setuptools` |
| `settings.json` 的 `git.mode=system` | 内置 MinGit 缺少可用 `git.exe` |
| 前端构建产物存在 | `source-code/dist/` 存在且含 `index.html` |
| 端口空闲 | 5000 起无占用；8188 由 ComfyUI 使用 |

### 6.3 现有条件带来的限制

- 只有一台机器，无法验证「另一台机器安装/升级」；单实例、路径、权限相关用例只能做同机双开或临时目录模拟。
- 无专职测试人员，人工验收集中在 P0/P1 与发版前回归；P2 主要靠自动化与抽查。
- jsdom 下 `useElementSize` 恒为 0，网格/虚拟列表类断言必须 mock 尺寸。
- 前端历史单测存在失败基线，故 vitest 只能做「不倒退」判断，不能作为阻断项。

## 七、测试规模（功能点清单）

| 模块 | 主要功能点 | 用例数（计划） | 自动化倾向 |
|---|---|---|---|
| 资产库 | 扫描、筛选、分类、批量、影院、详情、路由、导入导出、转提示词 | 34 | 接口/逻辑可自动化，影院与系统弹窗半自动 |
| 提示词库 | CRUD、分类、搜索排序、收藏、复制、导入导出、图片 | 16 | 高 |
| 工作流 | 导入导出、文件夹、批量、预览、节点解析 | 14 | 高 |
| 设置与自动更新 | 设置读写、外观、窗口、代理、更新链路 | 12 | 中（窗口/更新器半自动） |
| 安全与密钥 | 掩码、加密、迁移、CORS、路径穿越 | 10 | 高 |
| 窗口图标与启动 | 启动、单实例、窗口、托盘、图标、日志 | 9 | 半自动/手工 |
| 通用 UI 与布局 | 路由、主题、i18n、弹窗、布局 | 10 | 中 |
| 合计 | — | 105 | — |

用例编号与字段规范见 `testCase/README.md`。

## 八、角色与协作方式

| 角色 | 职责 |
|---|---|
| 用户 | 提出需求与验收标准；确认交互/排版；在真实桌面环境中做最终验收；决定发版 |
| Agent | 阅读代码与文档；实现改动；编写/维护用例与问题单；执行自动化检查；给出基线与结论 |

协作约定：

1. 需求变更先落到用例或问题单，再改代码。
2. Agent 完成改动后必须给出：改动文件、执行的命令、实际结果（通过数/失败数）。
3. 涉及数据格式、密钥、更新链路的改动，必须附回归用例编号。
4. 用户验收以 P0 用例 + 界面实际效果为准，不以 Agent 自述为准。

## 九、测试工具

| 工具 | 版本/来源 | 用途 |
|---|---|---|
| pytest | `requirements-test.txt` | 后端单元测试 |
| vitest + Testing Library + fast-check | 前端 devDependencies | 前端单元/属性测试 |
| TypeScript `tsc` | 5.9.x | 类型检查（阻断） |
| ESLint | 9.x | 代码规范（报告） |
| Playwright（msedge） | 本机/Agent 环境 | 浏览器开发模式 UI 冒烟与截图 |
| Flask test client / `Invoke-WebRequest` | 内置 | HTTP 路由与安全检查 |
| Git | system 模式 | 差异、回归范围判断 |

## 十、测试方法与分层策略

### 10.1 分层总览

| 层级 | 对象 | 手段 | 触发时机 | 是否阻断 |
|---|---|---|---|---|
| L1 静态检查 | TS/TSX 类型 | `npx tsc --noEmit` | 每次提交/PR | 是 |
| L1 静态检查 | 代码规范 | `npm run lint` | 每次提交/PR | 否（报告） |
| L2 单元测试 | Python 纯逻辑、解析、加密、更新加固 | `pytest tests/unit` | 每次提交/PR | 是 |
| L2 单元测试 | React store/组件/属性 | `npx vitest run` | 每次提交/PR | 否（报告） |
| L3 桥契约 | `window.pywebview.api` 方法名、入参、返回结构、掩码 | 契约清单 + 手工/脚本比对 | 桥方法新增或改名时 | 是（新增/改名必须同步前端） |
| L4 HTTP 路由 | 静态文件、`/gallery/*`、`/prompt/images/*`、CORS、路径穿越 | Flask test client / `Invoke-WebRequest` | 路由变更时 | 是（安全类） |
| L5 UI 冒烟 | 启动、路由、主流程 | Playwright（dev 模式）+ 手工 | 发版前 | 是（P0） |
| L6 回归 | 受影响模块 + 固定 P0 集 | 用例回归 + 自动化 | 每次修复后 | 是 |

### 10.2 静态检查

- `tsc`：0 error 才可合并；工作区若因未完成改造报错，必须先修复或移出改动范围。
- ESLint：当前为报告项，仅要求「不高于基线」，新增文件不得新增 error。

### 10.3 单元测试

- 后端：覆盖 `tests/unit`（gallery、prompt_library、workflow、updater、secret_store、http_server、icon/window、settings）。
- 前端：覆盖 store、组件、属性测试；允许使用 `fast-check` 做不变量验证。
- 失败处理：vitest 既有失败不阻断，但**本次改动相关文件**的用例必须通过。

### 10.4 桥契约测试

桥是本项目最容易「改后端忘前端」的位置。每次新增/改名公共方法必须核对：

| 检查点 | 要求 |
|---|---|
| 方法可被前端调用 | `Api` 公共方法（非下划线） |
| 方法名一致 | 前端 `window.pywebview.api.<name>` 与后端 `def <name>` 完全一致 |
| 返回结构一致 | 前端按 `success/error_message/data` 或既有字段读取 |
| 敏感字段 | 返回体中不得出现明文 `api_key`，只允许 `api_key_masked`/`has_api_key` |
| 列表/字符串兼容 | 上传图片等参数在桥层做过 `list → str` 归一 |

### 10.5 HTTP 路由测试

| 路由 | 验证点 |
|---|---|
| `/`、`/<path:path>` | 返回前端静态资源；不存在 JS/TS 返回 404，不回退 `index.html` |
| `/gallery/thumbnail/<id>`、`/gallery/asset/<id>` | 200 + 正确 Content-Type；无缩略图回退原图；视频支持 Range；不存在返回 404 固定文案 |
| `/prompt/images/<filename>`、`/workflow/previews/<filename>` | 正常返回；非法文件名/越界返回 404 |
| CORS | 仅放行 `http://127.0.0.1` 与 `http://localhost` 的任意端口；不返回 `*` |
| 路径穿越 | `..`、`%2e%2e`、反斜杠、盘符、NUL、绝对路径均 404 |

### 10.6 UI 冒烟与手工验收

固定冒烟路径（每次发版前）：

1. 启动到首页，侧边栏可见。
2. 进入资产库，选择测试目录，增量扫描完成。
3. 打开详情、切换筛选、进入/退出影院。
4. 进入提示词库，新建并保存一条提示词。
5. 进入工作流，导入一个 JSON 并打开详情。
6. 打开设置，切换主题并保存。
7. 关于页检查更新（无更新时可接受）。

浏览器开发模式约定：

- 地址：`http://localhost:4173`；
- Playwright：`channel: 'msedge'`；
- 无 `window.pywebview` 时 store 走 `src/mocks/*` mock 数据，不能据此判断真实后端行为；
- 首屏渲染慢，截图前等待 ≥ 11 秒。

### 10.7 回归策略

| 改动类型 | 必跑 |
|---|---|
| 前端 UI/store | `tsc` + 相关 vitest + 对应模块 P0/P1 + 通用 UI 冒烟 |
| 后端 gallery | `pytest tests/unit` + 资产库全部 P0 + 扫描/批量/路由用例 |
| 后端 prompt/workflow | `pytest` + 对应模块 P0 + 导入导出用例 |
| 密钥/更新/HTTP | `pytest` + 安全模块全部用例 + 更新链路用例 |
| 打包/启动 | 冷启动、单实例、图标、日志、设置读写 |

## 十一、测试数据与 Mock 策略

### 11.1 测试数据

| 数据 | 用途 | 生成方式 |
|---|---|---|
| 临时资产库目录 | 扫描/分类/导入导出 | `%TEMP%\cn-gallery-<随机>`，禁止直接使用真实资产库 |
| PNG（含 `workflow` 文本块） | 工作流提取、参数解析 | 用 ComfyUI 导出的 PNG，或脚本写入 tEXt/iTXt |
| JPG/WebP/MP4/WebM | 类型筛选、缩略图、Range | 小体积样本，文件名含空格/中文/超长名各一份 |
| 损坏图片/0 字节文件/不支持后缀 | 异常分支 | 临时生成 |
| 工作流 JSON | 导入、节点统计 | UI 格式（含 `nodes/links`）与 API 格式各一份；另备非法 JSON |
| 提示词导出 JSON | 导入导出往返 | 先导出再导入，验证分类/重名映射 |
| 假 API Key | 掩码、加密、迁移 | `sk-test-1234567890abcdef` 等固定值，禁止使用真实 Key |
| 假更新包 | SHA256/zip-slip/解压上限 | 单测内用 `zipfile` 构造，禁止下载真实发布包 |

### 11.2 Mock 与降级

| 场景 | 策略 |
|---|---|
| 纯浏览器开发模式（无 pywebview） | store 自动走 `src/mocks/asset`、`src/mocks/prompt` 等静态数据；只验证渲染与交互，不验证持久化 |
| jsdom 布局 | `useElementSize` /`ResizeObserver` 返回 0，网格列数、虚拟列表必须 mock 尺寸 |
| Radix Select/Dialog | `setup.ts` 已补 Pointer Capture、`scrollIntoView`、`ResizeObserver`；断言中文文案前锁定 `zh-CN` |
| ComfyUI 8188 不在线 | 插件状态/工作区应给出可理解的错误或降级，不允许白屏 |
| 网络失败/代理失败 | 用 mock 或断网，验证提示与重试，不验证真实服务商 |
| 更新服务不可用 | 单测桩替换网络层，只验证分支 |

### 11.3 数据安全

- 测试前备份 `source-code/data/`、`source-code/backend/config/`；
- 测试结束删除临时目录与假密钥；
- 不得把真实资产库、真实 Key、真实更新包提交到仓库。

## 十二、进入与准出标准

### 12.1 进入标准（开始测试前必须满足）

| # | 条件 | 判定 |
|---|---|---|
| 1 | 代码可编译，`npx tsc --noEmit` 无 error | 阻断 |
| 2 | 后端 `pytest tests/unit` 通过 | 阻断 |
| 3 | 前端可构建（`npm run build`）且 `source-code/dist/` 更新 | 阻断 |
| 4 | 应用可冷启动到首页 | 阻断 |
| 5 | 改动涉及的文件有对应用例或明确手工步骤 | 阻断 |
| 6 | 数据/密钥/更新相关改动已说明兼容与回滚方式 | 阻断 |

### 12.2 准出标准（发版前必须满足）

| # | 条件 | 判定 |
|---|---|---|
| 1 | P0 用例执行率 100%、通过率 100% | 阻断 |
| 2 | P1 用例通过率 ≥ 95%，未通过项有已登记问题单 | 阻断 |
| 3 | `tsc` 0 error；`pytest tests/unit` 全通过 | 阻断 |
| 4 | ESLint error 数 ≤ 770、warning 数 ≤ 1215（2026-11-04 实测基线） | 报告 |
| 5 | vitest 失败数不多于基线（2026-11-04 实测 545–547 failed / 1277–1279 passed / 4 skipped），且改动相关用例通过 | 报告 |
| 6 | 无未关闭的 S1/S2 | 阻断 |
| 7 | 用户完成界面验收并确认 | 阻断 |

### 12.3 与 `quality.yml` 的映射

| 工作流步骤 | 现状 | 本文对应 |
|---|---|---|
| `npx tsc --noEmit` | 阻断 | 12.1-1、12.2-3 |
| `npm run lint` | `continue-on-error: true` | 12.2-4 报告项 |
| `npm run test:run`（vitest） | `continue-on-error: true` | 12.2-5 报告项 |
| `python -m pytest tests/unit` | 阻断 | 12.1-2、12.2-3 |

> 说明：`quality.yml` 注释中的 ESLint/vitest 基线（811/1252、548/1244）是 2026-11-01 的旧值；2026-11-04 实测：ESLint 770 errors / 1215 warnings，vitest 1277–1279 passed / 545–547 failed / 4 skipped（两次复跑结果有 ±2 波动），后端 209 passed / 2 skipped，`tsc --noEmit` 通过。后续每次更新基线需同步本节、12.2 与版本记录。

## 十三、基于风险的测试优先级

| 风险等级 | 判定 | 典型模块 | 用例优先级 |
|---|---|---|---|
| 高 | 可能丢数据、泄密、无法启动/更新 | 扫描清空元数据、密钥迁移、更新校验、启动 | P0 |
| 中 | 主流程不可用但有替代路径 | 提示词/工作流导入导出、批量操作、影院 | P1 |
| 低 | 体验、文案、边缘输入 | 排序细节、极端尺寸、提示文案 | P2 |

已知高风险点及其用例映射：

| 风险 ID | 风险点 | 对应用例 |
|---|---|---|
| R-GAL-01 | 全量扫描 `clear_all_data()` 清空收藏/标签/评分/描述 | TC-GAL-004/005 |
| R-GAL-02 | `stop_scan()` 设类属性，扫描循环读实例属性，可能停不掉 | TC-GAL-006 |
| R-GAL-03 | 批量收藏逐个 `toggleFavorite`，已收藏会被取消 | TC-GAL-020 |
| R-GAL-04 | `Asset.to_dict()` 不输出 `scheduler`，保存即丢字段 | TC-GAL-033 |
| R-GAL-05 | `gallery_get_workflow()` 用 PIL 打开，视频资产无法导出工作流 | TC-GAL-032 |
| R-GAL-06 | `KSamplerAdvanced` 的 `widgets_values` 索引与 KSampler 不同，参数错位 | TC-GAL-034 |
| R-GAL-07 | `assets.json` 全量覆盖写，无原子写/备份，解析失败退化为空数据 | TC-GAL-010 |
| R-GAL-08 | 影院模式修改全局 chrome，离开页面可能不复位 | TC-GAL-026 |
| R-GAL-09 | 增量扫描用 NSFW 结果覆盖 `tags`，手填标签被冲掉 | TC-GAL-002 |
| R-SEC-01 | 密钥文件损坏/旧明文 Key 迁移失败 | TC-SEC-006/007 |
| R-SET-01 | 官方通道缺少有效 `file_hash` 时拒绝下载；开发通道跳过校验 | TC-SET-010/011 |
| R-WF-01 | 工作流导入只接受含 `nodes` 数组的 UI 格式 JSON | TC-WF-002/003 |

## 十四、缺陷分级与管理流程

### 14.1 严重程度

| 级别 | 定义 | 示例 |
|---|---|---|
| S1 致命 | 无法启动、数据丢失、密钥/更新安全失效、主流程完全不可用 | 启动白屏、全量扫描清空收藏、更新包未校验 |
| S2 严重 | 核心功能错误且无替代路径，或有数据不一致 | 批量收藏反向取消、停止扫描无效、视频工作流导出必然失败 |
| S3 一般 | 有替代路径或影响局部 | 某筛选组合结果偏差、个别文案错误 |
| S4 建议 | 体验/可维护性改进，不影响正确性 | 影院退出后侧栏需手动恢复 |

### 14.2 优先级

| 优先级 | 处理要求 |
|---|---|
| P0 | 立即修复，修复前不合并/不发版 |
| P1 | 当前迭代修复，发版前必须有结论 |
| P2 | 可排入下一迭代，登记后不阻塞 |
| P3 | 择机处理 |

### 14.3 流程

```
新建（BUG/OPT）
  → 确认（复现 + 定级 + 关联用例）
  → 处理中（修复/实现 + 自查）
  → 待验证（附证据与回退说明）
  → 关闭（回归通过）
       ↘ 重开（回归失败或问题复现）
```

规则：

- 新建问题必须附环境、版本、复现率、步骤、实际/期望、证据；缺证据不进入「处理中」。
- 修复提交必须写关联问题编号；同一提交只解决一个问题域。
- 关闭前必须执行「关联用例 + 同模块 P0 回归」。
- 问题单模板见 `docs/test/issue/bug模板.md`、`docs/test/issue/优化模板.md`。

## 十五、可重复执行命令清单

> 以下命令均在 PowerShell 中执行；后端命令工作目录为 `source-code/backend`，前端命令工作目录为 `source-code/frontend`。

### 15.1 后端

```powershell
# 单元测试（阻断项）
.venv\Scripts\python.exe -m pytest tests/unit -o addopts="" -q -p no:cacheprovider

# 单模块
.venv\Scripts\python.exe -m pytest tests/unit/gallery -o addopts="" -q -p no:cacheprovider
.venv\Scripts\python.exe -m pytest tests/unit/core/ai -o addopts="" -q -p no:cacheprovider

# 启动（需先有 source-code/dist）
.venv\Scripts\python.exe -u main.py
```

### 15.2 前端

```powershell
npm ci
npx tsc --noEmit          # 阻断
npm run lint              # 报告
npx vitest run            # 报告
npm run build             # 产出 source-code/dist
```

### 15.3 UI 冒烟（开发模式，无 pywebview）

```powershell
npm run build
npx vite preview --port 4173
# 浏览器访问 http://localhost:4173 （不要用 127.0.0.1）
```

Playwright 关键参数：`channel: 'msedge'`、首屏等待 ≥ 11 秒、忽略本机 `HTTP_PROXY` 对 `localhost` 的影响。

### 15.4 HTTP 路由抽查

```powershell
# 先确认后端实际端口（默认 5000 起）
Invoke-WebRequest -Uri "http://127.0.0.1:5000/" -UseBasicParsing | Select-Object StatusCode
Invoke-WebRequest -Uri "http://127.0.0.1:5000/gallery/thumbnail/not-exist" -UseBasicParsing
Invoke-WebRequest -Uri "http://127.0.0.1:5000/../backend/config/settings.json" -UseBasicParsing
```

### 15.5 变更影响判断

```powershell
git status --short
git diff --stat
git diff -- source-code/backend source-code/frontend
```

## 十六、交付物与门禁清单

### 16.1 交付物

| 交付物 | 位置 | 说明 |
|---|---|---|
| 测试方案 | `docs/test/ComfyNext标准测试方案.md` | 本文 |
| 用例索引与方法 | `docs/test/testCase/README.md` | 编号、优先级、字段、方法 |
| 模块用例 | `docs/test/testCase/01~07-*.md` | 共 105 条 |
| 问题模板 | `docs/test/issue/README.md`、`bug模板.md`、`优化模板.md` | 含已填示例 |
| 执行记录 | 在问题单/提交说明中留痕 | 命令、通过数、失败数、截图 |

本方案不要求额外产出独立测试报告文档；发版结论以用例执行记录和问题单状态为准。

### 16.2 门禁清单（合并/发版前逐项勾选）

- [ ] `npx tsc --noEmit` 0 error
- [ ] `pytest tests/unit` 全部通过
- [ ] 改动相关 vitest 用例通过，失败总数不高于基线
- [ ] ESLint error ≤ 770、warning ≤ 1215（不新增）
- [ ] 对应模块 P0 用例全部通过
- [ ] 安全、数据格式、更新链路改动已完成专项检查
- [ ] 无 S1/S2 未关闭
- [ ] 用户已完成界面验收

## 十七、风险与限制（非人员类）

| 风险 | 影响 | 应对 |
|---|---|---|
| 前端历史测试失败基线高 | vitest 不能阻断，回归信号弱 | 只对改动相关文件要求通过；逐步清理失败用例 |
| jsdom 无布局 | 网格/虚拟列表/拖拽难以自动断言 | 尺寸 mock + 手工冒烟补充 |
| 单机单环境 | 无法验证跨机器安装、升级、权限差异 | 用临时目录/双开模拟；发版前人工验证一次真实升级 |
| ComfyUI 8188 不可用 | 工作区、插件状态相关界面无法完整验证 | 验证降级提示；必要时用本地桩服务 |
| 更新器为独立 exe | 工作区当前没有 `ComfyNexusUpdater_v1.0.exe`，需 `构建.ps1` 步骤 5.5 产出；自动化难以覆盖真实替换流程 | 单测覆盖解压/校验；具备打包产物后补一次真实升级人工验收；在此之前 TC-SET-009/011/012 定为 P1 |
| 资产库 JSON 无 schema | 旧数据兼容风险 | 用例覆盖旧字段/缺字段/损坏文件导入 |
| 显卡无视频输出 | 多分辨率/多屏验证受限 | 只验证当前分辨率与窗口缩放 |

## 附录 A：已知脆弱点速查

| 模块 | 现象 | 代码位置 | 用例 |
|---|---|---|---|
| 资产库 | 全量扫描前 `clear_all_data()`，收藏/标签/评分/描述丢失 | `source-code/backend/src/gallery/scanner.py:158-159` | TC-GAL-004/005 |
| 资产库 | `stop_scan()` 设置 `GalleryScanner._cancelled`，实例循环读 `self._cancelled` | `scanner.py:53-69`、`scanner.py:175` | TC-GAL-006 |
| 资产库 | 批量收藏调用 `toggleFavorite`，非幂等 | `AssetBatchToolbar.tsx:32-36`；后端已有 `gallery_batch_favorite`（`api.py:7570`） | TC-GAL-020 |
| 资产库 | `to_dict()` 无 `scheduler`，整份 JSON 保存后字段丢失 | `models.py:75-120` | TC-GAL-033 |
| 资产库 | `gallery_get_workflow()` 用 `PIL.Image.open`，MP4/WebM 无法导出 | `controller.py:294-326` | TC-GAL-032 |
| 资产库 | `KSamplerAdvanced` 的 widgets 索引按 KSampler 解析 | `scanner.py:1513-1526` | TC-GAL-034 |
| 资产库 | `save()` 直接覆盖写，无临时文件/备份 | `storage.py:62-76` | TC-GAL-010 |
| 资产库 | 影院模式使用全局 `useChromeStore`，离开页面依赖手动恢复 | `useChromeStore.ts:27-33`、`AssetLibraryPage.tsx:356-362` | TC-GAL-026 |
| 资产库 | 增量扫描更新 `tags` 时不区分来源 | `scanner.py:295-319` | TC-GAL-002 |
| 安全 | `mask_api_key` 长度 < 8 返回 `***` | `security_utils.py:13-38` | TC-SEC-001 |
| 更新 | 官方通道缺少合法 SHA256 即拒绝下载；开发通道跳过 | `update_controller.py:185-207` | TC-SET-010 |

## 附录 B：待确认项

| # | 事项 | 现状 | 确认方式 |
|---|---|---|---|
| 1 | 视频资产的 `hasWorkflow` 何时为真 | 扫描器有 MP4 元数据解析，但导出仍走 PIL | 用一个含 workflow 的 MP4 实测 TC-GAL-032 |
| 2 | 删除非空分类的行为（拒绝 / 子分类上移 / 级联删除） | 前端有删除确认，后端需实测 | TC-GAL-014 执行后回填 |
| 3 | 影院模式离开页面是否真的不复位 | 现有代码在关闭影院时 `showAllChrome()`，但直接路由跳转不触发 | TC-GAL-026 实测后回填 |
| 4 | 更新器真实升级时的回滚行为 | 单测覆盖解压校验，未覆盖替换失败 | 发版前人工升级一次并记录 |
| 5 | 当前工作区 tsc 是否稳定通过 | 本次实测通过；后续改造可能引入报错 | 每次执行后记录 |
| 6 | vitest 实际失败数是否与历史基线一致 | 本次复跑结果见交付说明 | 每次执行后记录 |
| 7 | 更新器 exe 何时具备 | 当前工作区未找到 `ComfyNexusUpdater_v1.0.exe`，构建脚本步骤 5.5 产出 | 执行一次打包后回填；届时将 TC-SET-009/011/012 升回 P0 |
