# LangGraph审批恢复参考

查阅：2026-10-20。官方链接及原创笔记，未镜像第三方文档。

- [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)：恢复使用Command和原thread；中断所在节点会重新开始，恢复值不等于Aegis的服务端批准。Aegis采用纯中断节点和独立宿主执行。
- [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)：checkpointer与thread快照。Aegis本轮仅使用InMemorySaver验证同进程对象重建，不声称跨进程持久性。

本机官方发行LangGraph1.2.15/checkpoint4.3.0的源码与探针验证：StateSnapshot包含config/tasks/interrupts；节点运行config的checkpoint_map中根键对应暂停snapshot。该字段依赖已锁版本，缺失时拒绝收据。根据实际框架测试确定，不把滚动文档中新接口自动列为已支持。

逻辑call的稳定action_id、完整图绑定信封、HMAC收据、未知不重试和单个同步根中断均为SPEC-013项目决定，不是官方框架的安全保证。其他节点/宿主/原函数仍可信。
