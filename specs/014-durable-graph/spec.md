# SPEC-014：本机持久checkpoint与独立进程恢复

日期：2026-10-22。先采用官方SqliteSaver验证本机单个同步根interrupt的跨进程恢复，沿用013的稳定逻辑action、精确snapshot绑定和011永久消费claim。不改Collector/OpenAPI/四迁移/Dashboard，无模型依赖或调用。不是多机调度、异步图或自动消除未知结果。

## 存储与兼容

新增可选aegis_runtime.durable_graph.open_reviewed_checkpointer(path,create=False,timeout=3)上下文工厂，返回官方SqliteSaver，退出关闭自有SQLite连接。模块导入仅标准库；构造时要求reviewed-langgraph-sqlite extra。固定LangGraph1.2.15/checkpoint4.3.0/sqlite3.1.2，新增aiosqlite0.22.1/sqlite-vec0.1.9，既有59个第三方pin不变，开发基线62。SQLite扩展不主动加载。

显式本机文件路径，拒绝:memory:/URI/UNC、目录或缺父目录，不自动建立业务路径。create=True仅允许新文件，独占创建；默认必须已有文件，以mode=rw打开，缺失文件不得悄悄变成空图。文件由宿主保护，Windows不声称POSIX mode提供ACL隔离。

本机元数据表aegis_checkpoint_meta格式1记录并核对三个框架版本及严格serializer配置；缺marker、格式/版本不匹配、损坏/只读/锁超时失败关闭，不自动迁移既有文件或向任意SQLite库添加表。官方表setup仅在新文件执行。宿主升级框架需单独设计迁移，不以新文件替代未知动作。

WAL + synchronous=FULL，连接等待0<timeout<=5秒；限定本机单个宿主串行管理thread，不声明文件锁是调度/单次副作用保证。JsonPlusSerializer显式pickle_fallback=False、allowed_msgpack_modules=()、allowed_json_modules=()，保留官方内置safe类型；不从文件导入任意自定义类。官方checkpointer仍保存完整图状态/interrupt/写入，文件可信但不构成不可篡改审计。

013恢复图的invoke明确durability="sync"；示例初次运行同样用sync，收到正常返回时等待本步checkpoint写入。SQLite与PostgreSQL/业务存储没有共同事务，不承诺断电/磁盘故障或硬件持久性。

## 宿主工作流

新无LLM示例分start/status/resume命令，state目录显式选择；start只新建目录/数据库，生成稳定thread/call并暂停，prepare后写严格JSON ticket。ticket含完整参数，独占创建、fsync，原子提交，失败不自动新建动作。status只加载已有checkpoint和ticket，不准备、不领取、不执行；resume用同一文件/key/id/Policy/工具版本建立全新驱动/图进程。凭证与key来自本机环境，不写文件。

示例不读任意pickle/远程状态；ticket读取有大小/重复键/JSON边界检查。启动失败可能已保存checkpoint或服务端审批，禁止通过删目录/换id/key自动重跑。跨进程恢复仍必须满足审批未过期、原绑定/本地allow及唯一claim；超过TTL并不会续期。

## 退出边界

| 退出位置 | 工具副作用 | 新进程的允许行为 |
| --- | --- | --- |
| 已暂停并prepare、尚未claim | 0 | 原checkpoint/ticket经人工批准后显式resume一次 |
| claim已提交、原函数前 | 0 | claimed未知，恢复拒绝，不释放 |
| 函数写入后、尚未确认 | 可能1次部分写入 | claimed未知，恢复拒绝 |
| completed已提交、图继续前 | 1次 | 图可能仍暂停，恢复拒绝；不自动重建收据/重跑 |
| 图sync写入完成后、宿主输出前 | 1次 | status能读取完成标记；重复resume拒绝 |

使用真正独立Python子进程及os._exit模拟这些边界，不用同一个InMemorySaver冒充进程恢复。测试用真实HTTP/PG作审批库、真实SQLite文件作checkpoint、fsync合成事件作副作用计数。注入退出钩子仅测试代码存在，生产API不提供故障开关。拒绝/过期/参数或版本变更零新增副作用。

## 验收

| AC | 验证 |
| --- | --- |
| 1401 | 显式文件、只新建/只重开、marker/版本、锁/损坏/错误路径、上下文关闭、严格反序列化/无任意模块或pickle |
| 1402 | 新进程读取原thread/checkpoint/interrupt/action，成功批准后一次执行和完成标记；旧同步/异步/图回归 |
| 1403 | 真实进程在claim前后/函数写入后/确认后/图写入后退出，新进程无重复副作用或新action |
| 1404 | status无审批网络/执行；拒绝/到期/缺失或篡改状态/参数/版本失败关闭；原始业务异常和遥测隐私沿用013 |
| 1405 | 可选extra/wheel隔离，官方来源+两平台62-pin收据，原OpenAPI/四迁移不变，示例/spec/证据回写 |

未交付：生产PostgresSaver、多进程同时驱动同一thread、异步/子图/多interrupt、跨版本存储迁移、completed收据重建、自动重试/过期续领、生产身份/租户、外部系统恰好一次。
