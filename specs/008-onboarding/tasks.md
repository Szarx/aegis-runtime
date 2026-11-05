# SPEC-008 任务

状态：本地安装/Trace 流程及 Docker 恢复后的缓存平台流程验收完成，2026-10-18。人工首次接入和冷启动目标未验收。

- [x] T801：冻结首次有效 Trace、机器耗时与人工接入的不同口径。
- [x] T802：实现独立环境快速开始与分阶段 receipt。
- [x] T803：失败/隐私/数据校验的针对性测试。
- [x] T804：native / langgraph 全新 venv 实际验证和缺缓存失败验证。
- [x] T805：更新快速开始、README、路线图与结果；平台/人工目标保持准确。
- [x] T806：Docker 恢复后独立项目、新库、OTLP/查询/实际页面和连续分阶段计时；保留卷完成收尾。

## 实际命令与结果

Windows / Python 3.12.14，使用 SPEC-006 已校验官方 wheel 缓存；每次全新 venv，include-system-site-packages=false，不继承 PYTHONPATH/PYTHONHOME，不使用旧环境安装的 SDK。安装从本地源码构建，pip check 均通过。

```text
python scripts/quickstart.py --profile native --wheelhouse tmp/wheels --runs-dir "artifacts/onboarding acceptance"
python scripts/quickstart.py --profile langgraph --wheelhouse tmp/wheels --runs-dir "artifacts/onboarding acceptance"
```

| 阶段（秒） | native | langgraph |
| --- | ---: | ---: |
| venv | 14.576 | 10.589 |
| setuptools | 8.737 | 6.586 |
| SDK 构建/依赖安装 | 9.175 | 144.183 |
| pip check | 0.757 | 6.419 |
| 示例新进程 | 0.356 | 9.522 |
| JSONL 校验 | 0.021 | 0.012 |
| 从创建环境到首个有效 Trace | 33.623 | 177.311 |

native 共 7 个包（含 pip、setuptools、SDK），没有 OpenAI / LangGraph / LangSmith；langgraph 共 46 个包。两者均没有 FastAPI / Psycopg / OTLP Exporter，不强制安装整套 59 项开发依赖。实际包版本保存在 [validation.json](validation.json)。

native 得到 2 Trace / 4 Span，成功/预期失败各一对 Agent→Tool；langgraph 得到 1 Trace / 4 Span，1 Agent / 2 LLM / 1 Tool，baseline / traced 输出与 2 模型 / 1 工具计数一致，7/3 用量均为合成值。诊断 failed/dropped/pending/export_failures/instrumentation_failures 均为零。

实际运行使用含空格输出目录。两套安装环境随后从仓库外工作目录重跑实际示例，使用最终校验器再次验证输出，初始耗时不因重跑而覆盖。原始记录位于忽略目录 artifacts/onboarding acceptance；仓库摘要不含本机绝对目录或原始输出。

另从仓库外目录使用空 --wheelhouse 启动：venv 成功，build-prerequisite 固定缺包退出码 1，约 21.459 秒；没有执行 sdk-install 或 example，没有 first_valid_trace_ms，不回退网络。失败 receipt 和旧成功目录均保留。

## 针对性测试

```text
python -m unittest tests.contract.test_onboarding -v
python -O -m unittest tests.contract.test_onboarding -v
```

8 个新方法通过（最终 -O 运行约 0.475 秒），覆盖丢失/重复 Span、父子关系错、错误模型用量、业务计数变化、诊断失败、坏 JSONL、凭证环境隔离、真实进程非零/超时、启动错误与保留旧目录。即使 Python 优化模式启用，验收检查也不会被禁用。

初次沙箱运行遇到 Windows 临时目录写权限限制，改用工作区 tmp 作为 TEMP/TMP 并在允许子进程的环境重跑后通过；该失败不作为产品通过证据。既有 SDK/Collector/Dashboard 源码未改，SPEC-007 的 108 方法证据沿用，没有声称本轮重跑全套 116 方法或重新构建页面。

## 交付与限制

入口 [scripts/quickstart.py](../../scripts/quickstart.py)，步骤和排查见 [快速开始](../../docs/quickstart.md)。receipt 为 aegis.onboarding.v1，保留阶段状态/耗时与固定错误分类，不复制 raw stdout/stderr、环境或命令参数。平台和人工接入字段保持 not_run。

交付检查通过 70 份 Markdown / 266 个本地链接、167 个源文件/文档/配置的凭证模式扫描、脚本 Python 编译、产物忽略及未变 OpenAPI。59 个本地 Windows wheel 的 SHA256 与既有官方下载凭据逐项一致；没有重新下载或改写历史凭据。

首次本地验收零新增 Provider 请求，无新依赖版本或外部资料下载。默认在线安装分支已提供，但未测真实 PyPI 下载时间；使用预装 Python、已有源码和官方缓存，结果不能外推为冷启动或人类 5 分钟接入保证。当时 Docker Linux Engine 不可用，原始 validation.json 保留该时点的平台 not_run；Docker 恢复后的单独续验如下。新用户人工修改与完整冷启动 10 分钟体验继续保留未验收。

## Docker 恢复后的 AC806 续验

用户启动 Docker 后，实际连接 Engine 29.7.2；完成 SPEC-007 的遗留 down 并确认旧卷保留。使用新的 aegis-spec008-check 项目、动态回环端口和全新数据库卷，初始 API Trace 数量为 0。源码、基础镜像/依赖缓存、上轮安装好的 SDK venv 已存在；不重复安装 Python 或把旧机器安装时间相加。

```text
docker compose -p aegis-spec008-check up -d --build --wait --wait-timeout 120
```

测试进程将三个发布端口设为 0，使用独立合成开发 token。native / langgraph 在各自 venv 用 --no-index / --find-links 和原约束文件补装 sdk/python[otlp]，pip check 通过，再运行原示例的 --endpoint。全过程没有真实模型请求。

| 阶段 | 毫秒 | 口径 |
| --- | ---: | --- |
| Compose 构建/启动至三服务健康 | 26231.565 | 独立项目、新卷；已有镜像/依赖缓存 |
| native OTLP extra 安装 | 14479.555 | 在既有原生 venv 补装，本地 wheel 缓存 |
| native pip check | 1367.418 | 新增依赖一致性 |
| native 示例 HTTP 执行 | 972.512 | 合成成功/失败、flush 与 shutdown |
| 起点至首次 HTTP 查询完成 | 44292.792 | 累计，含端口发现及父子/状态校验 |
| 起点至页面列表+详情首次确认 | 107887.062 | 累计上界，含浏览器/工具操作间隔，不是首屏性能 |
| 随后的 LangGraph OTLP 安装 | 7009.611 | 页面确认后独立步骤 |
| LangGraph pip check | 1153.464 | 依赖一致性 |
| LangGraph 示例 HTTP 执行 | 4425.843 | baseline / traced 一致 |

原生形成 2 Trace / 4 Span（成功和预期失败），LangGraph 形成额外 1 Trace / 4 Span；总计 3 Trace / 8 Span。HTTP 和直接 PostgreSQL 均核对数量、父子关系、状态筛选 UNSET=2 / ERROR=1，迁移集合 {1,2}，三个服务健康。两个 SDK 的失败/丢弃/pending/导出失败/观测失败均为零，graph_outcome 为 null 与非图流式场景一致。

实际浏览器先确认原生列表与 Agent→Tool 异常详情，再手动刷新看到 LangGraph 新增记录，核对 1 Agent / 2 LLM / 1 Tool、Provider=deepseek 和合成 7/3 Token。截图保存在 artifacts/platform-onboarding/native-detail.jpg、langgraph-detail.jpg。元数据和计时证据见 [platform-validation.json](platform-validation.json)，不覆盖首次本地测量快照。

临时浏览器标签已关闭，aegis-spec008-check 已 down，确认同项目剩余容器为 0；aegis-spec007-check_postgres_data 和 aegis-spec008-check_postgres_data 均保留。其他 Docker 项目未改动。本轮无产品源码改动或新增自动化方法，既有测试证据不重复计数；本次新增的是实际部署/HTTP/数据库/页面验收。在线下载与人工 5 分钟目标仍未验收。

续验后的交付检查通过 70 份 Markdown / 272 个本地链接、168 个文件的凭证模式扫描、当前 OpenAPI 和依赖基线、截图/状态文件忽略规则。初次本地验收的摘要保留，其 follow_up_platform_receipt 指向最新平台结果。
