# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

ComfyNexus 是一个为 ComfyUI 设计的现代化管理平台（仅支持 Windows），采用 React 19 前端 + Python 后端（pywebview 桌面应用）架构。核心目标是治理和优化 ComfyUI 生态：环境管理、版本控制、插件市场、依赖管理、AI 助手、工作流解析等。

**技术栈：**
- **前端**: React 19, TypeScript, Vite, TailwindCSS, Zustand, React Router, Radix UI
- **后端**: Python 3.12+, pywebview, Flask, aiohttp, psutil
- **内置工具**: MinGit 2.53.0（无需用户安装 Git）

## 关键构建命令

### 开发环境

```bash
# 前端开发
cd source-code/frontend
npm ci               # 按 package-lock.json 精确安装（推荐）
npm install          # 安装/更新依赖
npm run dev          # 开发服务器
npm run build        # 生产构建（产物输出到 source-code/dist/）
npm run lint         # ESLint 检查
npm run test:run     # 单次运行 Vitest（CI/验收用）
npm run test         # Vitest watch 模式（本地开发）
npm run test:ui      # Vitest UI 模式
npm run test:coverage  # 覆盖率报告

# 后端开发（需要 Python 3.12+）
cd source-code/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 后端测试
pip install -r requirements-test.txt
python -m pytest                    # 运行所有测试
python -m pytest tests/unit         # 单元测试
python -m pytest tests/integration  # 集成测试
python -m pytest -v -s              # 详细输出
python -m pytest -k "test_name"     # 运行特定测试
pytest --cov=src --cov-report=html  # 覆盖率报告

# 运行主应用（开发模式）
# 首次运行或前端改动后，必须先构建前端（产物在 source-code/dist/）
cd source-code/frontend
npm run build
cd ../backend
python main.py
```

### 生产构建

```powershell
# 从项目根目录执行
.\build.ps1 -Version "1.0.2"

# 可选参数：
# -SkipFrontend  跳过前端构建
# -SkipClean     跳过清理
# -SkipTests     跳过测试
# -VerboseOutput 详细输出

# 快速构建（跳过测试和前端）
.\build.ps1 -SkipTests -SkipFrontend

# 构建产物位于 source-code/build_scripts/打包产物_<版本号>/
```

## 架构设计

### 1. 前端架构 (`source-code/frontend/`)

```
frontend/
├── src/
│   ├── pages/          # 页面组件（与侧边栏菜单一一对应）
│   ├── components/     # 可复用 UI 组件
│   ├── contexts/       # React Context（全局状态）
│   ├── hooks/          # 自定义 React hooks
│   ├── api/            # 与后端 API 的桥接层
│   ├── router/         # 路由配置
│   ├── i18n/           # 国际化配置
│   └── lib/            # 工具函数库
├── main.tsx            # 主窗口入口
└── floating-main.tsx   # 浮动窗口入口（独立应用）
```

**关键约定：**
- **页面与路由**：每个 `pages/` 下的文件对应一个路由，路由配置在 `router/` 中集中管理
- **API 调用**：通过 `window.pywebview.api.<method>()` 调用后端，统一在 `api/` 目录封装
- **状态管理**：全局状态使用 Zustand，局部状态优先使用 React hooks
- **样式规范**：TailwindCSS utility-first，避免内联样式，复用 `components/ui/` 下的基础组件

### 2. 后端架构 (`source-code/backend/`)

```
backend/
├── src/
│   ├── bridge/         # 前端桥接层
│   │   ├── Api.py      # 暴露给前端的主 API 类
│   │   └── controllers/  # 业务逻辑控制器
│   ├── core/           # 核心业务层
│   │   ├── env/        # 环境管理（EnvironmentManager 核心）
│   │   ├── plugin/     # 插件管理
│   │   ├── ai/         # AI 服务（多模型支持）
│   │   ├── dependency/ # 依赖分析与冲突检测
│   │   ├── cache/      # 缓存服务
│   │   └── config/     # 配置管理器
│   ├── utils/          # 工具函数（logger, file_ops, etc.）
│   └── gallery/        # 资产库（图片 NSFW 检测、瀑布流）
├── main.py             # 应用入口
├── MinGit-2.53.0-64-bit/  # 内置 Git（免安装）
└── tests/              # 测试套件
```

**关键约定：**
- **API 暴露规则**：`Api.py` 中仅公开方法暴露给前端，私有属性以 `_` 开头（pywebview 序列化限制）
- **环境管理**：`EnvironmentManager` 是核心，负责 ComfyUI 环境的扫描、验证、配置和启动
- **控制器职责**：`controllers/` 层处理业务逻辑，`core/` 层是纯业务服务，避免循环依赖
- **日志规范**：使用 `backend.src.utils.logger` 的 `app_logger`，支持 emoji 自动替换（Windows 控制台兼容）

### 3. 数据流架构

```
前端组件
   ↓ (window.pywebview.api.method())
Api.py（路由层）
   ↓
Controller（业务逻辑层）
   ↓
Core Service（核心服务层）
   ↓
File/Git/Process（系统层）
```

**示例：**
- 用户点击"启动 ComfyUI" → `EnvironmentController.start_comfy()` → `ProcessManager.start()` → 启动子进程
- 插件市场搜索 → `MarketplaceControllerBridge.search_plugins()` → `CacheService.get()` → 三级缓存（内存/文件/网络）

## 关键模块说明

### 环境管理 (`core/env/`)
负责 ComfyUI 环境的全生命周期管理：
- **EnvironmentManager**: 主入口，协调扫描、验证、启动
- **EnvironmentScanner**: 自动检测目录下的 ComfyUI 安装
- **EnvironmentValidator**: 验证环境有效性（Python、Git、依赖）
- **LaunchArgsBuilder**: 构建启动参数（支持 Flux 预设、极客模式）
- **DependencyDetector**: 检测 Python/PyTorch/CUDA 版本

### 插件管理 (`core/plugin/`)
- **PluginManager**: 安装、更新、启用/禁用插件
- **DependencyAnalyzer**: 分析插件依赖树和版本冲突
- **ConflictDetector**: 检测并标记依赖冲突（严重程度分级）

### AI 助手 (`core/ai/`)
多模型支持（OpenAI, Claude, Ollama, 智谱, 讯飞星火等）：
- **AIService**: 统一 AI 调用接口
- **providers/**: 各模型的适配器（BaseProvider 继承）
- **search/**: 联网搜索（DuckDuckGo, Google）
- **DocumentProcessor**: 文档/图片分析

### 缓存系统 (`core/cache/`)
三级缓存策略（内存 → 文件 → 网络）：
- **CacheService**: 统一缓存入口
- 支持过期策略、手动刷新、按需清理

## 开发注意事项

### 1. 添加新功能时
- **前端页面**：在 `pages/` 下添加 `.tsx` 文件，在 `router/` 注册路由
- **后端 API**：在 `Api.py` 中添加公开方法（非私有），在 `controllers/` 实现逻辑
- **测试**：前端在组件同目录加 `.test.tsx`，后端在 `tests/` 下添加 `test_*.py`

### 2. Git 操作
应用内置 MinGit，通过 `GitManager` 类操作，不要直接调用 `subprocess`：
```python
from backend.src.core.git_manager import GitManager
git_manager = GitManager(repo_path)
git_manager.clone(url)
git_manager.checkout_branch(branch_name)
```

### 3. 进程管理
ComfyUI 启动使用 `ProcessManager`，自动处理端口冲突、进程检测、日志捕获：
```python
from backend.src.core.process_manager import ProcessManager
process_manager.start(python_path, script_path, args, cwd)
```

### 4. 依赖冲突处理
使用 `DependencyAnalyzer` 分析依赖树，`ConflictDetector` 检测冲突：
- 冲突分级：info（无影响）、warning（可能影响）、error（严重冲突）
- 自动生成修复建议（手动 pip install 或 requirements.txt）

### 5. 国际化
- 前端：在 `i18n/locales/` 下添加翻译（中英文必备）
- 使用 `react-i18next` 的 `useTranslation` hook

### 6. 构建与打包
- PyInstaller 配置文件：`build_exe.spec`（发布版）、`build_exe_debug.spec`（调试版）
- 构建脚本会自动：
  1. 构建前端 → 产出到 `source-code/dist/`
  2. 打包后端 → PyInstaller 将 Python 代码打包成 exe
  3. 合并产物 → 最终发布包包含前端静态文件 + exe + 依赖

### 7. 构建产物与版本控制（重要）

**原则：构建产物不入库，发布包通过构建脚本 / Releases 分发。**

- 以下路径均为生成物，**不要提交**：
  - `source-code/dist/`：前端构建输出，同时是开发模式下后端托管的目录
  - `source-code/build/`、`source-code/backend/{build,dist}/`：PyInstaller 中间产物 / 输出
  - `source-code/frontend/coverage/`、`source-code/frontend/tsconfig.tsbuildinfo`
- 构建相关文件只保留源码、`package-lock.json`、`frontend/public/` 静态资源和测试；运行数据与本地配置的入库策略另行评估。
- 克隆后首次运行后端前，必须先 `cd source-code/frontend && npm run build`；否则 `main.py` 找不到 `dist/index.html`，无法进入主界面。
- 修改静态资源请改 `frontend/public/`，不要改 `dist/` 下的拷贝（会被下次构建覆盖）。
- 如果历史提交中已跟踪构建产物，用 `git rm -r --cached <路径>` 移出版本控制（保留本地文件），然后提交；不要用不带 `--cached` 的 `git rm`。
- **不要用 `git ls-files -ci --exclude-standard` 批量清理**：仓库中有刻意强制跟踪的依赖与配置（如 `backend/lib/webview2_netcore/*.dll`），批量操作会误删。只清理上列构建产物路径。
- 防回归：提交前可用 `git ls-files -- 'source-code/dist/**' 'source-code/build/**' 'source-code/frontend/coverage/**' 'source-code/frontend/tsconfig.tsbuildinfo'` 检查，输出必须为空。

## 测试策略

- **前端测试**：Vitest + Testing Library，覆盖 UI 组件和页面逻辑
- **后端测试**：pytest，标记分级：`@pytest.mark.unit`、`@pytest.mark.integration`、`@pytest.mark.slow`
- **属性测试**：使用 hypothesis 进行基于属性的测试（边界场景）
- **CI/CD**：未配置 GitHub Actions，手动构建发布

## 调试技巧

### 前端调试
- 在浏览器 DevTools 中可直接调用后端：`window.pywebview.api.<method>()`
- Vite 开发服务器支持 HMR，修改代码即时生效
- 开发模式下后端托管的是 `source-code/dist/`，改完前端需重新 `npm run build` 才能在桌面窗口看到效果

### 后端调试
- 主入口 `main.py` 顶部有 `SIMULATE_FROZEN = True` 开关，模拟打包环境
- 日志文件位置：`data/logs/app.log`（自动轮转）
- 使用 `app_logger.debug()` 输出调试信息

### 常见问题
1. **端口占用**：检查 8188 端口是否被占用，前端会显示冲突提示
2. **Git 权限**：内置 MinGit 位于 `backend/MinGit-2.53.0-64-bit/`
3. **依赖冲突**：使用 `依赖管理` 页面的冲突检测功能排查

## 代码风格

- **Python**: 遵循 PEP 8，使用类型提示（Type Hints）
- **TypeScript**: 严格模式（`strict: true`），避免 `any` 类型
- **命名约定**:
  - Python: snake_case（函数/变量），PascalCase（类）
  - TypeScript: camelCase（函数/变量），PascalCase（组件/类型）
- **文档字符串**: Python 函数必须有 docstring，复杂逻辑加注释说明
