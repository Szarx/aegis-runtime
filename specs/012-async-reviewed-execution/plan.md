# SPEC-012 方案

先维护取消/确认表，不改现有审批协议/数据库/前端。将ReviewedTool中纯配置/参数准备拆为私有公共基类；同步类型限制保留。AsyncReviewedTool只接受async函数，原始工具在调用者任务内await，边界检查点传递取消，取消不发failed确认。

AsyncReviewedClient复用011纯配置/响应绑定校验，HTTPX只在构造时可选导入；原生异步流与asyncio.timeout限制整个请求，固定连接池/关闭责任，禁止后台重试。成功/错误确认与取消区分，父上下文由原生await保留。

先做确定性AsyncTransport和Task取消测试，再用真实回环HTTP/Uvicorn/PostgreSQL验证已提交领取的响应丢失和原子并发；按受影响范围回归同步Runtime与数据库。提供无LLM的async示例，完成wheel/可选依赖隔离和原OpenAPI/迁移不变检查，回写证据。
