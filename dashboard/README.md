# Aegis Dashboard

029–031统一为紧凑数据工作台，含本页审核队列、渐进筛选、ID复制、节点搜索/类型视图、键盘导航和会话密度。设计与操作见[指南](../docs/dashboard-design.md)，实际验证见[031](../specs/031-trace-reading/tasks.md)。后续补齐首屏披露、本页导出/审批排序和[具体Span链接](../specs/039-trace-node-links/tasks.md)，打开链接后仍需独立连接Collector。新增[调用耗时排查](../docs/trace-reading.md)，可按已接收模型/工具耗时排序并定位节点，范围见[040验收](../specs/040-call-duration/tasks.md)。

当前前端87方法、类型/构建/产物预算通过；加载/失败恢复、对比度/触控与焦点范围见[033](../specs/033-dashboard-states/tasks.md)/[034](../specs/034-dashboard-accessibility/tasks.md)。可用[一条合成演示命令](../docs/dashboard-demo.md)准备真实平台中的Trace、模型用量、治理事件及可选待审核记录，无真实模型调用。安全事件支持[本页JSONL/CSV下载](../docs/security-events.md)，实际文件/精度/末页与窄屏验证见[036](../specs/036-security-page-export/tasks.md)。

SPEC-020新增安全事件中心，使用Trace会话查询治理事件，支持组合筛选、分页和Trace关联。身份与决策仍是应用上报遥测。完整流程、示例和当前验证见[安全事件指南](../docs/security-events.md)及[020验收](../specs/020-security-events/tasks.md)。

已实现 [SPEC-003](../specs/003-dashboard/spec.md) 的原生 Trace 列表、父子树、相对时间线、节点属性与异常类型。Trace 区消费 SPEC-002 查询接口且只读，审批区见文末 SPEC-010；实际验收见 [任务记录](../specs/003-dashboard/tasks.md)。

## 使用 Compose

仓库根目录运行 `docker compose up -d --build --wait`，默认打开 `http://127.0.0.1:8080`，输入与 Collector 相同的 Bearer token（本地默认 `aegis-local-dev`），然后连接。运行原生网络示例后可查看成功和失败的执行。完整步骤见 [本地部署](../deploy/docker/README.md)。

token 只在当前页面内存中，刷新需重新输入；不写入 URL、浏览器存储或构建配置。前端同源代理 `/api/` 到 Collector，镜像不内置 token。未启用服务端认证的本地环境可留空。

## 本机开发

Node `^22.12.0 || >=24.0.0`，实际 Windows Node 22.23.2 / npm 10.9.8。进入 dashboard：

```text
npm ci
npm run dev
npm test
npm run build
```

统一质量入口（仓库根目录，依赖已安装后）为`python scripts/check_dashboard.py`。Node未在PATH时加`--node "C:\Program Files\nodejs\node.exe"`。它顺序执行单测/类型/构建，失败、skip、超时和包体预算超限均退出1；日志/测试JSON/资源哈希与机器结果在artifacts/dashboard-check。预算入口JS gzip50KiB、全部JS1200KiB、CSS64KiB；这不是网络性能或Lighthouse保证。见[032验收](../specs/032-dashboard-quality/tasks.md)。

`npm run build`后可用`npx vite preview --host 127.0.0.1 --port 5189`检查生产bundle，代理继承AEGIS_COLLECTOR_URL（默认本机8000）。这是开发预览，不是生产部署；不把角色凭证放进配置或URL。实际部署继续按Compose指南。CI前端job复用统一检查器，远端执行状态需单独验收。

默认开发 URL 为 `http://127.0.0.1:5173`，默认代理 Collector `http://127.0.0.1:8000`。可在启动前设置 `AEGIS_COLLECTOR_URL` 指向其他本地 Collector（PowerShell：`$env:AEGIS_COLLECTOR_URL = "http://127.0.0.1:8000"`）。这只是开发服务器配置，不是浏览器可编辑的跨域目标；勿把 token 放进 URL。

生产构建输出 dist；详情/ECharts 按需加载。Vue 3.5.44、Vite 8.3.4、TypeScript 5.9.3、ECharts 6.1.0、lossless-json 4.3.1，完整锁文件为 package-lock.json。当前87个针对性测试覆盖精度、关系、筛选、网络协调、图生命周期、队列、节点阅读、模块加载、受测对比度和本页导出。浏览器验收另行记录，不计入自动化测试数量。

## 界面与限制

- 列表：Agent / Service / 状态 / 本地开始时间范围、每页 20 条、手动刷新。应用筛选重置页码；尚未应用的输入不会被翻页/刷新提交。
- 详情：hash 深链 `#/traces/<trace_id>`、Agent/LLM/Tool 树、ECharts 时间线、可键盘选中的 Span、属性和异常类型。
- Unix 纳秒以 bigint 保留，先减原点再用于图表；可展开查看原始值。日期展示毫秒精度，0 ns 仍可选择。
- 外部父/缺失父、多个根和循环关系安全显示。token / 连接变化取消旧请求，10 秒请求上限；不自动轮询。
- 原生 UNSET 展示“已完成”；LLM 按 outcome 区分 completed / closed / incomplete / cancelled / error。模型节点及Trace汇总展示实际可得用量，缺失保持未知、0保留0，费用不估算。普通工具标签不授权；受控工具决策来自宿主上报，不代表服务端身份认证。

大规模 Trace 性能与更多浏览器尚未验收。LLM 与节点用量已按 [SPEC-004](../specs/004-openai/tasks.md) 完成离线浏览器验证；LangGraph 显式接入及状态流见后文；审批准备见文末；策略编辑、恢复执行、生产身份、多租户尚未实现。组件只访问 API，不访问数据库或执行工具。目录 api/ 负责解码与请求，domain.ts 负责精度/关系，views/ 与 components/ 负责展示。

## DeepSeek 显示

SPEC-005 在模型用量区增加 Provider，旧 OpenAI 与 DeepSeek 节点均可显示；缺失仍为未知。已在真实 Compose 中核对默认离线四组合和两轮工具循环，Provider=deepseek、input=7/output=3 为合成值。前端 20 测试、类型与构建通过，截图和实际限制见 [005 记录](../specs/005-deepseek/tasks.md)。

用户随后批准的真实调用也已核对：deepseek-live-verification 服务下共 5 Trace / 16 Span，Provider=deepseek、模型 deepseek-flash，工具循环显示 LLM→Tool→LLM，首个 LLM 输入 299、输出 35 Token。真实截图 artifacts/deepseek/dashboard-live.jpg，与离线证据分开保存。

## LangGraph 验收

SPEC-006 未修改前端源码，复用已验证的界面。真实 LangGraph / ToolNode 与合成模型经 Collector / PostgreSQL 的 4 Trace / 16 Span 已浏览器核对：1 Agent、2 LLM、1 Tool，模型 Provider / Token、工具异常类型可见，Agent 与 Trace 汇总状态按各自语义保留。证据见 [006](../specs/006-langgraph/tasks.md)。前端 20 个测试及构建证据沿用未变更的 SPEC-005，本轮不重复计入 Python 测试。

## 图流式生命周期：SPEC-007

列表与详情消费可空 graph_outcome，无字段的旧响应仍可解码。图状态区分 completed / closed / error / cancelled，异常 status 优先；closed 显示“提前关闭”，不当作完整完成。UNSET 筛选显示“无异常”，仍使用原 API 值；图节点详情单独展示 stream / astream 与结束原因，关闭时提示未确认完整执行。没有图流的原生和模型记录保持原展示。

23 个前端方法、严格 TypeScript、Windows Vite 与 Docker 生产构建通过。浏览器核对 8 Trace / 24 Span 的列表状态及提前关闭详情的两个节点、astream / closed；截图保存在 artifacts/langgraph-stream/，见 [007](../specs/007-langgraph-stream/tasks.md)。

## Runtime 工具决策：SPEC-009

受控工具节点显示“已阻止”，详情显示允许/阻止、固定原因、绑定身份、权限、策略/规则、action ID 和实际结束原因；allow 后业务异常分别保留。无 Runtime mapping 的旧 permission 仍仅为元数据。Trace ERROR 包括拒绝尝试，不能等同于工具实际运行；页面只展示上报记录，不认证或执行授权。

当前 26 个前端方法、严格类型与 Windows / Docker 构建通过。浏览器已核对显式拒绝和允许后业务异常，图片 artifacts/runtime-policy/dashboard-denied.jpg；范围与记录见 [009](../specs/009-runtime-policy/tasks.md)。

## 审批准备：SPEC-010

新增 #/approvals 独立组件，reviewer token 只在组件内存，离开/断开清空，不复用 Trace 凭证。页面显示动作说明、身份/工具/权限、策略/参数绑定、有效期与关联追踪；记录批准/拒绝只保存决定，不执行工具。写结果未知清空列表，需手动刷新后才能继续。当前31项前端测试、类型检查及 Windows / Docker 生产构建通过，详见 [010](../specs/010-approval-records/tasks.md)。

## 执行审批：SPEC-011

#/reviewed-actions显示完整JSON实参（含默认值）、工具版本、审核/执行身份和时间。无损解析64位整数，明确区分available、claimed结果未知、completed、failed不可重试；核对参数后提交当前review_digest。界面不含执行凭证、领取/执行/释放按钮。与旧准备页面切换即销毁会话，旧列表不混入可执行动作。新增精度/摘要/状态/独立路径测试；实际页面与同步Agent恢复证据见 [011](../specs/011-reviewed-execution/tasks.md)。
