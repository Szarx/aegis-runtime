# SPEC-003 实现方案

1. Vite 构建 Vue SFC，TypeScript strict；依赖精确版本与 npm package-lock。Node 22.23.2 为本机基线，具体安装后版本记录于 tasks。不增加全局状态框架，使用组件与组合逻辑管理有限页面状态。
2. API adapter 对 response.text 使用 lossless-json 的整数解析器；整数先进入 bigint，时间保持 bigint，分页/计数仅在安全范围内转为 number。公共 API 不变，禁止对原始 API 数据直接 response.json。
3. 纯领域函数构建有限且确定的树遍历、计算相对纳秒与日期、构造合法筛选；为精度和异常关系写针对性测试。ECharts 只接收相对毫秒，tooltip 内容使用 Vue 文本展示，关闭 HTML tooltip。
4. 单独请求协调器负责 AbortController、超时和请求序号；列表与详情取消各自请求。连接成功前不展示旧数据；Bearer 由内存对象显式传入，仅允许固定同源路径。
5. 页面由连接、列表、详情组成，hash 仅携带非零 trace_id。采用有边框的暗色工作台，错误以珊瑚色、Agent 以紫色、Tool 以青色区分，标识/时间用系统等宽字体，不引入外部字体或图片依赖。
6. ECharts 使用模块化 custom/canvas 时间线，ResizeObserver resize，卸载 dispose；树和列表同时提供按钮，保证键盘和 0 时长选择。
7. 本机开发 Vite 代理 API，Compose 静态 Nginx 代理到 Collector；静态构建产物打入镜像，不把认证配置写入 JS。先验证现有 Node/官方 npm registry，网络问题按官方包元数据与完整性记录处理。
8. 验证包括领域/网络故障测试、实际浏览器交互与响应布局、生产构建、真实 Compose + 原生示例闭环。仅合成数据，测试创建自己的项目/数据库，不接触其他服务。

参考来源写入 resources，前端交互契约见 [ui.md](contracts/ui.md)。代码完成后同步 README / ARCHITECTURE / ROADMAP，完整 Phase 1B 继续保持未完成。
