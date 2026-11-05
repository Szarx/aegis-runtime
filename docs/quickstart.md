# 首次本地接入

需要已安装的 Python 3.11+ 和本地 Aegis 源码；本次实测 Windows / Python 3.12.14。SDK 尚未公开发布，下面从当前仓库安装。默认不调用模型服务、不需要模型 Key，也不需要 Docker、Node 或数据库。

## 一条命令生成并验证 Trace

在仓库根目录执行：

```text
python scripts/quickstart.py
```

命令会创建独立的 artifacts/onboarding/native-* 目录与虚拟环境，从官方 PyPI 安装核心 SDK 依赖，运行已有原生 Agent，并自动验证成功/合成失败的 2 条 Trace、4 个 Span 和父子关系。不修改当前 shell、不复用或覆盖已有 .venv。安装和每个子进程默认最多 180 秒，可用 --timeout-seconds 在 1–1800 秒间调整。

真实 LangGraph、合成模型和工具循环：

```text
python scripts/quickstart.py --profile langgraph
```

会选择 langgraph / deepseek extras，运行真实 StateGraph / ToolNode。接入前后输出和两次模型/一次工具调用保持一致；验证 1 条 Trace、4 个 Span、父子关系与每个模型 7/3 的合成 Token。没有真实 DeepSeek / OpenAI 或 LangSmith 请求。该 profile 不依赖 Collector / OTLP。

默认安装需要访问 PyPI。已有适合当前系统/Python 的官方 wheel 缓存时，可完全禁用包索引：

```text
python scripts/quickstart.py --profile native --wheelhouse tmp/wheels
python scripts/quickstart.py --profile langgraph --wheelhouse tmp/wheels
```

tmp/wheels 为本机验收缓存，不随 Git 分发；新用户没有该目录时使用默认在线方式。Docker wheelhouse 可能只有 Linux 二进制，不能替代 Windows 缓存。缺包会立即失败，不回退网络。本次实际验证为新环境 + 已缓存官方 wheels，未测在线下载时间。

## 找到并理解结果

终端最后输出 Result 与本次 receipt.json 路径。目录内包含：

| 文件 | 用途 |
| --- | --- |
| receipt.json | 各阶段状态/耗时、导出诊断、已校验 Trace/Span 数与验收边界 |
| traces.jsonl | 本次合成示例的本地 Span 元数据，非 OTLP 请求体 |
| venv/ | 本次独立安装，可继续用于已有 Agent 接入 |

只有所有阶段成功且数据校验通过才返回退出码 0。first_valid_trace_ms 从创建环境开始，到示例执行、flush 和 JSONL 校验完成为止；不包含安装 Python、取得源码、用户阅读或手工接入，更不包含页面首次可见时间。平台与人工接入验收字段保持 not_run。

每次运行使用新目录，不删除旧记录。--runs-dir 可指定其他存放目录；建议仍放 artifacts 内，避免把虚拟环境、Trace 和本机路径加入 Git。receipt 不保存子进程原始输出、凭证、环境变量或绝对用户路径；终端只打印本机结果路径和固定阶段。原生 profile 不运行 baseline / traced 对照，因此 business_comparison_verified 为 null，真实 LangGraph profile 成功后为 true。

## 接入自己的 Agent

SDK 已安装在本次 venv，可在自己的程序中初始化并标记入口与工具：

```python
import aegis
from aegis import observe, tool

aegis.init("my-agent", output_path="artifacts/my-agent/traces.jsonl")

@tool(permission="orders.read")
def lookup_order(order_id):
    return existing_lookup(order_id)

@observe
def run_agent(query):
    return existing_agent(query)

try:
    result = run_agent("synthetic test query")
finally:
    aegis.flush()
    aegis.shutdown()
```

将 existing_lookup / existing_agent 替换为已有代码，并把已标记工具传入 Agent。装饰入口不能自动发现内部模型/工具；permission 仅是观测元数据。LLM 客户端需对应 Wrapper，已有编译图用 observe_graph；详见 [LangGraph 示例](../examples/langgraph/README.md) 和 [SDK](../sdk/python/README.md)。先用合成输入验证行为与调用次数，再接真实业务。

## 继续到 Collector / Dashboard

先确认 `docker info` 能连接 Engine，再按 [本地部署](../deploy/docker/README.md) 执行 `docker compose up -d --build --wait`。该阶段需要镜像/前端依赖和独立计时，不包含在上面的 SDK 结果中。

若要沿用快速开始环境发送 OTLP，需要再安装 otlp extra。PowerShell 示例，将 $run 改为刚输出的目录：

```powershell
$run = "artifacts/onboarding/native-本次目录"
& "$run/venv/Scripts/python.exe" -m pip --isolated install --index-url https://pypi.org/simple --no-build-isolation --constraint requirements-dev.lock "./sdk/python[otlp]"
$env:AEGIS_API_TOKEN = "aegis-local-dev"
& "$run/venv/Scripts/python.exe" examples/native-python/agent.py --endpoint http://127.0.0.1:8000/v1/traces
```

Linux/macOS 将解释器路径改为 venv/bin/python，并按 shell 设置相同 token。打开 `http://127.0.0.1:8080`，输入与 Collector 配置一致的 token，检查成功/失败记录和两个 Agent→Tool 链路。页面 token 只保存在内存。停止服务用 `docker compose down`，保留数据卷。

Docker 恢复后已在独立项目/新库实际验证上述 OTLP 补装到页面的流程：缓存环境约 26.2 秒三服务健康、44.3 秒完成首次原生查询、107.9 秒确认列表与详情。最后一项包含工具操作间隔，是可见性确认的上界；沿用已安装的 SDK 环境，不能与前一轮 SDK 安装时间相加冒充冷启动。原生与 LangGraph 共 3 Trace / 8 Span 已核对，见 [平台续验](../specs/008-onboarding/tasks.md)。快速开始脚本本身仍不启动 Docker，其 receipt 的平台字段保持 not_run；独立平台结果保存于 [platform-validation.json](../specs/008-onboarding/platform-validation.json)。

## 排查失败

| 结果 | 下一步 |
| --- | --- |
| 参数被拒绝 | 检查 Python 版本、profile、超时范围和 wheelhouse 是否存在 |
| venv / process_unavailable | 检查解释器的 venv/ensurepip、目录写权限；不依赖当前 shell 已激活的环境 |
| build-prerequisite / sdk-install 失败 | 缓存需要固定版本 setuptools 及当前平台的完整依赖；默认在线模式检查 PyPI、代理/证书和本机 pip 配置 |
| process_timeout | 查看失败阶段，修复环境或合理提高 --timeout-seconds；新命令会创建新目录 |
| dependency-check 失败 | 本次 venv 的 `python -m pip check` 可定位缺失/冲突，不复用旧环境掩盖问题 |
| example / validation 失败 | 本次环境手动重跑对应 examples CLI，检查 traces.jsonl；不要把缺 Span 或父子关系错误当作接入通过 |
| Docker Engine 不可用 | 先恢复 Docker，再执行部署；不影响本地 JSONL 接入，不代表平台已经启动 |

脚本不会把 pip 或应用的原始报错复制进 receipt；排查时在本机查看，不将含凭证日志贴入聊天或提交仓库。详细契约和实际测量见 [SPEC-008](../specs/008-onboarding/spec.md) 与 [任务记录](../specs/008-onboarding/tasks.md)。5 分钟接入和 10 分钟完整体验仍是待人工验证目标。

已有项目的下一步请参考 [接入选择与步骤](existing-agent.md) 和 [独立配方](../examples/existing_agent/README.md)，区分仅观测、allow/deny与人工审批。

安装前/出现环境问题时可先运行 `python scripts/doctor.py`；它只检查选定发行包版本，不安装或运行Agent。profile和未检查范围见 [预检说明](preflight.md)。

安装之后可运行[平台连通性诊断](platform-diagnostics.md)，区分服务/数据库/查询凭证和指定Trace问题；不运行Agent或写入示例数据。
