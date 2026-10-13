# 第五周：把学习 Agent 做成可视化 Web 应用

本项目在第四周持久化学习 Agent 的基础上增加本地 Web 控制台。浏览器页面可以创建学习目标、查看任务依赖、逐步执行工具、观察完成率和工具调用时间线。服务端仍然使用 Python 标准库，数据保存到 `outputs/session.json`，关闭页面后再次打开可以恢复会话。

## 功能

- 在网页输入学习目标，调用第四周 Planner 生成四个带依赖的任务
- 通过任务卡片显示状态、工具、前置任务、尝试次数和结果
- 点击执行下一步，只运行当前满足依赖的任务，并把事件写回会话文件
- 查看完成率、工具成功率、可执行任务数量和事件数量
- 显示工具调用时间线和复盘建议
- 提供清空会话操作，便于重新演示
- 不依赖第三方 Python 包，不联网调用模型；`--llm` 仍可由命令行显式启用第四周的模型规划回退逻辑

## 快速开始

```powershell
cd 'C:\Users\wushe\Documents\ChatGPT\week 5\ai-learning-week5-agent-dashboard'
python -m src.web
```

打开 <http://127.0.0.1:8000>。也可以运行命令行测试：

```powershell
python -m unittest discover -s tests -v
```

## 页面操作流程

```text
输入目标
  ↓
POST /api/init
  ↓
任务卡片 + 依赖关系 + 指标
  ↓
点击执行下一步
  ↓
POST /api/run，运行当前 ready task
  ↓
保存 outputs/session.json，刷新后恢复
```

后端接口只有三个写操作：`/api/init` 创建计划，`/api/run` 执行可运行任务，`/api/reset` 删除当前会话。`GET /api/session` 返回页面所需的完整状态，包括任务、事件、复盘指标和可执行任务编号。静态资源由同一个 `ThreadingHTTPServer` 提供。

## 目录结构

```text
ai-learning-week5-agent-dashboard/
├─ src/
│  ├─ agent.py       # 第四周的初始化、执行和复盘
│  ├─ memory.py      # Session、Task、Event 持久化
│  ├─ planner.py     # 目标拆解和依赖
│  ├─ tools.py       # 本地工具和参数校验
│  └─ web.py         # HTTP API 与静态文件服务
├─ web/
│  ├─ index.html     # 页面结构
│  ├─ app.js         # 请求、渲染和交互
│  └─ styles.css     # 响应式样式
├─ tests/
├─ outputs/
├─ examples/
├─ blog/
├─ requirements.txt
└─ README.md
```

## 设计说明

页面没有复制一套新的 Agent 状态。每次 API 调用都读取或更新 `Session`，所以命令行和浏览器可以使用同一份 JSON。依赖判断继续由 `Session.ready_tasks()` 完成，前端只负责展示结果和发送操作。执行错误沿用第四周的两次重试与事件记录，前端能看到失败任务的错误文字。

页面将任务状态用颜色和徽标区分：待执行任务显示灰色，已完成任务显示绿色，失败任务显示红色。时间线按最新事件排在前面，事件内容来自 `Event.output` 或 `Event.error`。刷新页面时先请求 `/api/session`，存在会话文件就直接恢复任务和指标。

## 后续方向

当前版本适合单用户本地使用。下一步可以加入任务详情编辑、人工确认按钮、图形化依赖连线和真实模型规划的配置面板。数据格式、工具白名单和执行循环已经保留，后续功能可以围绕这些接口继续扩展。

## 线上部署：GitHub Pages + Render

GitHub Pages 只发布 `web/` 静态文件，Python API 服务部署到 Render。项目提供了 `render.yaml` 和 `.github/workflows/pages.yml`。

### 部署后端

1. 在 Render 创建 Web Service，连接本仓库并使用 `render.yaml`。
2. 在 Render 环境变量中设置 `OPENAI_API_KEY`，可选设置 `OPENAI_MODEL`。
3. 将 `AGENT_ALLOWED_ORIGIN` 设置为 GitHub Pages 的完整地址，例如 `https://用户名.github.io`。
4. 访问后端 `/api/health`，确认 `model_configured` 为 `true`。

Key 只存在 Render 的环境变量中。不要把 Key 写入 `web/config.js`、前端代码、GitHub Secrets 以外的文件或请求 URL。

### 部署前端

1. 在仓库 Settings → Pages 中选择 GitHub Actions。
2. 在仓库 Variables 中增加 `AGENT_API_BASE`，值为 Render 后端地址，例如 `https://ai-learning-week5-agent.onrender.com`。
3. 推送到 `main`，工作流会把 `web/` 发布到 GitHub Pages，并生成指向后端的 `config.js`。

页面的使用真实大模型规划开关会向 `/api/init` 发送 `use_llm: true`。后端读取自己的 `OPENAI_API_KEY` 调用 Responses API。没有 Key 或模型请求失败时，接口返回错误，页面不会静默改用规则规划。

### 无 API Key 时的模拟模式

打开网页中的使用真实大模型规划后，后端会先检查 `OPENAI_API_KEY`。没有配置时，页面使用本地规则规划作为模拟模型，并显示橙色提示，说明没有发生真实模型调用。页面中的四个示例可以分别演示学习计划、项目计划、面试准备和读书笔记整理。每个示例都会返回目标摘要、学习清单、时间预算和复盘提醒。

这套模拟模式用于演示页面和 Agent 执行流程，不产生 OpenAI API 费用。配置 Key 后，同一个开关会改为调用真实模型，模型结果仍然经过工具白名单和依赖校验。
