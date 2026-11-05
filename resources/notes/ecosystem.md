# 生态资料与后续用途

查阅日期：2026-10-13 起，实施状态更新于 2026-10-17。保存官方入口与短摘要，不做竞品能力排名或未经验证的兼容性承诺。

- [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview)：SPEC-006 已使用真实 StateGraph / ToolNode 验证 invoke / ainvoke；自动全节点、图流式和新用户接入耗时仍待验证。
- [FastAPI](https://fastapi.tiangolo.com/tutorial/first-steps/)：Collector / 查询服务，已按 SPEC-002 实现接收与查询契约。
- [PostgreSQL JSON 类型](https://www.postgresql.org/docs/18/datatype-json.html)：SPEC-002 用于过滤后的资源/属性/事件存储；实际验证 PostgreSQL 16.15。
- [Vue](https://vuejs.org/guide/introduction.html)：Dashboard 的组件开发入口；追踪树、时间线与未知用量展示由产品 spec 决定。

FastAPI / PostgreSQL 已通过 SPEC-002，Vue Dashboard 按 SPEC-003 实现，见 [Dashboard 笔记](dashboard.md)。2026-10-17：OpenAI Wrapper 离线见 [004](openai.md)，DeepSeek 6 个真实请求见 [005](deepseek.md)，LangGraph 真实框架 / 合成模型见 [006](langgraph.md)。框架内真实 Provider 尚未验收，不合并这些证据扩展兼容性声明。详见 [Collector 笔记](collector.md)。
