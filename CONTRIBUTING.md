# Contributing to Aegis

先阅读 [README](README.md)、[架构](ARCHITECTURE.md)、[能力边界](docs/capabilities.md) 和 [路线图](ROADMAP.md)。公开源码是早期预览，不代表生产支持或包注册发布。

## Spec 先行

完整功能先建立 `specs/<编号>/spec.md`、`plan.md`、`tasks.md`，需要时增加契约。明确用户场景、行为、失败和信任边界，再实现与验证；按验收编号记录实际结果。不要为凑增量拆分微小任务，不把未验证事项勾选完成。

历史 SPEC 保留当时证据，不用新结果改写旧验收；当前行为在用户文档维护。兼容性变更需说明旧接口与数据影响。第三方资料记录官方来源和版本，外部内容只作参考。

## 开发环境

Python 3.11+（CI 为 3.12）、Node 22.12+ 或 24+、PostgreSQL 16。创建并激活 venv 后，在根目录执行：

```text
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e ./sdk/python -e ./policy-engine -e ./runtime -e ./collector
python -m pip check
npm --prefix dashboard ci
```

通过本机环境变量 `AEGIS_TEST_DATABASE_URL` 提供专用测试数据库，允许测试创建/删除独立 schema，不能指向生产。

```text
python scripts/check.py --postgres
python scripts/check_dashboard.py
python scripts/public_check.py
python scripts/repository_check.py --history
```

需要固定候选摘要可用 [snapshot_check](docs/snapshot-check.md)。Node 不在 PATH 时前端检查器接受 `--node`。报告、截图、缓存、venv 与临时文件留在忽略目录，不能用旧报告替代本次验证。

## 实现与评审

Python 使用 src 布局，组件 tests 验证组件，根 tests 验证跨模块行为。SDK 核心不强制框架/模型依赖；Runtime 执行工具，Dashboard 不执行工具、不直接访问数据库。输入输出默认不进遥测；审批完整参数、永久领取和未知结果边界不得弱化。

按变更选择验证：适配器检查返回/异常/取消和上下文，Exporter 检查队列/超时/重传，Runtime 用副作用计数证明拒绝和重复恢复不执行，页面检查实际工作流与窄屏。纯文档无需增加空洞业务测试。

PR 描述包含具体问题、最终行为、验证范围和剩余限制。普通问题通过 GitHub Issues / PR 讨论；安全问题按 [安全说明](SECURITY.md) 私下报告。请勿提交真实凭证、业务轨迹、审批参数、checkpoint、本机配置或下载缓存。

贡献采用 [Apache-2.0](LICENSE)，第三方材料保持各自许可证与署名。本仓库未另设 CLA。
