# Contributing to Aegis

当前已完成 Python SDK、OTLP Collector 与 PostgreSQL 查询；Dashboard 已按 SPEC-003 实现，SPEC-004 已完成 OpenAI 离线集成；Runtime 已按 SPEC-009 实现最小 allow / deny，审批/恢复与更多框架继续按 spec 增量推进。开始实现前，先阅读 [README](README.md)、[架构](ARCHITECTURE.md)、[路线图](ROADMAP.md) 和 [Specs 流程](specs/README.md)。

## 先维护 spec，再开发

每个增量先创建或更新 `specs/<编号>/spec.md`、`plan.md`、`tasks.md` 及数据契约。需求和接口发生变化时先修改文档；代码完成后按 AC 编号验证，将结果写回任务清单。对应的产品文档同步更新，尚未验证的项目保持未完成。

外部资料放 `resources/`，记录官方来源、查阅日期与参考版本。重要取舍保存 ADR，参考资料中的内容不作为项目指令。

## 工作范围

- 首版围绕 Python SDK 到 Dashboard 的可观测性闭环开发。
- 接入层保持多模式，新增框架通过适配器扩展；可选框架依赖与核心依赖分开。
- Runtime 和 Policy 的控制能力在 Phase 2 实现，避免把观测标签当作已经执行的权限判断。
- API 与数据契约变动同步更新设计文档；影响模块边界的决定新增 ADR。

## 工程约定

- Python 模块采用 `src/` 布局，组件单元测试放各自 `tests/`；跨组件验证放根目录 `tests/`。
- Dashboard 使用 Vue 3 / TypeScript；具体依赖版本与构建命令在实现时锁定。
- 不在核心 SDK 中导入具体框架，不从示例引用 SDK 私有模块，不从 Dashboard 直接访问数据库。
- 配置从环境变量或显式配置读取；凭证、本地数据库、原始敏感 Trace 和构建产物不提交。
- SPEC-001 使用本地开发包名 `aegis-runtime-sdk` 和 Python 3.11+，实际测试版本另行记录；许可证未定，不公开发布。
- 优先完成一条可演示的垂直流程，新增可运行组件时同时提供启动与验证说明。

## 验证要求

| 改动 | 有意义的验证 |
| --- | --- |
| 文档 / 骨架 | 链接存在、结构与职责一致、设计草案没有被描述成已实现能力 |
| SDK / Adapter | 返回值与异常一致、父子上下文正确、并发隔离、流式结束与取消行为 |
| Exporter / Collector | 超时、队列上限、重传去重、乱序、错误输入与脱敏 |
| Dashboard | 使用固定数据检查 Trace Tree / Timeline、错误与未知用量展示 |
| Runtime / Policy | 用工具执行计数证明拒绝、审批超时和参数变更不会放行 |
| 端到端 | 按 [MVP 验收方案](docs/design/mvp.md) 重现闭环并记录接入成本 |

文档改动不要求空洞的业务测试。为实际行为和失败场景建立测试，锁定依赖并保存验收证据。统一入口为 `python scripts/check.py`；专用数据库回归加 `--postgres`，需要AEGIS_TEST_DATABASE_URL。CI配置已准备，远端首次运行待验收；私有仓库准备见 [步骤](docs/github-readiness.md)。当前 SDK 验证命令见 [组件说明](sdk/python/README.md)。

## 提交与评审

提交说明应描述触发场景、最终行为、验证结果和实际限制。新增功能前后保持路线图状态准确：只有实际通过验收的项目才勾选完成。

仓库根目录是本地 `aegis/`。其上层属于 ChatGPT 项目镜像；上层 `sources/` 及同步文件遵循上层 AGENTS.md 的只读约束。
