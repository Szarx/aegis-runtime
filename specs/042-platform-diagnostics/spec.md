# SPEC-042：已有Agent的平台连通性诊断

2026-10-29，设计冻结。仓库命令scripts/platform_check.py只读检查用户明确指定的Collector，补足017只查元数据、008负责安装之后的连通性排查。不启动Docker、不安装、不运行Agent或模型、不写入遥测/审批/数据库。无需新依赖或协议/迁移/UI变更。

AC4201：必填--base-url，HTTPS或HTTP精确loopback主机；无userinfo/query/fragment或路径前缀。读取AEGIS_API_TOKEN仅作受保护查询的Bearer，形状不合法在网络前退出2。健康探针不携带凭证。固定GET路径、禁止重定向、禁用环境代理，不重试。每次socket超时--timeout-seconds为1..30，默认3；每份响应最多1MiB，必须200/application-json/有效无重复键JSON。此为socket操作超时，不宣称整轮硬实时deadline。

AC4202：依次live、ready、limit=1/offset=0的Trace列表，任何失败停止后续检查，区分HTTP未授权、就绪失败、未找到、重定向、HTTP错误、网络不可用/超时、协议错误。可选--trace-id严格非零小写hex32，继续读取该Trace与limit=100的治理事件页，验证返回标识/计数/关联，不把第一条Trace推断成用户应用。报告只显示固定阶段/分类/计数、明确请求的Trace标识及缺父数量，不输出URL、token、服务名、属性、参数或异常正文。未知仍为未检查。

AC4203：默认仅stdout JSON；显式--output独占创建文件，已有目标在网络前拒绝，写失败退出非0。0表示选定只读查询通过，1表示检查/保存失败，2表示预检/参数错误。报告列出未检查的SDK导出、业务行为、模型、界面、审批角色、身份真实性和完整审计。空列表可通过连通性检查；指定Trace缺失必须失败。缺父数量明确但不作为服务不可用；查询可用不代表Trace完整。

AC4204：契约覆盖参数/敏感信息/分阶段失败/响应边界/输出独占与真实socket重定向不跟随。真实HTTP+PG新增合成Agent追踪与allow/deny治理，正确/错误凭证、指定Trace、服务停机均实际验收；只读命令前后数据计数相同。更新接入与故障排查指南及机器证据。
