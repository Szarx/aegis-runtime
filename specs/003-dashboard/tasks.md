# SPEC-003 任务与验证

状态：已验证，2026-10-15。

- [x] T301：先维护 spec、方案和 UI / 精度契约。
- [x] T302：锁定 Vue / Vite / TypeScript / ECharts / 无损解析依赖。
- [x] T303：实现 API、请求协调、精度和异常关系处理。
- [x] T304：实现连接、Trace 列表、树、时间线和节点详情。
- [x] T305：前端与 Collector 同源代理、Compose 和运行文档。
- [x] T306：领域与故障测试、类型检查、构建、浏览器与真实后端闭环。
- [x] T307：回写版本、AC 证据、资源和产品文档。

## 运行环境与依赖

Windows Node 22.23.2 / npm 10.9.8；Linux 构建镜像 Node 22.23.3 / npm 10.9.9。Vue 3.5.44、Vite 8.3.4、@vitejs/plugin-vue 6.0.10、TypeScript 5.9.3、vue-tsc 3.3.13、Vitest 5.0.4、ECharts 6.1.0、lossless-json 4.3.1。精确传递依赖与官方 tarball integrity 在 dashboard/package-lock.json，直接依赖 [来源记录](../../resources/downloads/frontend.json)。

Nginx 1.31.7，进程 UID 101；Collector / PostgreSQL 为 SPEC-002 实现，使用 PostgreSQL 16.15。Docker 29.7.2 / Compose 5.5.0。镜像 [Node](../../resources/downloads/node-image.json)、[Nginx](../../resources/downloads/nginx-image.json) 的官方来源与摘要已保存，基础 tag 仍可变化，不宣称复验了其他版本。

## 自动化与构建

dashboard 下执行 `npm test`，2 个测试文件 / 17 个用例全部通过，最终运行 391 ms。`npm run build` 的 vue-tsc strict 类型检查与 Vite 生产构建成功；列表首包 92.59 KB（gzip 36.01 KB），详情 467.67 KB（gzip 158.86 KB）按需加载，CSS 18.55 KB。Windows 和容器 Linux 构建输出文件名及大小一致。

测试覆盖：19 位整数、相邻 1 ns、0/大时长、类型/重复键/不安全计数拒绝、子先父后/多根/缺失父/循环/自父、1500 层迭代遍历、筛选与时间边界、旧响应丢弃、取消、token 仅作为同源请求头、401/404/503 固定错误、有限超时、跨域目标拒绝和原生 fetch 调用方式。1500 层仅验证关系算法，不冒充大 Trace 页面性能测试。

浏览器首轮发现把原生 fetch 作为类方法调用会导致非法接收者错误；改为显式委托的默认函数，并新增回归测试。ECharts 的 api.style 弃用提示改为显式 style；生产代码不再调用该 API。未通过修改契约掩盖失败。

## 真实浏览器与服务链路

本次使用 Codex 应用内浏览器操作本地页面；这是单独记录的 UI 验收，不计入 17 个自动化用例。未使用模拟 Collector 替代端到端记录。

| AC | 已通过证据 |
| --- | --- |
| 301 | 原生 CLI → 官方 OTLP → 真实 Collector / PostgreSQL → Vue；customer-agent 成功/异常各一条，每条 Agent + Tool 两个节点 |
| 302 | ERROR 筛选得到 1 条；分页合成 Agent 21 条，首 20、次页 1、末页禁用前进；无匹配、筛选重置页码与清空恢复；旧请求覆盖用受控异步传输验证 |
| 303 | UI 缺失父提示与循环关系断开展示；各节点仅出现一次；多根、乱序、自父和深层关系另有算法测试 |
| 304 | UI 显示原始开始 1790000000000000101、结束 1790000000000000102、时长 1 ns；原生 0 ns 节点保留标记；大整数边界另有单元测试 |
| 305 | lookup_order 可定位 builtins.LookupError；Token / Cost 显示未采集，orders.read 标记权限元数据 |
| 306 | UI 错误 token 固定提示、旧数据清空；404 有返回与重试；刷新 token 字段为空，重新认证恢复深链；失联/超时/取消使用受控 transport 测试 |
| 307 | 详情深链、浏览器后退保留列表筛选，Enter 键选中节点；320 px 无页面横向溢出（时间线/表格容器内可滚动），1280 px 树/时间线/属性分区正确；HTML 名称按纯文本，无 img 元素 |
| 308 | Linux npm ci 离线校验安装 73 个包、容器类型检查/构建、非 root Nginx、三服务健康、生产页面与同源 API 均通过 |

原生成功 Trace：`a66bc139949e67f044518340d45aecb2`；异常：`fa45ff9650d379d57bc50a50f0f427b1`。业务成功/预期异常各一次，accepted/exported=4，其余失败/丢弃/pending 为 0。随后增加 24 条合成 Trace / 25 Span，仅用于分页、精度、异常关系与文本呈现；没有伪装成真实模型或成熟框架。

使用专属 `aegis-spec003-check` 项目，随机回环端口：PG 32768、Collector 32769、Dashboard 32770。生产 Dashboard 的同源查询确认原生 2 Trace / 4 Span；三项 healthy。原始合成响应与生产页面截图保存在忽略的 artifacts/dashboard/；不依赖它们构建源码。验收结束停止本次服务，保留专属数据库卷，不修改其他项目。

## 网络、文档与限制

Sites 的本地安装助手遇到 Windows npm 路径问题，使用本机 npm.cmd 安装同一锁定依赖。常规 Docker pull / 容器 npm ci 多次超时或连接重置；从相同官方 Registry 校验 manifest/config/layers/diff IDs 后导入镜像，准备独立官方 npm 缓存，再在容器中 `npm ci --offline` 按锁文件验证成功。未使用第三方镜像源，也未以宿主机 dist 冒充容器源码构建。缓存可丢弃且不入 Git，见 [缓存说明](../../deploy/docker/npm-cache/README.md)。

README、架构、路线图、组件与资源已同步；文档链接、精确锁文件、token 不持久化的源码约束、缓存/产物忽略已检查。SPEC-001/002 保留历史验收，不重写为本次 UI 结果。

最终文档检查：46 份 Markdown、151 个本地链接有效，22 个唯一官方来源。隔离 Compose 已停止，专属数据卷保留；浏览器响应尺寸设置已恢复默认。

原生可视化闭环完成，5 分钟接入/10 分钟完整体验未做首次使用计时，不宣称已达成。大 Trace 性能、其他浏览器/CPU 平台、OpenAI / LangGraph、用量、生产身份与策略审批仍未验证或实现。下一增量先维护 OpenAI Wrapper spec。
