# 并行科技真实模型测试

测试时间：2026-10-13。本地启动独立 HTTP 服务，使用临时进程环境变量中的用户授权密钥调用并行科技，测试后清除变量和测试会话。密钥未写入仓库。

- 接口：https://llmapi.paratera.com/v1/chat/completions
- 模型：GLM-4-Flash，从账户模型列表确认
- 目标：准备 Python 后端开发面试，安排 4 小时，涵盖 HTTP、数据库和项目复盘
- 最终结果：模型规划 4 个任务，结构校验通过，summarize、checklist、time_budget、review_prompt 全部执行成功；完成率和工具成功率均为 100%
- 会话重新读取：事件与保存前一致
- 规划耗时：13447.07 ms
- 用量：prompt_tokens 389、completion_tokens 263、total_tokens 652
- 密钥检查：服务端返回的会话内容不含测试密钥

初次测试中模型漏掉 depends_on，服务端拒绝计划，并保留模型输出与校验错误。补充完整 JSON 示例及中文输出要求后，最终测试通过。模型输出具有随机性，后续仍可能出现校验失败；系统保留失败记录，不将失败请求标记为成功。

自动验证：15 项 Python 测试通过，浏览器本地模拟的 4 种场景测试通过。

手动真实调用测试脚本为 tests/manual_real_model.py，只有主动执行且配置密钥时才会调用模型，常规单元测试不访问模型接口。

## 线上部署与浏览器测试

2026-10-13 用户授权将同一密钥保存到 Render 服务环境变量。已配置 OPENAI_API_STYLE、OPENAI_BASE_URL、OPENAI_MODEL 和 OPENAI_API_KEY；来源域名配置保留。部署 dep-db6q072j9qps73a2hqg0 成功上线，健康接口返回 model_configured=true。

从 GitHub Pages 前端开启真实模型选项并提交上述面试目标，GLM-4-Flash 返回 4 个任务，通过结构校验。原始输出、依赖图、模型标识和用量均正常展示。响应耗时 17276.64 ms，用量 prompt_tokens=389、completion_tokens=275、total_tokens=664。

逐次点击执行下一步，完成率依次为 25%、50%、75%、100%，最终工具成功率 100%，事件数 4。刷新前端后，真实模型标识、完成率和四次工具调用记录均恢复。密钥保存在 Render，前端无需填写密钥。
