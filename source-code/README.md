# `source-code/` 目录说明

> 本文件**只做源码目录导航**。产品功能介绍、系统要求和用户 FAQ 的唯一来源是仓库根的 [`README.md`](../README.md)；
> 架构、命令、约定与调试方法见 [`CLAUDE.md`](../CLAUDE.md)；打包发布见 [`build_scripts/打包说明.md`](build_scripts/打包说明.md)。
> 请勿在本文件里复制产品章节（规则见 [`README更新规范.md`](README更新规范.md)）。
>
> Last verified: 2026-11-01（对照 commit `6e3c986`，目录清单来自 `ls -d source-code/*/` 与 `git ls-files` 实测）

## 该看哪个文档

| 你想了解 | 去这里 |
|:---|:---|
| 这个产品能做什么、怎么装 | `../README.md` |
| 前后端结构、关键命令、编码约定、调试与日志 | `../CLAUDE.md` |
| 构建 / 发布 exe | `build_scripts/打包说明.md` |
| README 该怎么写、什么时候该更新 | `README更新规范.md` |

## 目录结构（实测）

```
source-code/
├── frontend/            # React 19 + TypeScript + Vite 7 桌面端界面（npm run build → ../dist/）
├── backend/             # Python 3.12.x + pywebview + Flask 后端，入口 main.py
│   ├── src/bridge/      # 暴露给前端的 class Api 与 controllers/
│   ├── src/core/        # env / plugin / marketplace / ai / dependency / cache / updater ... 业务服务
│   ├── src/utils/       # logger、paths、git_config、mingit_downloader 等
│   ├── tests/           # pytest 套件（配置见 backend/pyproject.toml）
│   ├── requirements.txt / requirements-test.txt / tox.ini
│   ├── MinGit-2.53.0-64-bit/   # 仅配置骨架，无 git.exe
│   └── updater/         # 独立更新器（updater.spec）
├── dist/                # 前端构建产物（开发模式下由后端托管；不入库）
├── build/               # PyInstaller 中间产物（不入库）
├── build_scripts/       # 构建/发布脚本与 打包说明.md
├── hooks/               # PyInstaller hook 文件（hook-onnxruntime.py 等），不是 Git hooks
├── scripts/             # 开发辅助脚本：init_project.py、set_app_icon.py、generate_version_json.py、
│                        #   extract_comfyui_nodes.py、diagnose_system.bat
├── tools/               # 环境/依赖诊断：check_system_dependencies.(ps1|bat)、deep_check_dependencies.bat、diagnose_pythonnet.(ps1|bat)
├── assets/              # 图标等源资源
├── data/                # 运行数据（含 ai_assistant.db 等，由 backend/src/utils/paths.py 定位）
├── logs/                # 运行日志 comfynexus_<时间戳>.log（不入库）
├── cache/               # 缓存（不入库）
├── lora_data/           # LoRA 扫描数据（不入库）
├── backup/              # 快照/备份（不入库）
├── build.ps1            # 完整构建入口（参数见 打包说明.md）
├── quick_build.ps1      # 交互式打包入口（无参数）
├── comfy_nexus_version.py  # 版本号唯一来源（__version__）
└── pre_build_check.py   # 构建前置检查
```

## 从零跑起来

```powershell
# 0) 仓库根提供了 start_dev.bat（当前写死了本机绝对路径，换机器需自行修改）

# 1) 前端：必须先构建，开发模式下后端托管的就是 source-code/dist/
cd source-code/frontend
npm ci
npm run build          # 或 npm run dev 起 Vite 开发服务器

# 2) 后端：Python 3.12.x（本机用 3.12.3）
cd ../backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py

# 3) 测试
pip install -r requirements-test.txt
python -m pytest -o addopts="" -q tests          # 全量（离线、无网络依赖）
python -m pytest -o addopts="" -q tests/unit     # 仅单元测试
```

首次启动会进入 Git 引导窗口：自动下载便携版 MinGit 2.53.0.2，或指定你已有的系统 Git（仓库内的 `MinGit-2.53.0-64-bit/` 不含可执行文件）。

## 需要知道的现状

- **开发模式看的是 `source-code/dist/`**：改完前端必须重新 `npm run build`，桌面窗口才会更新；只开 `npm run dev` 时改的是浏览器里的页面。
- **`npm run test` 是 watch 模式**，一次性验证请用 `npm run test:run`。
- **全量打包脚本要求 `source-code/.venv`**，与开发用的 `source-code/backend/.venv` 不是同一个目录，详见 `build_scripts/打包说明.md` 的"注意事项"。
- **应用自动更新默认关闭**（`backend/src/core/settings_manager.py` 的 `general.autoUpdate = false`），且当前设置界面没有对应开关。
- 构建产物（`dist/`、`build/`、`backend/{build,dist}/`、`frontend/coverage/`、`frontend/tsconfig.tsbuildinfo`）**不纳入版本控制**，规则见 `../CLAUDE.md` 第 7 节。
