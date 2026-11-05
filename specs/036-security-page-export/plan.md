# SPEC-036 方案

1. securityPageExport.ts纯函数投影固定字段，以lossless-json.stringify保留bigint，CSV逐格转义；严格限定已载入页的offset/数量和文件名。
2. SecurityTable增加邻近标题的下载操作和范围说明，禁用状态来自原查询props。事件处理函数显式创建Blob/临时链接，反馈和对象URL生命周期受组件拥有。
3. 自动化纯序列化/SSR状态；生产preview真实下载读取文件比对页内行数、最大int64纳秒与末页，窄屏核对不产生整页横溢。
4. 记录OWASP参考的适用范围与限制，更新指南、机器证据和路线图后进入下一SPEC。
