# SPEC-028：统一接入中的图流式生命周期与观测治理闭环

2026-10-25，已验证。场景：已有真实LangGraph的两轮模型/工具循环→Application配置控制工具→显式模型Wrapper与app.graph装配→invoke/ainvoke/stream/astream→结果/事件对照→完整消费或关闭/异常/取消→平台查询耗时、Token、工具决策和图生命周期。合成官方SDK transport，无真实LLM请求。

新增app.graph(compiled_graph, name=None)，显式延迟加载原SDK LangGraph adapter；配置v1/v2/v3与报告形状不变。返回限定方法句柄：invoke、ainvoke、stream、astream、with_config，不隐式代理其他图API。模型仍由宿主显式wrap_openai等入口观测，工具在构图前经app.tool绑定；不自动发现调用，不改变审批/图恢复协议或把流事件当作授权。

invoke/ainvoke整体租约；with_config保留原配置语义且返回受同一Application管理的图。stream/astream创建时需活动会话，底层原流及其父上下文按SDK语义创建，业务在首次拉取前不执行。闲置流不持有租约、不产生Span；第一次next/anext取得租约，跨yield保持调用计数但不保留OTel活动上下文。直到EOF、成功close/aclose或异常后清理完成才归还。会话关闭后未使用流不能开始执行；已结束流可幂等关闭。

单个流只允许一个进行中的拉取/关闭；不支持并发消费或跨事件循环操作。async在调用者循环await，不创建后台消费/清理任务或线程桥接。节点异常/取消对象身份保持；清理失败不能替代原始拉取/消费者异常。已经开始的流若清理失败，保留租约、禁止再拉取，宿主须在原循环显式重试close/aclose，清理成功后才能关闭Application。无GC自动关闭，宿主必须在finally/上下文中关闭提前退出的流；单独break不表示关闭。借用图、模型客户端和其他资源仍由宿主拥有。

沿用SDK既有流outcome与隐私语义：completed/closed/error/cancelled，状态事件和对象原样返回，异常/取消不重试业务。仅白名单Trace元数据；原始模型/工具输入输出、流payload、callback metadata、凭证不采集。模型调用耗时为客户端请求生命周期；图流耗时含消费者等待，不声称纯推理时长或首Token时延。

完整示例提供真实StateGraph/ToolNode、官方模型SDK离线两轮调用、同步/异步、完整/提前关闭/业务失败和允许/拒绝，接入前后结果及计数对照。真实HTTP/PG验证图outcome、LLM用量/耗时、Agent/LLM/Tool关联与治理事件；复用原Dashboard/API，可离线导出核验。独立核心安装不引入模型/图依赖，显式extras安装后可运行完整示例。

AC2801：限定图API、旧配置/报告兼容、延迟依赖、with_config/参数/对象保持、关闭后拒绝调用。

AC2802：真实stream/astream懒执行、整个消费生命周期租约、父上下文恢复、EOF/提前关闭/节点错误/取消、清理失败保持租约和异常身份、单消费者/原循环边界。

AC2803：真实框架+官方SDK合成模型+受控工具的完整运行矩阵、无外部模型请求；HTTP/PG中的耗时、Token、图生命周期、治理关联与隐私，导出离线核验。

AC2804：可运行指南/示例、全新核心及显式extras离线安装、完整回归与机器证据、专用环境清理。服务/迁移/UI/既有SDK和审批协议保持；无真实Provider、远端发布或新GUI验收声明。
