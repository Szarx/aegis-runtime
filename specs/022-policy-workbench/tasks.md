# SPEC-022 任务

状态：已验证，2026-10-23。

- [x] 冻结完整工作流、严格格式和授权/覆盖边界。
- [x] 工作台模块与CLI、规范指纹和批量报告。
- [x] 策略用例示例、实际CLI/Runtime与包安装验收。
- [x] 兼容回归、文档/机器证据及环境清理。

## 完整交付与回归

工作台模块、check/explain CLI、严格套件、决策解释、规范指纹、规则覆盖、JSON报告及验收后接入Runtime示例一起交付。新增10个方法（Policy7、Runtime1、契约2），原285全部重跑；244个Python（SDK59、Policy12、Runtime66、Collector32、契约34、真实PG41）与51个前端，共295方法通过，无失败/错误/跳过。子场景/CLI进程不重复计数。

| AC | 实际验收 |
| --- | --- |
| 2201 | UTF-8/重复键/未知字段/未来版本/错误类型/标识/文件体积、套件边界与预期配对拒绝；规范指纹忽略顺序和空白，策略revision/成员改变时变化 |
| 2202 | 解释复用既有求值结果，deny优先与同效果规则ID排序；缺身份不匹配规则；报告区分不符、空用例与有限覆盖，复制套件快照；输出独占保护，写入/关闭失败删除残文件 |
| 2203 | 真实CLI校验7项并解释拒绝，错误预期返回1、无效输入/已存在输出返回2且不泄露原内容；同步/异步示例各7尝试、1业务调用、14Span。独立Runtime测试14次尝试共2业务调用，逐Span核对effect/reason/rule_id，拒绝不执行 |

最终Policy wheel安装到独立target后，通过`python -I -S`执行check与explain，无site-packages或环境PYTHONPATH依赖，7项通过、deny-blocked胜出。wheel包含workbench与__main__；原Policy核心__init__.py字节与015历史包相同。SHA-256：5f367b147626825343cba693ae3c4b02602a1cd79f8e2aa13bf62e5387b4b2df。

机器证据见[validation.json](validation.json)。本机明细：artifacts/check/result.json与tests.log、artifacts/policy-workbench-frontend.json、artifacts/policy-workbench/package.json及docker.json，另保存安装包产生的实际报告。生成物忽略，不混入源码。62 pins、44来源、两平台缓存哈希与020/011兼容契约保持，pip check及文档/候选文件检查通过。

本轮专用aegis-spec022-check健康、测试schema清零后关闭容器/网络，卷保留，未动用户现有服务。无LLM请求、GitHub远端/推送或远端CI。服务/SQL/SDK/Runtime实现/UI未改；前端测试重跑，类型/构建/页面证据沿用020。指纹不是审批绑定，有限用例覆盖不证明生产完整性、规则不可达或可信身份。
