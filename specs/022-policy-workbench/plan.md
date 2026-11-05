# SPEC-022 方案

新模块复用Policy.from_dict/from_json和evaluate，不改原求值器。独立CLI只读取有界JSON；校验套件并建立快照后再计算报告。规则覆盖只表示测试用例中的选中/匹配，不称作生产覆盖或不可达分析。指纹与审批签名严格隔离。

测试包含纯格式/求值/指纹/报告与实际CLI退出码；同一套件经Runtime同步和异步工具对照决策与业务次数。构建Policy wheel到独立target，以不加载site-packages的Python执行check/explain。平台未改，保留020 OpenAPI及四迁移，既有Runtime/审批回归使用统一入口。
