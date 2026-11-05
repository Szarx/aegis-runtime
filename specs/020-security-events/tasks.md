# SPEC-020 任务

状态：已验证，2026-10-23。

- [x] 冻结完整纵向功能、角色/隐私与兼容边界。
- [x] 查询存储/路由/OpenAPI及协议与PG测试。
- [x] 前端事件中心/解码/筛选分页/状态与测试。
- [x] OTLP示例、真实HTTP/PG/页面完整流程验证。
- [x] 受影响回归、文档/机器证据与环境清理。

## 完整交付

本轮按完整用户功能交付：只读治理事件查询、组合筛选/分页、页面状态及Trace关联，加上可运行Agent、操作文档、协议快照与实际验收。新增18个方法（Collector6、PG4、前端8）；旧254个方法全部重跑，累计272。全部221个Python（SDK59、Policy5、Runtime65、Collector32、契约20、真实PG40）和51个前端方法通过，无失败/错误/跳过；子场景与重复运行不重复计数。vue-tsc、Vite生产构建、pip check通过。

| AC | 实际验收 |
| --- | --- |
| 2001 | Trace认证与三种审批角色隔离；只读方法、全部筛选参数/范围、400/401/503固定响应及no-store。新020快照精确匹配，移除新增路径/两个模型后精确等于011旧契约。初次回归发现FastAPI自动添加422，补与既有路由一致的4XX声明后完整回归通过，未修改历史快照掩盖问题 |
| 2002 | 真实PostgreSQL：同时间稳定分页、重复上报不增量、同Action不同Trace独立、旧普通Tool排除；全部过滤与组合/时间边界/SQL值绑定/null配置/隐私/存储重建/故障及旧Trace行为核对 |
| 2003 | 无损纳秒/严格白名单及字段配对、非法数据拒绝、筛选URL、过期页抑制、请求取消/固定错误、SSR加载/空/重试/分页/安全文本、允许后异常和取消分别展示。生产浏览器核对最终构建的拒绝筛选、清空、空结果及原Trace的Agent+被拒工具 |
| 2004 | 示例使用真实Runtime、SDK与OTLP HTTP上报，真实Collector/PG，生产Dashboard通过本机同源代理查询真实服务。25次尝试/25Trace/50Span，完成5、拒绝10、业务异常5、取消5，业务函数进入15次；第一页20/第二页5，拒绝10、异常5、取消5、demo-agent20，25事件全部关联原Span，错误凭证401 |

## 包与环境

Collector本地wheel构建并安装到独立target后，确认从target导入新接口模块、020 OpenAPI匹配、011路径/模型全部保留；4个SQL资源字节与015包完全相同。依赖使用现有锁定开发环境，不冒称全新依赖环境或新Docker镜像验收。wheel SHA-256为785f422c98a351efcdd2db8521362977f7d7656087d38cd851667655176898c7。

本轮临时HTTP服务已停止，验收浏览器标签已关闭；仅删除专用合成schema并关闭aegis-spec020-check容器/网络，卷保留，其他项目未动。62个Python pin、44个官方来源和两平台缓存哈希保持；没有真实Provider请求或凭证使用。

机器结果见[validation.json](validation.json)。本机详细输出位于artifacts/check/result.json、tests.log、artifacts/security-tests.json及artifacts/security-events中的live-http.json、package.json、docker.json、denied.png、trace.png。artifacts按规则忽略，不作为源码上传；可运行示例与测试保留在仓库。

边界：应用上报身份不是服务端认证，记录不是完整或不可篡改审计。无新索引/大规模性能、跨页快照、租户隔离、审计保留/导出或执行按钮。私有开发上传的本机门槛通过，未创建/推送GitHub或运行远端CI；许可证仍未定。
