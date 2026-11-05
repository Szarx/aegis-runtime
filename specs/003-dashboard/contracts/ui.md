# Dashboard 交互与精度契约

- `/` + `#/traces`：连接后列表；`#/traces/<32 位非零小写 trace_id>`：详情。非法 hash 显示无效地址，可回列表。
- 连接：可输入 Bearer，点“连接 Collector”。连通性由一次受保护列表查询确认，健康检查不能替代认证验证。连接失败清空页面数据，保持可重试；“断开”清空内存 token。
- API 固定 `/api/v1/traces` 或校验 ID 后的详情路径；query 使用 URLSearchParams，禁止动态跨域 endpoint。请求 cache=no-store、redirect=error、凭证不自动附带 cookie。
- 开始时间筛选使用本地 datetime-local 到毫秒，再用 bigint × 1,000,000 转换；空值不发送。结束早于开始时不发请求。纳秒原始值以十进制字符串显示。
- 按 20 条翻页，后退 offset≥0；offset 达到 API 10000 上限或无下一页时禁用前进。筛选使用已应用值，刷新/翻页不暗中提交尚未应用的输入。
- 详情树按 API 顺序建立，父缺失视作独立根并提示。环/自父构成不完整关系，从确定的起点断开展示，每个 Span 仅出现一次，保留原始 parent_id。
- 时间轴显示各 Span 相对 Trace 最早起点的区间；点选行/图更新右侧节点详情。0 ns 显示标记但文字仍为 0 ns。超长标签截断并保留 title / 文本详情。
- 所有外部名称、属性、异常类型按 Vue 插值渲染。无 v-html、HTML 图表 tooltip 或自动链接远端内容。
- token 变更/断开和路由变化使旧请求失效；被取消的请求不显示错误。网络与解析错误固定提示，可手动重试。
- 统计和状态以服务端为准：当前页 Trace、异常数、Span 数为局部派生指标；Token/Cost 未知。每个 Span 的 exact timestamp 和 permission 可在 metadata 查看。
