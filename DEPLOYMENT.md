# 公网部署验证记录

日期：2026-10-13

前端：https://wushenghao666.github.io/ai-learning-week5-agent-dashboard/
后端：https://ai-learning-week5-agent-dashboard.onrender.com
Render 服务：srv-db6oefuk1f9s73atc2pg，Python 3，Free，每月 0 美元实例。
Render 部署提交：f213f872b9d5b28a8dcf68f71a4446d6b559bd64。

已完成：

- Render 控制台显示 Deploy succeeded / Live。
- /api/health 返回 HTTP 200，ok 为 true，model_configured 为 false。
- GitHub 变量 AGENT_API_BASE 已指向 Render 服务，Pages 工作流 38331716721 成功。
- tests/smoke_deployed.py 对四类独立测试会话验证：CORS、无 Key 模拟模式、25% 到 100% 分步执行、时间预算、四次成功事件、刷新恢复、会话隔离、OPTIONS 预检和清空。
- 浏览器实际操作作品集示例：显示模拟警告，四个按钮操作后完成率 100%、工具成功率 100%、事件数 4，时间预算为 8 小时分为 4 天。
- 测试会话使用随机编号，API 测试结束后清空各自的会话。浏览器保留一份完成示例供查看。

尚未完成：

- OPENAI_API_KEY 未配置，未进行真实模型付费请求验证。
- 请在 Render Environment 添加 Key 并保存重新部署，再检查健康接口和模型规划模式。
- 模型调用会产生 OpenAI API 费用；免费仅指托管实例。
- Render 免费实例休眠或重启后临时文件会丢失。
