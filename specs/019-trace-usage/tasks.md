# SPEC-019 任务

状态：已验证，2026-10-23。

- [x] 冻结已接收模型用量、维度完整性和兼容范围。
- [x] 纯BigInt汇总、详情组件和覆盖测试。
- [x] 前端/页面验证、协议检查与文档证据。

## 实际验收

本轮43个前端方法全部通过（新增8、原35重跑），vue-tsc类型检查与Vite生产构建通过。累计254方法；211个Python方法沿用018，不声称本轮重跑PG/SDK/Runtime。无新增依赖、API字段、SQL迁移或真实模型请求。

| AC | 结果 |
| --- | --- |
| 1901 | 输入/输出分别汇总和覆盖；部分缺失时未知而非部分和，无LLM与真实0区分；两次9223372036854775807精确相加为18446744073709551614。排除非模型/其他trace/映射，重复ID只计一次；异常取消带用量仍保留，非法类型/负值/超范围单项不强制转换 |
| 1902 | 实际Vue详情SSR经既有lossless API解码，显示精确大整数与节点原用量；未知、0、无模型及数据覆盖文案核对。初次两项SSR断言未考虑Vue scoped样式自动属性，改为允许额外属性后43项全通过，未改变业务逻辑绕过测试 |
| 1903 | 浏览器访问当前生产构建+本机合成API：完整大整数/部分缺失/无模型/真实0四种状态；截图核对小窗口长数字换行，无截断。最终增大范围说明字号并重建/重新加载核对。无真实Collector/PG新增端到端验收 |

前端入口（dashboard目录）：

```text
node node_modules/vitest/vitest.mjs run
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit
node node_modules/vite/bin/vite.js build
```

## 证据与边界

[validation.json](validation.json)保存范围和计数；artifacts/usage-tests.json为最终43项Vitest机器结果，artifacts/trace-usage/partial.png为合成数据浏览器截图。临时页面服务仅回环地址、不使用用户凭证/业务数据，核对后关闭；未启动Docker或调用Provider。前端只消费既有详情协议，OpenAPI仍为011、迁移仍为1..4，62 pins及44来源不变。

只对当前已接收v2模型节点负责，覆盖率不证明Trace到齐、Provider账单完整或覆盖内部重试/未接入调用。费用不估算、无服务端用量聚合/列表筛选。后续节点到达需重新加载详情，节点级数据继续保留。私有开发准备边界沿用018，未创建/推送GitHub仓库。
