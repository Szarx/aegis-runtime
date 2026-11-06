# 接入外部 ReAct Agent 模板

这份配方执行 LangChain 官方 [react-agent](https://github.com/langchain-ai/react-agent/tree/9e516c6d8d4f2025949ad9279c4af147eab0683e) 的固定版本。原图、状态、Context 和提示词保留原字节，来源与校验值见 [upstream.json](upstream.json)。上游 MIT 许可证保存在 upstream/LICENSE，适用于这份第三方源码。

模板原本在 utils.py 构造真实模型，在 tools.py 构造 Tavily 搜索。离线验收把这两个服务边界改为本机合成服务。每轮在新的产物目录复制源码并记录实际差异，固定图里的 ReAct 循环由原始 graph.py 执行。宿主适配与模型桥接集中在 run.py，接入成本需要连同该文件计入。

安装仓库锁定依赖和 SDK、Policy、Runtime。可以先按[首次接入](../../docs/quickstart.md)准备本机 Python 环境。此配方完整离线矩阵使用 requirements-dev.lock，以及三个本地开发包。

在仓库根目录运行，每次选择新的输出目录。

```text
python examples/external_react_agent/run.py --mode baseline --output artifacts/external-baseline
python examples/external_react_agent/run.py --mode observe --output artifacts/external-observe
python examples/external_react_agent/run.py --mode allow --output artifacts/external-allow
python examples/external_react_agent/run.py --mode deny --output artifacts/external-deny
```

baseline、observe 和 allow 的业务摘要应一致，模型调用 2 次，业务工具调用 1 次。deny 在副作用前退出，业务工具调用为 0。observe/allow 的本地 traces.jsonl 包含 1 Agent、2 LLM、1 Tool。摘要比较完整稳定消息内容、工具参数和结果，排除框架随机消息 ID。

## 接入平台与审批

要将 Trace 发送到已有平台，设置 AEGIS_API_TOKEN，并追加 `--endpoint http://127.0.0.1:8000`。模型与搜索服务继续使用合成响应。Dashboard 可按服务 external-react-agent 查找新 Trace。

approval 模式还需宿主配置 AEGIS_APPROVAL_REQUEST_TOKEN、AEGIS_APPROVAL_EXECUTION_TOKEN 和十六进制 AEGIS_APPROVAL_BINDING_KEY。reviewer 在独立页面使用自己的凭证。

```text
python examples/external_react_agent/run.py --mode approval --endpoint http://127.0.0.1:8000 --wait-seconds 300 --output artifacts/external-approval
```

宿主输出 pending 和 Action ID 后，图在 ToolNode 内暂停，工具尚未执行。进入执行审批，按 Action ID 查找并人工决定。然后在该输出目录创建空文件 resume，触发宿主尝试恢复。文件仅触发恢复检查，实际执行仍需当前有效批准及单次领取。

PowerShell 示例

```powershell
New-Item -ItemType File -Path artifacts/external-approval/resume
```

批准时恢复完成且工具执行一次，宿主确认后验证重复领取被拒。拒绝时 report.json 为 approval_unavailable，工具执行 0 次，退出码 1。等待超时则宿主退出，已有审批请求仍按平台有效期处理。

## 范围和成本

配方只支持一个合成 search 调用。checkpoint 和待恢复票据保存在当前进程，宿主必须保持运行。多工具并发、进程重启与真实 Provider 调用需要独立配方。服务边界替换涉及两个文件，Aegis 接入还包括宿主实现、依赖安装、SDK 生命周期与独立 reviewer 配置。

automated_elapsed_ms 从第三方依赖导入前开始，覆盖复制、适配、图导入、运行、审批等待和导出。依赖安装与人工阅读时间单独记录。当前自动化验收不能给出陌生开发者的首次手工接入时间。结果与问题见 [SPEC-048](../../specs/048-external-agent/tasks.md)。
