# Dashboard 资料与取舍

查阅与验证：2026-10-15。对应 [SPEC-003](../../specs/003-dashboard/spec.md)，保留 Vue 3 / TypeScript / ECharts 的既定方向，只做只读原生 Trace 可视化。

[Vue TypeScript](https://vuejs.org/guide/typescript/overview) 与 [Vite](https://vite.dev/guide/) 用于 SFC 构建。已验证 Vue 3.5.44、Vite 8.3.4、TypeScript 5.9.3 / vue-tsc 3.3.13、Node 22.23.2。TypeScript 先使用明确安装验证的 5.9.3；不因 registry latest 升到未验证的主版本。依赖精确锁定于 package-lock，构建时执行独立类型检查。

[lossless-json 官方说明](https://github.com/josdejong/lossless-json) 提供自定义整数解析器。安装的 4.3.1 类型/源码明确支持 `parseNumber`；不依赖文档示例里命名不一致的 numberParser。API 纳秒通过文本 token 进入 bigint，分页/计数验证后才转安全 number。先减 bigint 原点，再转换图表坐标；原始时间保持十进制值。

[ECharts 生命周期](https://echarts.apache.org/handbook/en/concepts/chart-size/) 用于容器大小变化和卸载释放。使用 6.1.0 模块化 custom series，以 ResizeObserver 驱动 resize、卸载 dispose。浏览器验证发现旧 api.style 的弃用提示，已改为显式样式；不使用 HTML tooltip。树按钮提供等价键盘导航，图表只表达记录的区间。

- [前端依赖来源与完整性](../downloads/frontend.json)：官方 registry 的直接依赖元数据；完整传递依赖见 dashboard/package-lock.json。锁文件包含可选平台，不代表全部平台均已安装/验证。
- [Node 镜像来源](../downloads/node-image.json) 与 [Nginx 镜像来源](../downloads/nginx-image.json)：官方 Registry，manifest/config/layer SHA256 与 diff IDs 校验；Docker archive 导入后的本地 manifest 与上游原始摘要分开记录。
- [验收记录](../../specs/003-dashboard/tasks.md)：17 个前端测试、真实 Collector / PostgreSQL 的浏览器操作与构建/部署证据。

当前镜像基础 tag 可变化，未来公开发布应锁定完整基础镜像链并复验。本轮仅本地开发，不发布公共 Site、包或镜像。
