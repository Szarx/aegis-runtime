# 持久图的官方依据与下载

查阅：2026-10-22。原创整理与官方链接，不保存整篇第三方文档。

- [官方Checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)：checkpoint、thread与持久后端。Aegis本轮选择本机SQLite验证独立进程，其他后端不自动列为已支持。
- [官方SQLite发行](https://pypi.org/project/langgraph-checkpoint-sqlite/3.1.2/)：3.1.2需要checkpoint>=4.3,<5，与本项目4.3.0兼容；依赖aiosqlite和sqlite-vec。官方安全说明建议限制反序列化类型，本项目显式使用builtin-safe-only和禁pickle。
- [aiosqlite0.22.1](https://pypi.org/project/aiosqlite/0.22.1/) 与 [sqlite-vec0.1.9](https://pypi.org/project/sqlite-vec/0.1.9/)：作为官方SQLite包的依赖安装，Aegis本轮不调用异步SQLite或加载向量扩展。

元数据来自官方pypi.org，字节来自files.pythonhosted.org，逐文件SHA256对照；Windows CPython3.12与Linux x86_64收据：[Windows](../downloads/spec014-python-windows.json)、[Linux](../downloads/spec014-python-linux.json)。旧59版本及006历史收据保持，014新增3项后为62 pins。

实际源码检查发现官方SqliteSaver会在setup做表初始化/兼容列更新，Aegis只在新文件setup；既有文件核对marker/表列后标记已setup。WAL/FULL、文件版本marker、严格ticket、未知不重试及不恢复收据均为本项目决策，不是框架对跨库恰好一次的承诺。
