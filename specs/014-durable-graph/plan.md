# SPEC-014方案

复用官方SQLite实现，不自研checkpointer。三个新依赖从官方PyPI元数据选定，下载字节SHA256核对；保持59-pin历史收据，另建62-pin快照。strict serializer显式指定，不依赖宿主全局环境。新文件metadata/setup，既有文件只检查/读取，不自动初始化缺失状态。

工厂管理自己的sqlite3连接，WAL/FULL和有限锁等待；调用已有ReviewedGraphTool，只将图继续改为sync durability。示例先支持本机单个宿主、独立进程命令，不做分布式锁或自动恢复收据。

先存储边界与真实图关闭/重开测试，再真实子进程+HTTP/PG；测试worker以明确phase调用os._exit，副作用文件fsync后计数。避免在生产接口引入测试开关。完成后仅按受影响范围回归，验收记实际方法数与继承证据，检查wheel/安装/协议并清理专用容器。
