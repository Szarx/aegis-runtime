# 如何接入已有 Agent

固定外部项目的实际接入见[官方 ReAct 模板配方](../examples/external_react_agent/README.md)。它保留上游图，记录外部服务边界替换和宿主适配，覆盖观测、拒绝及 ToolNode 审批暂停与恢复。

已有Agent可先选用[SPEC-025统一配置入口](application-onboarding.md)，减少Policy/工具权限/SDK关闭的手动装配；仍需显式交给Agent包装后的工具，不自动发现内部调用。下表保留各独立入口，适用于已有SDK会话和高级审批场景。

Aegis 服务不需要 LLM；模型仍由 Agent 的客户端调用。先确定需要的能力，再在可信宿主选择入口。以下是当前已实现的路径，框架外部身份认证、自动发现或任意框架注入不在这些入口的保证范围。

| 需求 | 接入方式 | 需要修改的位置 |
| --- | --- | --- |
| 先看一次 Agent 调用边界 | 原生入口 `aegis.observe`；已有编译图 `observe_graph` | Agent 宿主入口 |
| 看内部 LLM 时长/用量 | `wrap_openai` 或显式 DeepSeek 工厂 | 构造/传入模型客户端处 |
| 看工具调用 | `aegis.tool` | 工具转成框架schema之前 |
| 在副作用前 allow/deny | `Runtime(...).tool`，替换观测工具包装 | 可信宿主绑定Policy/subject，并将包装后工具传给框架 |
| 人工审阅后执行普通工具 | ReviewedTool / AsyncReviewedTool | 显式prepare、独立审核、宿主resume |
| 人工审阅后继续单个图中断 | ReviewedGraphTool / AsyncReviewedGraphTool | 采用纯interrupt节点、宿主驱动和受约束checkpoint |

观测的 permission 只是标签。需要阻止执行时用 Runtime；人工批准不能覆盖本地deny，批准也不会让Collector执行工具。给已经编译的图套 observe_graph 只能观察图入口，不能自动发现内部模型或给未包装工具补上控制。

## 先验证基础观测

1. 在独立环境安装。原生快速开始用 [quickstart](quickstart.md)，LangGraph与模型客户端需要对应extras。开发分发尚未公开发布；本例完整环境可用仓库requirements-dev.lock加本地包，不能假设只安装SDK核心就有框架/Runtime。
2. 找到宿主创建客户端、业务工具和图的位置。保留原业务函数；在构图前包装客户端和工具，构图后包装入口。客户端仍由宿主关闭。
3. 在宿主启动初始化SDK，在退出时flush/shutdown；先输出本地JSONL，检查Agent→LLM/Tool父子关系、LLM开始/结束时间和真实可获得的用量。
4. 对合成输入分别执行未接入和观测版，核对完整业务结果和副作用次数。未知用量不补零；调用总时间不能当服务端推理时间。
5. 确认后按 [本地部署](../deploy/docker/README.md) 接入OTLP/Collector/Dashboard。网络和平台步骤独立验收，当前配方receipt不冒充页面验收。

具体独立应用与适配层见 [配方](../examples/existing_agent/README.md)。本例在已有factory支持注入客户端/工具的前提下，两个宿主文件只有一行导入不同；新适配层和SDK生命周期仍需实现。已有项目若把客户端/工具写死在内部，需先增加注入点，不能套用这个行数估计。

## 再增加执行控制

在adapter里以Runtime.tool替换aegis.tool，不要堆叠同一工具的两个Span包装。subject/Policy来自可信宿主；让模型输出subject或改Trace元数据不会授予权限。先运行allow检查结果等价，再运行deny确认业务工具0次。框架可能捕获ActionDenied并让Agent继续，因此需要同时查看治理工具Span和业务副作用，不能只看最终Agent是否返回。

人工审批接入有更多状态、披露和永久消费边界，不能靠换一个装饰器完成。请分别使用 [普通工具](reviewed-execution.md)、[异步工具](async-reviewed-execution.md)、[同步图](langgraph-reviewed.md) 或 [异步图](async-graph.md)。完整参数进入审核存储/图checkpoint与默认不采集正文的Trace是不同数据路径，宿主需要主动选择披露。

## 本轮验证与未测量事项

[SPEC-016](../specs/016-existing-agent/tasks.md) 验证真实框架、合成客户端的同步/异步×baseline/observe/allow/deny八组运行，记录调用次数、业务等价、Span数量/关系、LLM时长和宿主机械差异。

尚未计时安装、阅读、手工修改、真实第三方Agent项目迁移、在线下载或页面首次可见；不据此宣称人工接入5分钟。下一步人工验收应记录开始/结束、失败步骤、实际修改文件/行数，并单独标明缓存、依赖预装和是否包含平台启动。无新增真实模型请求。

接入前可先按 [预检说明](preflight.md) 运行doctor检查选定关键包；通过后仍需本页的实际行为/Trace对照，不能把元数据匹配当作真实接入成功。
