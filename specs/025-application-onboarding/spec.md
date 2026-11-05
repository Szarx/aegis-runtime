# SPEC-025：已有Agent统一接入流程

2026-10-25，已验证。本轮按完整接入场景交付：配置/Policy快照→只读检查→托管SDK启动→显式绑定受控工具/Agent→原生Python与真实LangGraph同步/异步→遥测诊断/关闭→真实Collector查询、导出、候选回放。

新增aegis_runtime.application：load_application读取aegis.application.v1 JSON（最多64KiB，UTF-8、无重复/未知键）。配置含service_name、policy_file、1..128项唯一tools(name/permission)、telemetry。文件相对路径以配置所在目录解析，不以cwd解析；配置是可信宿主输入，不支持Python表达式/环境值展开或模型生成配置。Policy通过022严格加载并固定快照，文件后续变化不自动刷新。

telemetry支持jsonl(path)或otlp(endpoint/token_env、可选timeout_millis默认3000)，禁止内联凭证/任意headers。OTLP只允许HTTPS或本机回环HTTP、准确/v1/traces路径、无账号/查询/片段；token_env为显式环境变量名或null匿名，提供变量名时必须有有效可打印ASCII非空值。配置不含subject，Application(config,subject=...)要求宿主绑定合法身份。

Application是单次使用的同步上下文管理器，在enter调用原SDK.init、exit flush/shutdown，只关闭自身SDK句柄，不替换已有活动SDK。返回值/业务异常/async取消和签名保持，Policy失败关闭与零重复业务执行保持。async函数在调用者任务await；同步上下文在全部工作结束后关闭，不提供异步context或stream支持。

app.tool(fn,name=...)从配置取权限，经原Runtime包装；未配置/重复绑定拒绝，不能通过参数覆盖权限。app.agent(fn,name=...)显式观测入口，可包装真实CompiledGraph.invoke/ainvoke。封装函数只在活动Application可调用；进入次数计数，关闭时有未结束调用则拒绝关闭并保持会话，宿主先await/join再close，不终止业务或强行关闭借用资源。停止后旧包装不能再次执行。遥测flush/关闭失败保留false诊断，不改变已经完成的业务结果，不产生业务重试。

python -m aegis_runtime inspect CONFIG --subject SUBJECT [--output REPORT]只校验配置/策略、预览各工具决策、检查token形状和OTLP包元数据，不启动SDK/创建遥测/探测网络/运行Agent。状态valid/blocked，退出0/1；输入/IO失败2。报告不含路径、端点、环境变量名或值、原工具参数；输出独占保护。installed不等于依赖可导入或Collector可达。

Application.status报告状态created/active/closing/closed/failed、配置/已绑定/未绑定工具、进行中计数和SDK数字诊断、flush/关闭结果；不记录配置路径或凭证。SDK单实例、控制只针对交给Agent的包装入口，未包装函数不被保护，不自动发现LLM/工具或授予审批。

AC2501：严格配置/快照/路径/环境引用、只读检查/退出码/隐私与现有SDK不被接管。
AC2502：配置工具权限绑定、未知/重复/关闭后拒绝、签名/返回/异常/async取消、并发关闭与诊断、现有Runtime授权兼容。
AC2503：原生/真实LangGraph同步异步、允许1/拒绝0、上下文关联、独立安装包和无需图依赖的核心导入。
AC2504：真实OTLP/Collector/PG的统一配置接入，查询/导出/离线回放、文档及完整回归和临时环境清理。
