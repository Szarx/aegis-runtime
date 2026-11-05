# SPEC-028 任务

状态：已验证，2026-10-25。

- [x] 冻结完整流式接入场景、资源/异常/取消与隐私边界。
- [x] AC2801：限定图API与旧配置兼容。
- [x] AC2802：同步/异步流生命周期及真实图契约。
- [x] AC2803：模型/工具循环、运行矩阵与真实平台闭环。
- [x] AC2804：独立安装、全回归、文档证据及环境清理。

## 完整交付和验收

限定图API、流资源与异常语义、真实框架/模型SDK/受控工具循环、四调用运行矩阵、真实平台查询与治理导出、独立安装及操作指南一起交付。配置v1/v2/v3、原SDK/审批协议、Collector/API/四迁移和UI保持。

新增15方法（Runtime12、CLI契约1、真实PG2），原366全部重跑；330 Python（SDK59、Policy20、Runtime119、Collector32、契约49、真实PG51）与51前端，共381通过，无失败/错误/跳过。测试内组合、进程和安装示例不重复计为方法。

| AC | 实测证据 |
| --- | --- |
| 2801 | invoke/ainvoke/with_config保留配置和结果；只暴露五种方法，非编译图/重复托管句柄拒绝；关闭后调用/构造/配置失败；旧配置/报告全部回归，核心安装检查v1/v2/v3一致 |
| 2802 | 原StateGraph真实同步/异步流：创建/闲置关闭零执行/Span，已关闭会话不能开始；EOF归还、提前关闭归还，拉取后close busy；事件对象identity、父上下文在yield间恢复、两个独立流分别持有租约；单流并发拉取/关闭拒绝，async跨循环拒绝 |
| 2802故障 | 原节点异常、拉取取消和消费者取消对象保持，outcome error/cancelled；源清理失败不覆盖原拉取异常，已开始流保留租约，禁止再拉取，显式close/aclose重试后归还；清理本身取消同样保留租约，宿主原循环完成关闭；没有自动重试业务/后台清理 |
| 2803矩阵 | 20真实HTTP/PG配置运行：4模式×允许/拒绝×正常/框架处理工具失败，共16完整运行；另2流模式×2身份提前关闭共4。允许2模型/1业务/4Span，拒绝2模型/0业务/4Span，提前关闭1模型/0业务/2Span；8流completed、4流closed，另8普通Agent无流outcome |
| 2803平台 | 每模型7输入/3输出Token、模型请求耗时为正，父子与Trace关联完整、无消息/参数/异常文本；16治理事件（8deny）关联工具，导出后停服务离线核验16。独立故障schema另2Trace验证未处理error和cancelled均ERROR入库 |
| 2803流格式 | CLI独立12组合：sync/async×updates/values/combined×v1/v2，原始业务归一化后与基线一致，每次2模型1业务；提前退出/拒绝/失败在平台矩阵同时验证 |
| 2804安装 | 全新venv离线SDK015/Policy023/Runtime028 wheel，8核心分发（含pip）无框架/模型/HTTPX，缺extra拒绝图绑定且无执行/Span；显式SDK langgraph/openai extras后，安装路径校验、四调用和双流提前关闭共6组合通过，pip check通过 |

极短合成工具可能在同一Windows墙钟刻度开始/结束；初始“所有Span严格正耗时”的过严断言修为工具非负，模型和完整Trace正耗时检查保持，未修改时间字段或放宽授权条件。测试中的模型均为官方SDK合成transport，图流不是模型Token流。

Runtime wheel SHA-256：7a227e769c1908226d3af30052fdb208f45fe9de4a6812ef80127e4506f47517。对比027 wheel，除application追加方法外原Python源码字节保持，新增managed_agent_graph；SDK015/Policy023继承，无新依赖pins。机器证据见[validation.json](validation.json)，本机明细在artifacts/check、artifacts/managed-graph及artifacts/managed-graph-frontend.json。

专用aegis-spec028-check测试schema清零后移除自身容器/网络，卷保留，用户原服务未改。文档链接、候选文件、62 pins/44来源/双平台哈希/历史59收据、020 OpenAPI和pip check通过。UI类型/构建/浏览器、Collector镜像继承020，无本轮新页面或镜像声明；没有真实Provider、自动审核、GitHub创建/推送/远端CI或人工/在线安装计时。

边界：显式接入模型和工具，句柄不代理任意图API或控制原始函数；宿主拥有模型/图/checkpointer。已开始流清理失败会阻止会话关闭，需要显式在原循环完成清理；单独break/GC不是清理协议。图流耗时包含消费者等待，模型耗时是客户端请求生命周期，不代表纯推理或首Token时延；审批图仍走原精确checkpoint协议。
