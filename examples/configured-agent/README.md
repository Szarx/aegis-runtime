# 统一配置接入原生与LangGraph Agent

本例把原业务模块application.py和Aegis宿主run.py分开。业务只返回合成订单并计数，无Aegis导入、模型、网络或业务系统；LangGraph路径是真实StateGraph/ToolNode，使用合成请求节点。

安装和配置字段见[完整接入指南](../../docs/application-onboarding.md)。开发环境已安装锁定依赖与三个本地包后运行：

```text
python -m aegis_runtime inspect examples/configured-agent/application.json --subject reader
python examples/configured-agent/run.py --subject reader
python examples/configured-agent/run.py --subject blocked --async
python examples/configured-agent/run.py --framework langgraph --subject reader
python examples/configured-agent/run.py --framework langgraph --subject blocked --async
```

两种framework、两种调用方式、两种身份共8组合均有独立进程验收。每次先运行基线（业务1次），再运行管理版本：reader业务1次且结果等价，blocked业务0次且结果有意变化。管理阶段新增Agent/Tool共2Span，父子关联保持；前一基线不初始化SDK。

application.json与application-otlp.json分别示范文件与网络导出；policy.json控制reader允许、blocked拒绝。所有相对路径按配置文件目录解析，与启动cwd无关。JSONL默认写入artifacts/application-onboarding/traces.jsonl并追加。第二项write_record只展示未绑定清单，不会被隐式创建或自动保护。

网络模式需otlp extra、有效本机环境变量AEGIS_API_TOKEN与实际Collector地址。使用--config选择网络配置，身份仍由--subject这个合成宿主参数传入；真实应用应从可信宿主身份来源绑定。检查不会发送网络请求，实际Agent运行才发送OTLP。

真实平台验收将8组合各上报一条Trace，得到8事件/16Span、允许4/拒绝4；导出后停服回放，原Policy得到8不变，放宽候选得到4放宽/4不变。原业务结果、未知审计完整性和审批边界保持，见[025证据](../../specs/025-application-onboarding/tasks.md)。
