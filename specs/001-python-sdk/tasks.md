# SPEC-001 任务与验证

状态：已验证（2026-10-13）。每项有实际实现与验证证据；完整平台 MVP 仍未完成。

- [x] T01：维护 spec、API、本地数据契约、方案与官方资源。
- [x] T02：生命周期与 SDK 初始化（AC-08、AC-11）。
- [x] T03：同步/异步装饰器、父子上下文和异常隐私（AC-01–05）。
- [x] T04：有界后台队列、JSONL 导出与诊断（AC-06、AC-07、AC-09）。
- [x] T05：原生 Python 成功/失败示例（AC-10）。
- [x] T06：执行验收测试，记录环境与命令。
- [x] T07：更新 README、ROADMAP、组件说明与设计文档。

## 验证记录

环境：Windows、Python 3.12.14、OTel API / SDK 1.45.1、Semantic Conventions 0.66b1；完整依赖锁定于 [requirements-dev.lock](../../requirements-dev.lock)。Python 3.11+ 是配置的最低目标，其他版本尚未实际验证。

```text
python -m unittest discover -s sdk/python/tests -v
# Ran 15 tests in 0.514s — OK

python -m unittest discover -s sdk/python/tests -k ac09 -v
# 追加完整字段约束后，JSONL / 示例验收再次通过（1 test）。

python examples/native-python/agent.py
# accepted=4, exported=4, failed=0, dropped=0, pending=0
# export_failures=0, instrumentation_failures=0

python -m pip check
# No broken requirements found.
```

Windows 隔离环境在标准库 asyncio 的本机 socketpair 初始化处阻塞，尚未进入 SDK 逻辑；完整异步验收改在隔离环境外运行，全部通过。SDK 没有为此修改业务行为或跳过异步测试。

测试文件：[test_sdk.py](../../sdk/python/tests/test_sdk.py)。测试名称标记 AC 编号，覆盖同步/嵌套、12 个并发异步 Run、上游上下文、原始返回/异常对象、内容隐私、取消、导出错误、队列溢出、flush / shutdown 超时、宿主 Provider、非法配置和本地记录契约。

独立运行示例生成 `artifacts/native-python/traces.jsonl`，2 次 Agent Run / 4 个 Span，成功与失败各一次；无网络模型请求、Collector、数据库或 Dashboard。公开部署、规范完整兼容和框架接入体验尚未验收。

## 下一增量

先建立 SPEC-002，冻结 Collector 的 OTLP 传输与接收契约，再开发服务端。权限/审批继续按 Phase 2 推进。
