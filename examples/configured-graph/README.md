# 配置审批图示例

完整同步/异步start→独立审核→新进程resume→status流程见[操作指南](../../docs/configured-graph.md)。[application.json](application.json)固定工具/图版本，[policy.json](policy.json)只允许demo-agent的records.write；[agent.py](agent.py)显式绑定真实LangGraph，复用原SQLite格式和审批协议，不使用LLM、不自动批准。

从仓库根目录运行，先创建artifacts父目录。start必须用不存在的state；所有阶段传同一config/state/同步或异步模式。首次暂停不执行业务；独立reviewer批准后才可resume一次。tool-calls.jsonl只写计数；ticket.json和checkpoint.sqlite3包含明确披露的完整参数，应保护并留在忽略目录。

status不初始化SDK/审批客户端、不访问服务。失败/取消/unknown不重试，图继续与业务确认不构成共同事务。退出码、资源所有权、版本变化及部分效果边界见指南。适用于本机单宿主、单根单interrupt；不代表分布式恰好一次。
