# SPEC-043 方案

1. queryLocation集中校验、规范hash/URL和UTC与本地草稿转换；复用现有API校验。
2. App拥有hash路由；Trace列表就地同步，SecurityEvents接收当前hash并发出导航，取消/序号隔离保留。连接只读探测和当前查询加载分开，地址错误不能回退全量查询。
3. CopyValue用于两列表标题栏；文档及真实preview验收后归档。
