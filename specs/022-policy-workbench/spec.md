# SPEC-022：策略开发与验收工作台

2026-10-23，已验证。完整场景：编写现有v1策略→文件校验→解释单次决策→批量声明式用例验收→将通过验收的不可变Policy用于Runtime。无新DSL/执行入口/模型/网络/服务接口或迁移。

公共aegis_policy.workbench模块提供load_policy、explain、check_cases；python -m aegis_policy提供check和explain命令。严格UTF-8 JSON，文件上限1MiB，拒绝重复键、未知字段、不合法标识、未来格式、错误类型与超过上限；不导入用户Python或执行表达式。

check可仅校验策略；附--cases时读取aegis.policy-cases.v1套件，1..128个唯一id用例，显式subject/tool/permission（前后两者可null）、expected effect/reason/rule_id。使用原Policy.evaluate，输出每项actual/expected、通过状态、匹配规则与选中规则，以及仅针对该套件的规则命中覆盖。deny优先、同效果按id排序，缺身份/权限默认拒绝，规则次序不影响解释。

explain输入只包含标识，不接收工具实参；显示原决策及所有精确匹配规则和最终获选者。身份/权限缺失时不匹配任何规则。规范策略指纹SHA-256包含revision，规则与成员按id/文本排序，忽略格式与输入顺序；只用于本地报告，不替代审批协议摘要或认证。报告不读取环境凭证或工具实参，不回显源文件路径或完整策略；输出配置的规则/用例标识、决策及指纹。

CLI成功0，用例不符1，输入/IO/配置错误2，错误文本固定且不回显内容。--output以独占xb创建新JSON报告，父目录需存在，拒绝覆盖；失败写入删除本次不完整文件，写失败返回2。无需output时stdout输出JSON；用例不符仍输出可审查报告。已有解释器/SDK不新增依赖，Policy旧入口与Runtime执行语义保留。

AC2201：严格策略/套件文件及配对校验、版本/类型/边界/隐私和指纹稳定。
AC2202：纯评估解释、deny优先/默认拒绝、规则次序、套件报告/有限覆盖/退出码/文件保护。
AC2203：可运行策略和用例、真实CLI和Runtime同步/异步执行对照、打包安装与兼容回归、文档证据。
