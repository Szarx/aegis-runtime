# SPEC-044 方案

1. 扩展traceLocation可选来源解析/生成及统一返回信息，调用queryLocation严格白名单；保留旧Trace/Span解析限制。
2. 两类列表生成来源绑定，App选Span时保留来源，TraceDetail与加载/失败状态共用返回模型。节点分享保持最小地址。
3. 测试、真实preview和窄屏检查、文档证据一起交付。本轮仅044。
