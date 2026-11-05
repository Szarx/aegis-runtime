# SPEC-017 方案

importlib.metadata读取选定发行包版本；tomllib延迟到Python门槛后读取可信仓库基线。检查集显式列出SDK核心/模型图入口/异步SQLite入口所需的关键版本，既不要求安装Collector，也不声称覆盖全部transitive依赖。

配置检查独立显式开启，不读取.env文件或模型密钥。报告字段白名单化；实际版本仅参与比较，不进入输出。测试以注入metadata读取器和最小environment验证错误/隐私，再真实CLI验证本机/无site-packages/既有独立venv。只回归接入契约；核心包未改，旧SDK/Runtime/平台测试证据按来源继承。
