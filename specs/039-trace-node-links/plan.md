# SPEC-039 方案

1. traceLocation.ts纯函数读取/构造规范hash及清洗HTTP(S)页面URL。App只将解析后的Trace ID传给原查询通道，同Trace定位更新不重新loadDetail。
2. TraceDetail接收span定位/pageURL，选中变化通过统一函数发出事件。detail/外部定位与本机选择区分，避免清空当前筛选。缺失节点固定提示。
3. CopyValue扩展可隐藏长值并显示文字按钮，原默认ID复制保持。机器/实际浏览器验证后更新指南/路线图，继续下一SPEC。
