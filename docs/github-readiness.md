# GitHub 私有仓库准备

2026-10-23：用户选择先准备私有仓库。许可证仍未选定，不添加授权文本，不切为公开，不创建Release或发布PyPI/npm包。当前是开发快照，不是生产治理平台承诺。

## 上传前检查

SPEC-046 增加 Git 对象检查。运行 `python scripts/repository_check.py --staged` 核对首个提交将使用的树。提交后用 `python scripts/repository_check.py --commit HEAD` 核对实际提交中的文件，并确认两个报告的 `tree` 相同。工作树、暂存树、已提交的树可以包含不同内容。检查报告提供文件数量、树标识与问题类别，凭证模式仍是有限覆盖。

安装后的统一检查入口见[私有快照验收](snapshot-check.md)：`python scripts/snapshot_check.py --postgres`。需要专用测试数据库和已安装Node，输出独立报告并核对前后候选源摘要；SPEC-041已完成真实整体验收，具体候选摘要与运行范围以其任务和本机报告为准。

从aegis根目录安装requirements-dev.lock及四个本地包，运行：

```text
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e ./sdk/python -e ./policy-engine -e ./runtime -e ./collector
python -m pip check
python scripts/repository_check.py
python scripts/check.py
```

真实数据库回归需设置AEGIS_TEST_DATABASE_URL指向专用可删除测试schema的PostgreSQL，再运行 `python scripts/check.py --postgres`。各组件使用独立子进程，避免重名测试模块冲突；任何skip不判为通过，结果在artifacts/check。不要指向生产数据库。

Dashboard在dashboard目录运行 `npm ci`、`npm test`、`npm run build`。Windows npm执行环境受限时，已验证可直接使用Node执行本地vitest/vue-tsc/vite入口。依赖缓存、artifacts、tmp、venv和node_modules均不提交。

默认的 repository_check 检查 Git 跟踪文件和未忽略的工作树文件，只报告路径与问题类别。提交前用 `git diff --cached --check` 检查格式，用暂存和提交模式核实实际文件字节。已有远端或历史需要单独审查。

## CI范围

[ci.yml](../.github/workflows/ci.yml)在push/pull_request/manual触发：Python3.12/PostgreSQL16运行全部Python，Node22运行前端测试和构建。仅contents:read、checkout不保留凭证、官方Actions固定提交，无发包/部署job，不需要真实模型密钥。远端首次执行仍需验证，尤其Linux环境和在线依赖下载；本机Windows通过不能当作GitHub CI通过。

固定action的声明已核对官方源：[checkout](https://raw.githubusercontent.com/actions/checkout/11bd71901bbe5b1630ceea73d27597364c9af683/action.yml)、[setup-python](https://raw.githubusercontent.com/actions/setup-python/a26af69be951a213d495a4c3e4e4022e16d87065/action.yml)、[setup-node](https://raw.githubusercontent.com/actions/setup-node/49933ea5288caeca8642d1e84afbd3f7d6820020/action.yml)。不声称这些是最新版本；后续更新需明确复核。

## 两个不同的门槛

私有开发仓库的首次交付要求本机回归和构建通过、目标归属与私有属性核实、提交树检查通过，以及推送后的远端 SHA 核对。GitHub Actions 结果按该 SHA 单独记录。首次上传见 [SPEC-046](../specs/046-private-github/tasks.md)。

公开仓库：需用户选定许可证与公开分发命名，确认README能力边界、维护者联系/安全报告渠道和公开前文件/历史复核，并在私有远端先运行CI。真实Provider、新框架和人工5分钟接入未验收的部分继续注明，不要求为了公开预览冒称全部路线图完成。正式包版本发布另设版本/安装/兼容验收。

就绪证据见 [SPEC-018](../specs/018-private-repository/tasks.md)。达到私有上传门槛时会明确告知用户，公开发布时再次单独确认。

SPEC-020已更新本机证据：272项方法（221 Python含40真实PG、51前端）、类型/构建、Collector本地wheel安装与兼容契约、候选文件检查均通过，见[020验收](../specs/020-security-events/tasks.md)。当前仍可准备上传GitHub私有开发仓库；未建立远端、推送或运行GitHub CI，公开许可证门槛保持。

SPEC-027最新本机回归为366项（315 Python含49真实PG、51前端），配置持久化审批图与全新安装已验收，见[027记录](../specs/027-configured-graph/tasks.md)。仍可上传私有开发快照；未创建远端、提交、推送或运行GitHub CI，公开许可未定。候选集检查只覆盖当前工作树有限规则。

SPEC-028更新为381项（330 Python含51真实PG、51前端），统一图调用/流生命周期、真实模型工具合成矩阵和全新安装通过，见[028记录](../specs/028-managed-graph-stream/tasks.md)。私有快照就绪状态保持；仍无远端创建/推送/CI或公开许可，既有GUI/生产构建证据继承020。

2026-10-26，SPEC-035最新完整回归403项（339 Python含52真实PG、64前端），无skip；统一前端类型/构建/产物预算通过。029–034已在隔离服务及编译后preview逐项核对视觉、队列/节点工作流、加载/故障恢复、窄屏与受测点击/对比度；035补齐可复现合成演示，见[最新验收](../specs/035-dashboard-demo/tasks.md)。本机候选和依赖/协议/文档检查通过；仍未建立远端或运行GitHub CI，维持私有快照门槛与公开许可限制。

2026-10-28，SPEC-041完整统一回归435项（348 Python含52真实PG、87前端）全部通过，无skip；依赖、候选检查、类型/构建/固定资源预算及实际资源哈希通过，运行前后候选字节摘要一致。见[041记录](../specs/041-snapshot-check/tasks.md)。可以作为GitHub私有开发快照上传准备；实际创建仍需所有者/仓库名，未创建远端或执行CI。后续修改文件后须重新核对对应候选报告。

2026-10-29，SPEC-042最新完整回归444项（357 Python含53真实PG、87前端）通过，无skip；类型/构建/预算与候选摘要核对通过。新增只读平台诊断见[042验收](../specs/042-platform-diagnostics/tasks.md)。仍仅达到本机私有开发快照门槛，未创建远端或运行GitHub CI；公开许可未定。
