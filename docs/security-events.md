# 安全事件中心

SPEC-020提供已接收治理Span的只读查询和页面。Aegis服务无需LLM；事件由已接入Runtime的Agent经SDK/OTLP上报。运行示例与依赖见[示例说明](../examples/security-events/README.md)。

## 页面使用

打开Dashboard，以Collector的Trace API token连接，再选择“安全事件”。此处使用Trace会话，producer/reviewer/executor凭证不能替代Trace凭证；未配置Trace token的本地开发服务延续原有匿名行为。审批页面仍使用独立内存会话。离开页面会取消查询，断开连接清除凭证；页面不保存到浏览器持久存储。

可组合精确筛选上报身份、工具、权限、服务、决策、结果、Action ID和Trace ID。日期输入使用浏览器本地时区，发送为纳秒开始时间范围，含两端；表格显示UTC时间，悬停可查看原始纳秒值。应用筛选回到第一页；清空、刷新和前后翻页可重查结果。每页20条，最多offset10000。空值在行中显示未绑定身份、未声明权限或策略不可用，不替代成有效身份或权限；筛选空白表示不筛选，当前没有专门查询null的参数。

“已允许”只代表通过本地策略。执行可能完成、业务异常或取消；“已阻止”表示Runtime未进入工具函数。点击“查看Trace”可关联Agent父节点及治理Span。相同Action可能有多次尝试，事件身份为Trace与Span组合；不得只按Action ID合并。

## 查询接口

`GET /api/v1/security-events`返回items、total、limit、offset，详细字段见[OpenAPI](../specs/020-security-events/contracts/openapi.json)。limit默认20、范围1..100，offset0..10000。subject/tool/permission/service_name/action_id/trace_id/effect/outcome精确匹配；started_after_ns和started_before_ns为正int64纳秒，前者不能大于后者。

仅选择aegis.governance.v1、execute_tool、INTERNAL组合，不把普通工具的permission标签当作治理记录。白名单投影不含原始参数、结果、prompt、凭证、异常正文或审批完整参数。参数错误400、凭证错误401、存储不可用固定503；响应使用no-store及Vary Authorization，不回显故障详情。

count/page在同一个只读repeatable-read事务内读取，排序为开始时间降序、Trace ID/Span ID升序。Span重复上报沿用first-write-wins。跨页是不同请求，并发插入时页边界可能移动；没有跨页快照或游标。查询复用JSONB，不新增迁移或索引；大规模数据性能尚未验收。

## 信任与验证边界

跨Trace结果可通过[SPEC-021导出工具](security-export.md)生成JSONL/CSV与清单，离线核验并查看结果/原因汇总。仍不保证跨页快照或审计完整性。

页面标题旁可显式下载**当前页已载入记录**的JSONL或CSV，无额外查询。文件名含offset、实际条数和下载UTC时间；total是查询匹配数，不是文件条数。加载中、查询错误或无记录时不可下载。下载操作只在浏览器生成文件，不上传凭证或另查全量；提示“已请求下载”不代表浏览器已成功写盘。

JSONL为UTF-8一行一事件，固定16字段，null和纳秒整数原样保留，不合并相同Action的不同Span。CSV也是UTF-8，固定列/CRLF，危险公式前缀加单引号并逐格引用；这会改变CSV字段。电子表格可能自动四舍五入长数字或在重新保存时改变转义，导入时应把列设为文本；精确保留/机器处理请选择JSONL。文件可能含应用上报身份和标识，请按查询数据本身保管。

本页文件不含021清单，不可交给021 bundle verifier当作可核验排查包，也不证明全部事件已收到。需要跨页收集/清单时仍用命令行。实现与验收见[036](../specs/036-security-page-export/tasks.md)。

身份、策略和结果来自应用上报，Collector不会据此认证调用者或授予执行权。记录可能缺失或被授权数据库管理者修改；页面不是完整、不可篡改审计，也不提供审批、执行或删除操作。多租户隔离、保留管理、审计完整性和统计聚合另行设计。

本轮覆盖真实SDK→OTLP HTTP→Collector→PostgreSQL→生产Dashboard，合成数据25次尝试/50Span，含允许完成、显式拒绝、缺身份拒绝、业务异常和取消。自动化、安装及浏览器证据见[验收任务](../specs/020-security-events/tasks.md)，不依赖真实Provider。
