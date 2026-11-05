# SPEC-015 原生异步依据

2026-10-22 查阅官方 [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)、[checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) 和 [SQLite3.1.2发布页](https://pypi.org/project/langgraph-checkpoint-sqlite/3.1.2/)，并核对已锁定安装包的 AsyncSqliteSaver / aiosqlite0.22.1源码。此文件为原创摘要，不镜像第三方正文。

官方异步 saver 使用原生异步连接，调用者负责连接生命周期；图中断继续会重新进入节点。Aegis 把工具放在显式宿主驱动中，节点只处理 interrupt/完成收据。checkpoint_map 根 ID 的绑定只对锁定 LangGraph1.2.15 验证，不推广到任意框架版本。

aiosqlite 把 SQL 交给连接工作线程；取消等待者不能撤销队列操作。配置借入连接而不创建内部连接/后台清理任务，失败由宿主关闭并排空。序列化器沿用014 builtin-safe配置，不启用 pickle 或任意模块构造；未知扩展可能退化为基础 JSON 值，因此仍需精确绑定校验。

无新增依赖版本或下载。沿用 [Windows](../downloads/spec014-python-windows.json) / [Linux](../downloads/spec014-python-linux.json) 各62包收据；原59版本/收据不变。源码、真实 native await、HTTP/PG 与独立进程的可重复结果见 [015](../../specs/015-async-graph/tasks.md)。
