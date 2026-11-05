# 一条命令准备Dashboard合成演示

先启动Collector/PostgreSQL与Dashboard，见[本地部署](../deploy/docker/README.md)。仓库环境需安装SDK的otlp/openai/langgraph extras、Policy和Runtime；完整开发锁文件环境可直接运行。前端生产预览见[Dashboard说明](../dashboard/README.md)。

在本机环境设置AEGIS_API_TOKEN为目标Collector的Trace凭证；匿名开发服务可不设。然后从仓库根目录运行：

```text
python scripts/dashboard_demo.py --base-url http://127.0.0.1:8000
```

默认25个合成工具尝试覆盖允许、拒绝、未绑定身份、业务异常和取消，生成25条Trace/50Span；另有真实LangGraph/官方SDK进程内合成模型的两轮循环，管理运行2模型+1工具+1Agent共4Span。图示例还运行未接入基线作对照。没有真实Provider或外部业务服务请求，LangSmith关闭。

打开Dashboard，以Trace凭证连接，列表可见security-events-agent和configured-order-graph；模型Trace的输入汇总14/输出6，安全事件共26条（默认）。使用本页筛选、节点搜索、键盘与密度功能检查页面。原始消息/参数不进入追踪，时间和用量来自这些合成请求，不能当作真实模型性能或费用。

## 可选完整参数待审核记录

目标服务先启用独立producer/reviewer/executor角色，Agent宿主本机只需设置AEGIS_APPROVAL_REQUEST_TOKEN和AEGIS_APPROVAL_EXECUTION_TOKEN，不需要reviewer凭证。然后：

```text
python scripts/dashboard_demo.py --base-url http://127.0.0.1:8000 --with-approvals
```

默认创建2条待审核合成动作，摘要明确标为演示，参数包含9223372036854775807，用于核对无损呈现。reviewer在页面使用自己的凭证连接；脚本不会自动批准、拒绝、领取或执行这些审核工具。审批客户端目前仅支持回环HTTP，--with-approvals在HTTPS目标上预检拒绝；HTTPS只可用于Trace演示。

**此命令只准备界面演示，不提供执行宿主**。binding key临时生成且不落盘，所以不能用这些动作恢复工具。需要真实完整流程时使用[配置工具审批](configured-review.md)或[持久化图审批](configured-graph.md)示例。批准不是业务执行，待审核演示约10分钟自然过期。

## 输出、失败与范围

JSON终端与新建artifacts/dashboard-demo/随机目录的report.json记录完成阶段、计数和Action ID，打印report_file位置，不包含token、完整参数或binding key。--output可指定一个尚不存在的目录，已有目录拒绝覆盖。

--attempts允许1..100，--approval-count允许1..5（仅启用审批时创建）。目标必须HTTPS或回环HTTP，不带账号、路径、查询或片段。退出0为全部阶段成功，1为未完成，2为预检/参数错误。阶段失败不重试、不撤销已接收数据；先查报告和平台，再决定新建演示，避免把重跑当作幂等操作。

命令不会启动、迁移、清空或删除数据库；删除本地报告不会清除已上报Trace和审批历史。不发送真实业务内容、模型密钥或自动审核；不能据此声称全部内部调用已记录。验收见[SPEC-035](../specs/035-dashboard-demo/tasks.md)。
