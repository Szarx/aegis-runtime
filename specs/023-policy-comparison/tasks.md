# SPEC-023 任务

状态：已验证，2026-10-24。

- [x] 冻结完整比较场景、保守CI状态及信任边界。
- [x] 比较模块、CLI与规则/用例差异报告。
- [x] 变更示例、实际CLI/Runtime与独立包验收。
- [x] 兼容回归、文档/机器证据及环境清理。

## 完整交付

comparison模块与compare CLI贯通基准校验、规则结构比较、用例前后决策、有限覆盖和独占JSON报告。实际CLI/CI退出码、示例/指南与独立wheel一起验收；不发布、热加载或自动启用候选。

新增10个方法：Policy8、Runtime1、契约1；子场景/CLI进程不重复计数。原295全部重跑，254个Python（SDK59、Policy20、Runtime67、Collector32、契约35、真实PG41）和51个前端，共305方法全部通过，无失败/错误/跳过；详见[validation.json](validation.json)。

| AC | 当前证据 |
| --- | --- |
| 2301 | 同revision修改也被识别；只改revision仍需审查；规则/成员重排不变；未覆盖新规则仍需审查；基准预期不符不返回unchanged；modified_details指明effect/成员字段 |
| 2302 | 示例2放宽/1收紧/1原因变化/4不变，同效果规则ID变化亦可识别；缺身份/权限不匹配规则；复制输入快照，不保留调用方用例引用，报告不复制完整策略成员 |
| 2303 | 实际compare变化退出1、相同退出0、输入/输出失败2，旧报告不覆盖且错误不泄漏原文；真实同步/异步共32次Runtime尝试，基准每模式2业务调用、候选3，共10调用，逐Span核对effect/reason/rule_id |

最终Policy wheel安装到独立target，以`python -I -S`验证8项比较、0/1退出码、旧check的7项与旧explain，无site-packages或环境PYTHONPATH依赖。原Policy核心与022工作台源码字节均未改，新增comparison模块和CLI分支。wheel SHA-256：819d7226b63e59e41372b72c9c079557f9f70a03dd6a5f780d26b5574ce819b6。

边界：有限用例无法证明全空间等价、未覆盖规则不可达或生产完整性。配置变化返回1是保守审查信号，不是自动批准；规范指纹无认证/审批效力。平台服务、四迁移、SDK/Runtime实现/UI均未变，无真实LLM或远端GitHub操作。前端测试重跑，类型/构建/页面证据继承020。

本机明细：artifacts/check/result.json与tests.log、artifacts/policy-comparison-frontend.json、artifacts/policy-comparison/package.json、docker.json及独立安装包产生的实际差异报告。62 pins、44来源、两平台缓存哈希及历史59条收据未变，OpenAPI精确保持020，旧011路径/模型兼容测试通过。pip check、文档与候选工作树文件检查通过。

专用aegis-spec023-check健康、测试schema清零后关闭容器/网络，卷保留；未改用户现有平台服务。没有新镜像构建、发布、GitHub创建/推送或远端CI运行。
