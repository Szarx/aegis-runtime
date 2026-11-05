# SPEC-032 任务

状态：已验证，2026-10-26。

- [x] 冻结检查入口、失败关闭、预算与预览边界。
- [x] 检查器、产物契约与CI入口。
- [x] 实际执行与生产浏览器验收。
- [x] 文档、证据与预览交付。

4项新增Python契约通过，覆盖不完整/失败/skip报告、超时停止并保存部分日志、外部/越界/缺失入口、真实资源哈希与超预算。统一命令实际跑完59前端方法、类型与生产构建；9个JS/CSS产物，入口JS gzip37386字节，全部JS601298字节、CSS22192字节，均在预算内。原330 Python继承028，新增4项本轮运行，方法目录393，不声称本轮重跑全部334 Python或远端CI。

生产preview在回环5189，以原Vite同源代理连接8849隔离Collector。实际浏览器确认加载/assets/index-Cse4rMaC.js而非dev入口，详情hash深链可连接、Token14/6、LLM筛选2项；独立reviewer连接显示6项审批（已自然过期），未提交决定。截图artifacts/ui032，检查日志/清单artifacts/dashboard-check，摘要见[validation.json](validation.json)。生产预览保留供用户查看及033续验；原32776页面未变更。Vite preview仅本机预览，不是生产部署或远端公开发布。
