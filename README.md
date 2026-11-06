# Aegis

**Runtime governance for existing AI agents.** Trace model and tool calls, enforce local tool policies, and review sensitive actions before explicit execution.

Aegis 接入已有 Agent，让执行过程可读、工具操作可控、人工决定可追溯。平台本身不依赖 LLM，也不需要模型密钥。

**当前为早期公开预览，版本 `0.1.0.dev0`。** 适合本地试用和集成验证；尚无生产身份、多租户、分布式恢复或完整审计保证。项目使用 [Apache-2.0](LICENSE)，尚未向 PyPI/npm 发布安装包。

## 能做什么

| 能力 | 当前支持 |
| --- | --- |
| 观测 | Python Agent / Tool、OpenAI 兼容客户端、DeepSeek、显式 LangGraph 四类调用；父子关系、生命周期耗时、可获得的 Token 用量 |
| 工具治理 | 本地 Policy：allow / deny / require_approval；同步/异步工具与配置驱动接入 |
| 人工审批 | 独立申请、审核、执行角色；完整参数审阅、宿主显式单次领取/恢复；受约束的本机 SQLite 审批图恢复 |
| 排查 | 执行轨迹、树/时间线、慢调用、治理事件筛选与导出、候选策略离线回放 |
| 运行健康 | 可选 SDK 心跳、活动 Trace 和队列/失败计数；单 Collector 进程内的失联快照 |

只记录明确接入的调用，不自动发现任意模型调用，也不获取模型内部思维。单独的 `@tool(permission=...)` 仅标注元数据；执行拦截需要 Runtime。完整支持与限制见 [能力边界](docs/capabilities.md)。

## 从源码试运行

需要 Git、Docker Desktop / Docker Compose v2、Python 3.11+。以下步骤不需要模型账户；实际耗时取决于镜像与依赖下载。

```text
git clone https://github.com/Szarx/aegis-runtime.git
cd aegis-runtime
docker compose up -d --build --wait
```

打开 **http://127.0.0.1:8080**，输入本地默认查询 token `aegis-local-dev`。连接前可点“打开合成轨迹演示”，或直接访问 **http://127.0.0.1:8080/#/demo**；合成演示无需认证。平台首次启动没有真实 Agent 数据。

创建并激活 Python 环境：

```text
python -m venv .venv
```

PowerShell 执行 `.venv/Scripts/Activate.ps1`；macOS / Linux 执行 `source .venv/bin/activate`。随后安装锁定依赖与四个本地包：

```text
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e ./sdk/python -e ./policy-engine -e ./runtime -e ./collector
```

PowerShell 运行合成示例：

```powershell
$env:AEGIS_API_TOKEN = "aegis-local-dev"
python examples/native-python/agent.py --endpoint http://127.0.0.1:8000/v1/traces
python scripts/dashboard_demo.py --attempts 12
python scripts/platform_check.py --base-url http://127.0.0.1:8000
```

macOS / Linux 先执行 `export AEGIS_API_TOKEN=aegis-local-dev`，再运行相同的三条 Python 命令。刷新 Dashboard 可查看成功/失败 Trace、合成模型与策略允许/拒绝事件；这些命令不请求真实模型。只体验 SDK 可单独运行 `python scripts/quickstart.py`。

端口冲突时复制 [`.env.example`](.env.example) 为 `.env` 调整端口，并相应修改示例 endpoint。默认仅绑定 localhost；首次构建联网访问官方镜像、PyPI 和 npm 源。停止用 `docker compose down`，保留数据库卷。排障、角色配置与数据说明见 [本地部署](deploy/docker/README.md)。

## 接入自己的 Agent

```python
import aegis
from aegis import observe, tool

aegis.init(service_name="my-agent", output_path="artifacts/my-agent.jsonl")

@tool(permission="orders.read")
def lookup_order(order_id: str):
    return {"order_id": order_id, "status": "ready"}

@observe
def run_agent(order_id: str):
    return lookup_order(order_id)

try:
    run_agent("synthetic-order")
    aegis.flush()
finally:
    aegis.shutdown()
```

LLM 调用另用模型 Wrapper，已有图用 LangGraph Adapter；权限判断和审批另接 Runtime。

- [已有 Agent 接入](docs/existing-agent.md) / [配置驱动接入](docs/application-onboarding.md)
- [OpenAI 离线示例](examples/openai/README.md) / [DeepSeek](examples/deepseek/README.md) / [LangGraph](examples/langgraph/README.md)
- [外部官方 ReAct 模板完整配方](examples/external_react_agent/README.md)：保留原图，对照基线和合成服务边界
- [策略和人工审批闭环](docs/policy-approval.md) / [运行与采集健康](docs/runtime-health.md)

## 使用边界

遥测队列位于内存，进程异常退出可能丢失未导出数据。正常 Span 在结束后导出；心跳只提供最近活动快照，Collector 重启会清空健康记录。批准不直接执行工具；领取后的未知结果保持已消费，不能通过重试补齐遥测或业务结果。

默认不采集模型/工具输入输出；人工执行审批会显式保存完整参数，接入方必须选择允许披露的动作。静态角色 token、应用上报身份和本地部署不能替代用户认证、租户隔离或防篡改审计。见 [能力边界](docs/capabilities.md) 与 [安全说明](SECURITY.md)。

## 项目与验证

代码按 `sdk/python`、`runtime`、`policy-engine`、`collector`、`dashboard` 分工，示例在 `examples`。SDK 可独立运行；当前服务端为单 FastAPI 应用加 PostgreSQL。

- [文档导航](docs/README.md) · [架构](ARCHITECTURE.md) · [路线图](ROADMAP.md) · [贡献](CONTRIBUTING.md)
- [全部 SPEC 分类与验收](specs/README.md)：历史设计与验收不代表当前状态
- [公开材料与交付检查](docs/github-readiness.md) · [第三方归属](THIRD_PARTY_NOTICES.md)

开发环境运行 `python scripts/check.py --postgres` 验证 Python / 专用 PostgreSQL；前端依赖安装后运行 `python scripts/check_dashboard.py`。公开检查与最终实际结果见 [SPEC-050](specs/050-public-preview/tasks.md)。测试不需要真实模型凭证。
