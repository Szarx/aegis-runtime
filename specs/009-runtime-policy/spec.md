# SPEC-009：进程内工具权限控制

日期：2026-10-18。先冻结契约再实现；不发起真实模型请求。首版支持 allow / deny，人工审批与恢复后续独立设计。

## 授权与信任边界

- 宿主通过 `Runtime(subject="order-agent", policy=Policy.from_dict(...))` 绑定身份和不可变策略快照，工具使用 `@runtime.tool(permission="orders.read")`。同步与普通异步工具均支持，`functools.wraps` 保留签名，返回/业务异常对象保持。
- 身份由应用可信启动代码提供，不读取工具参数、LLM 文本、Trace agent_name、远端 header 或可变环境中的 subject。该标识不是认证系统，也不防御同进程内恶意代码/直接调用原函数；宿主负责在每个实际工具执行入口接入 Runtime。Runtime 是进程内库，不是沙箱。
- 既有 aegis.tool(permission=...) 仍仅观测，行为不变。Runtime 创建自己的受控 Tool Span，已有工具应以 runtime.tool 替换观测 tool，不同时叠加两个 Tool 装饰器。Agent 入口继续 aegis.observe，模型 Wrapper 不变。

## 策略格式与求值

JSON 根字段精确为 schema_version=`aegis.policy.v1`、revision、rules。每条规则精确为 id、effect=allow|deny、subjects、tools、permissions；三个匹配列表使用精确字符串匹配且均非空，无通配符、表达式、正则或继承。rules 可为空，此时默认拒绝。根/规则未知键、错误类型、空标识/空匹配列表、重复规则 ID/列表值、超过 128 条规则或各列表超过 128 项都拒绝加载。标识仅 ASCII 字母数字开头，后续允许字母数字与 `._:-`，最长 128；`*` 不支持。

策略加载复制输入并冻结成 tuple / frozen dataclass，外部原始字典修改不影响已创建快照；直接构造也执行相同校验。加载失败抛固定 ValueError，不执行工具；不自动回退到允许。配置和策略本身不从远程自动获取或热更新。

调用时精确匹配 subject / tool / permission 三元组，任一 deny 匹配优先于所有 allow；同类多条匹配用按 rule ID 排序的首条记录原因，结果与文件顺序无关。无匹配默认 deny。缺身份、缺权限、缺策略、求值异常或非法求值结果均拒绝。优先原因：identity_missing → permission_missing → policy_unavailable → policy_error / explicit_deny / explicit_allow / no_match。

Policy 引擎无 SDK/网络依赖，只返回不可变 Decision。Runtime 每次调用产生独立 action_id，在任何受保护工具副作用前求值一次。拒绝抛固定消息 ActionDenied(PermissionError)，附只读 decision 和 action_id，工具执行 0 次；允许只调用原函数一次，无新增重试。普通/异步异常身份及取消保持。SDK 未启用、shutdown、导出失败或 Span 创建失败时，权限控制仍执行；观测故障不导致额外调用或放行。

## 数据契约

受控工具尝试是自有 `aegis.governance.v1`，operation execute_tool / INTERNAL，name `execute_tool <tool>`。一个调用尝试只创建一个受控 Tool Span，拒绝并不意味着工具已执行。公共 SDK 遥测入口 `aegis.governance.governed_tool_span` 只记录元数据，不做授权；SDK 核心不依赖 Runtime 或 Policy。

属性白名单：原 Agent/Tool 字段，以及 action.id（32 位非零小写 hex）、subject.id、policy.revision、decision.rule_id、decision.effect、decision.reason、action.outcome；均在 aegis 命名空间。subject / permission / revision 在未知时缺省，绝不填虚构身份。显式规则匹配必须有 rule_id，allow 仅配 explicit_allow；deny 原因为其余六种。Outcome 为 completed / error / cancelled / denied：allow 可配前三项，deny 只配 denied；completed 为 UNSET 且无 error.type，其他 ERROR 且有异常类型。只有类型事件，无异常正文、参数、返回值或参数摘要。本地 JSONL 为 aegis.span.v4。

Collector 独立校验新 mapping 的字段/状态/原因配对，保留旧三个 mapping。复用既有 execute_tool 行、JSONB 和迁移 {1,2}，查询结构不变，007 OpenAPI 仍有效。decision、subject、policy 元数据是上报信息，不能在服务端作为可信身份或不可篡改审计证明。异步遥测可能丢失；本轮不承诺 durable audit 或因导出失败阻止已允许工具。

Dashboard 在受控工具节点展示明确的允许/阻止、固定原因、策略版本、规则、subject、action ID 与实际结束原因；将允许决策和工具异常分别展示。无 Runtime 标记的 permission 仍注明仅元数据。列表 status ERROR 可包含被拒绝的尝试，本轮不增加安全中心/审批 UI 或 Trace 决策汇总。

## 验收

| AC | 条件 |
| --- | --- |
| 901 | 严格加载与不可变快照；精确三元组、deny 优先、默认拒绝、顺序无关；坏策略从不运行工具 |
| 902 | 同步/异步真实工具计数：allow 一次、deny 零次；缺身份/权限/策略、求值异常都不放行 |
| 903 | 返回/异常/取消、签名、并发父子上下文、action ID 独立；遥测停用/异常不能绕过控制或重跑工具 |
| 904 | 本地 v4、OTLP 配对/白名单/隐私、旧 mapping、数据库迁移与查询兼容 |
| 905 | 合成示例验证成功、显式拒绝、默认拒绝与允许后业务异常，HTTP/真实 PostgreSQL/实际页面一致 |
| 906 | Policy/Runtime 可安装 wheel、相关回归、前端类型/构建及 README/架构/路线图/资源证据更新 |
