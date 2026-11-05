# 已有Agent的统一配置接入

SPEC-025将配置、Policy快照、工具权限、SDK生命周期、只读检查和框架示例放进同一接入流程。它提供进程内Application，不增加独立服务，不需要LLM。现有手动SDK/Runtime/审批入口继续可用。

需要配置工具必须人工审核时，使用[SPEC-026的显式v2配置](configured-review.md)和reviewed_tool；以下v1普通工具流程保持，不会自动升级或推断审批授权。

## 先运行完整示例

仓库根目录，使用Python 3.11+和本地源码，安装核心依赖及本地包：

```text
python -m pip install ./sdk/python ./policy-engine ./runtime
python -m aegis_runtime inspect examples/configured-agent/application.json --subject reader
python examples/configured-agent/run.py --subject reader
python examples/configured-agent/run.py --subject blocked --async
```

安装命令可能从包索引取得SDK的核心依赖；当前包仅用于本地开发，尚未发布。已有requirements-dev.lock环境可用`--no-build-isolation --no-deps -e`安装三个本地包。真实LangGraph示例另安装SDK的langgraph extra：

```text
python -m pip install "./sdk/python[langgraph]"
python examples/configured-agent/run.py --framework langgraph --subject reader
python examples/configured-agent/run.py --framework langgraph --subject blocked --async
```

每条命令先执行无Aegis的业务基线，再运行配置接入版本。允许时结果与基线相同、工具执行1次；拒绝时工具执行0次且有治理事件。每次管理运行产生1个Agent+1个Tool Span，输出到artifacts/application-onboarding/traces.jsonl，按SDK原语义追加。框架示例使用真实StateGraph/ToolNode和合成请求节点，**没有实际LLM调用**，也不将合成节点标成模型请求。已有模型仍通过原OpenAI/DeepSeek Wrapper显式观测。

## 一份可信宿主配置

```json
{
  "schema_version": "aegis.application.v1",
  "service_name": "order-agent",
  "policy_file": "policy.json",
  "tools": [
    {"name": "lookup_order", "permission": "orders.read"}
  ],
  "telemetry": {"mode": "jsonl", "path": "traces.jsonl"}
}
```

配置为UTF-8 JSON、最多64KiB，无重复/未知字段；工具1..128项且name唯一，name/permission/service_name为合法标识。Policy通过022加载并固定为不可变快照，磁盘文件后续变化不会热更新。相对policy_file和JSONL路径以**配置文件目录**为基准，绝对路径也可用；路径属于宿主可信配置，允许`..`，不进行环境表达式展开。不要把模型输出当作配置来源。

subject不写入配置，必须由可信宿主显式传入。它仍是宿主绑定标识，配置入口不提供外部身份认证或多租户隔离。

## 改造已有宿主

业务函数本身无需Aegis导入，宿主负责装配：

```python
from aegis_runtime.application import Application, load_application

config = load_application("aegis.json")
with Application(config, subject="reader") as app:
    protected_lookup = app.tool(lookup_order)

    @app.agent(name="customer-agent")
    def customer_agent(order_id):
        return protected_lookup(order_id)

    result = customer_agent("demo")
status = app.status()
```

需要自定义工具名时用`app.tool(function, name="configured_name")`。权限从配置固定读取，不接受调用者覆盖；未配置或重复绑定会失败。绑定只在会话活动时进行，函数签名与同步/异步类型保留，可在交给StructuredTool之前包装。返回对象、正常业务异常和async取消保持，拒绝沿用ActionDenied。

迁移时用这些入口替换原先对应的observe/Runtime.tool装配，避免在已经包装的同一函数外再次叠加追踪或控制。

真实编译图可通过`app.agent(graph.invoke, name="orders")`或`app.agent(graph.ainvoke, name="orders")`观测调用；工具必须先经app.tool再构造图。同步和异步函数都可用，async在调用者任务中await。app.agent不托管stream/astream；需要统一管理四种调用时使用新增[app.graph](managed-graph-stream.md)，替换这层Agent包装即可。它不自动发现内部工具/模型，审批恢复仍按显式checkpoint协议进行。

配置清单不是自动拦截机制。示例配置含lookup_order和write_record，只绑定实际使用的lookup_order，status会显示write_record未绑定；原始未包装函数仍可被宿主直接调用。请确保Agent实际获得的是包装入口。

## 生命周期与并发

Application是单次同步上下文：enter调用原SDK.init，exit对自身SDK句柄flush/shutdown。已有活动SDK时启动失败，不接管或关闭已有SDK；已嵌入SDK的宿主可继续手动Runtime路径。会话期间不要另外调用全局SDK初始化/关闭来更换所属实例。

它面向宿主进程的启动/关闭，不需每个请求重新创建。一个实例固定绑定一个subject，可服务并发调用；需要多个身份共享已有SDK时继续使用原手动Runtime装配，不把固定subject当作多用户请求认证。

每个受控Agent/Tool调用持有进行中计数，包含async await阶段。关闭前宿主必须等待任务完成或join线程；有未完成调用时close和上下文退出会报busy，会话保持活动，清理任务后重试close。若违反该前提，退出报错可能替代当时的业务异常；不要让后台任务脱离宿主的关闭协议。

关闭是同步有界操作，异步服务应在生命周期钩子中安排同步关闭，并先等待调用结束。这里不提供async context manager。关闭后保留的包装函数不能执行；不能重新enter同一Application。

遥测故障不会重跑业务。flush/shutdown失败会在status中保留false，正常业务结果不因此改变；可再次close尝试排空自身SDK，不会重跑工具或关闭后来的其他SDK。超时/进程强制退出仍可能丢失遥测，status不伪造成功。

## 只读检查和诊断

`python -m aegis_runtime inspect CONFIG --subject SUBJECT`只读取配置/Policy、预览每个工具决策、核对显式token引用与OTLP包元数据；不初始化SDK、创建JSONL、连接Collector或运行Agent。valid退出0、blocked退出1，配置/输出错误退出2。

加`--output artifacts/inspection-first.json`可独占保存报告，父目录需存在、文件不能已有。输出不含路径、端点、token变量名/值或工具参数。installed只表示元数据存在，不证明依赖可导入、网络可达或工具安全。

app.status包含created/active/closing/closed/failed状态、进行中计数、已配置/已绑定/未绑定工具、策略版本、SDK数字诊断及flush/shutdown结果。它不认证宿主身份，也不证明所有未接入调用均已记录。

## 接入平台、导出与回放

安装SDK的otlp extra，按[本地部署](../deploy/docker/README.md)准备Collector/PostgreSQL。将application-otlp.json中的端口改为实际地址，并在本机AEGIS_API_TOKEN环境变量提供Trace token后运行：

```text
python -m pip install "./sdk/python[otlp]"
python -m aegis_runtime inspect examples/configured-agent/application-otlp.json --subject reader
python examples/configured-agent/run.py --config examples/configured-agent/application-otlp.json --framework langgraph --subject reader
```

OTLP配置只允许endpoint、token_env及可选timeout_millis（1..30000，默认3000）；token_env为显式环境变量名，null表示匿名开发服务，指定名字时必须有合法非空值。不接受内联凭证或任意headers。端点为HTTPS或本机回环HTTP、准确/v1/traces路径，无账号/查询/片段。检查不会验证服务端凭证或审批角色。

在Dashboard安全事件中心按service=configured-agent筛选，查看允许/拒绝与原Trace；之后按[导出指南](security-export.md)生成包，再按[候选策略回放](event-policy-replay.md)离线评估。回放仍只计算决策，不重新执行工具或解除审批领取。

完整验收覆盖原生/真实框架八组合、生命周期故障、独立核心安装和真实平台闭环，证据见[SPEC-025任务](../specs/025-application-onboarding/tasks.md)。本机/合成示例不等同于人类首次接入耗时、任意框架适配或生产治理承诺。
