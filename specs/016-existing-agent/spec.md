# SPEC-016：已有 Agent 接入配方

日期：2026-10-23。目标：用独立文件展示已有 LangGraph Agent 如何接入既有 SDK / Runtime，不新增核心 API、依赖或协议。

原 Agent 模块不导入 Aegis，使用真实 StateGraph / ToolNode 与注入的 OpenAI 客户端、业务工具。适配层在构图前包装客户端/工具，构图后包装图入口；观测和 Runtime allow 保持业务结果与调用次数，deny 在工具副作用前阻止。模型由官方 SDK 的合成 HTTP transport 提供，无真实 Provider 请求，非生产 Agent 或真实模型验收。

提供同步/异步 CLI，运行 baseline、observe、allow、deny，独立输出目录和元数据 receipt。baseline 无 Span；其余各 Agent1/LLM2/Tool1，父子关系正确，原始参数/消息/凭证不上报。deny 由 ToolNode 处理，模型可完成收尾，业务工具执行0次；其余工具1次。禁止将拒绝结果与原业务等价混为一谈。

每次完整运行比较新建独立业务计数，校验 JSONL/flush/shutdown；输出新目录不覆盖既有证据，超出预期退出非0。报告实际执行/校验耗时与固定宿主 before/after 文件的机械行差异；不计为安装、人工阅读、真实项目迁移或5分钟体验证明。

AC1601：原 Agent 无 Aegis 依赖、适配层独立，8组 sync/async×4模式真实框架行为符合契约。
AC1602：严格检查执行次数、Span数量/父子/LLM耗时和合成用量、治理决策；损坏/缺失证据不能通过，不输出原参数/凭证。
AC1603：机械差异、CLI失败状态、接入选择/步骤/局限文档、受影响回归与机器证据；核心服务仍无需LLM，依赖/SQL/OpenAPI不变。
