# SPEC-013任务

状态：已验证，2026-10-20。

- [x] T1301：官方资料与锁定框架探针，冻结节点重跑/动作绑定/未知语义。
- [x] T1302：可选同步ReviewedGraphTool与纯interrupt节点、可信收据。
- [x] T1303：真实框架边界、故障/并发/绑定/隐私及受影响回归。
- [x] T1304：真实HTTP/PG、重建宿主和无LLM图示例。
- [x] T1305：wheel/可选安装、协议/迁移不变、文档/资源与机器证据。

## 验收与计数

本轮实际执行Runtime46方法、真实HTTP/PG相关9方法，共55独立方法通过，无PG跳过。新增Runtime13、PG2共15方法；旧目录194中40项本轮重跑，其余154项沿用已完成历史证据，累计目录209。首批12方法和PG修正后的2项复跑不重复计数。前端/服务端协议未改，35项前端及生产构建沿用011，未声称重新执行。CLI、wheel、安装和文档核对另计。

| AC | 实际结果 |
| --- | --- |
| 1301 | 真实StateGraph/InMemorySaver，暂停/节点重跑零工具和审批网络；默认值/严格JSON/显式披露及同步签名；不支持的config、非原生图、多pending interrupt拒绝 |
| 1302 | thread/graph/tool版本/Policy/参数/summary、checkpoint和interrupt绑定；checkpoint编辑使旧ticket失效，重建新绑定仍用原action_id并被服务端拒绝；布尔、坏MAC、错误thread及root checkpoint收据拒绝 |
| 1303 | pending/rejected零副作用；批准一次；领取后图变化在原函数前拒绝；慢checkpoint读取后重新检查时效，过期不开始原函数；业务异常保留原对象，已提交领取/完成响应丢失不重试。真实PG两并发宿主仅一个执行工具 |
| 1304 | 成功value身份保留，完成标记不含业务返回值；Agent→Tool父子关系和上下文恢复；state/ticket/参数/异常正文不进遥测。确认未知不继续图，后验checkpoint变化blocked，继续图异常unknown且不重试工具 |
| 1305 | 实际HTTP/PG与原生图：新驱动/新编译图复用同一个进程内saver恢复；已消费动作拒绝，更新checkpoint也不能再mint动作。原生OTLP实际入库/查询，原同步审批7项数据库回归通过 |
| 1306 | 四wheel构建并独立目标安装；干净venv核心无LangGraph/HTTPX，新模块可导入且缺extra有固定提示；离线追加extra后真实图暂停/绑定通过，无OpenAI/Collector包。原011 OpenAPI精确一致，打包四SQL与012 wheel逐字节相同，59第三方pins未变 |

主要执行入口（根目录、本地包与锁定开发依赖已安装）：

```text
python -m unittest discover -s runtime/tests -v
python -m unittest tests.integration.test_graph_reviewed tests.integration.test_reviewed -v
```

PG需专用AEGIS_TEST_DATABASE_URL，随机schema完成后删除；Windows使用允许本机线程/异步及回环HTTP的进程。首次新PG方法的一个错误来自测试把OTLP二进制响应当JSON，修正响应读取后两个新方法通过，生产代码未因此改变。实际测试Python3.12.14 / LangGraph1.2.15 / checkpoint4.3.0；未声称多版本兼容执行。

## 合成示例与交付

[示例](../../examples/langgraph-reviewed/README.md)实际经历进程stdin确认、独立reviewer决定与同进程宿主重建：成功写1条/图继续，部分失败写1条/原异常，拒绝0条，EOF0条。Enter不能代替服务端批准。测试重跑时按已有事件数记录本轮增量，不把历史合成记录重复算成单次执行；cli.json包含baseline/total。本轮第一次CLI harness的中文stderr使用Windows默认编码，改为子进程显式UTF-8后完整重验并检查stderr，生产示例未因此改动。

证据见 [validation.json](validation.json)。忽略目录artifacts/langgraph-reviewed保存CLI四场景、实际HTTP审阅参数、两阶段离线安装报告、四wheel哈希和合成JSONL。38官方来源ID、59第三方Python pin、两平台下载收据与npm锁核对；只保存官方链接及原创整理。未新增UI/browser验收，未重复构建前端。零真实模型/外部业务请求，无提交/推送/公开发布。专用aegis-spec013-check容器/网络清理，数据库卷保留，详情在机器记录。

## 未交付与下一步

仅同步单个顶层interrupt，config仅允许thread_id；宿主需串行管理同一thread，图存储与审批库不是原子事务。action稳定依赖graph_id/thread_id/call_id/key稳定；不要以新id/key重新审批未知副作用。其他节点/原函数/宿主/checkpointer可信。checkpoint和审核信封主动保存完整实参，须宿主保护。

InMemorySaver验证的是同进程对象重建，非跨进程持久化。异步图、多interrupt、子图、持久checkpointer、崩溃后的收据恢复、Policy require_approval、生产身份/多租户、不可篡改审计与跨系统恰好一次未交付。下一步先冻结持久checkpoint与进程恢复的spec，再实现对应增量。

最终新增慢checkpoint时效边界后，完整Runtime46及相关HTTP/PG9再次通过；计数按独立方法，不累加重跑。同步ReviewedTool增加私有调用扩展点，公共API与旧行为不变。
