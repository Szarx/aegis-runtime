# 已有 LangGraph Agent 接入配方

先阅读 [选择与步骤](../../docs/existing-agent.md)。本例使用真实 LangGraph / ToolNode 与官方 OpenAI SDK，模型响应完全来自合成 HTTP transport，不连接 DeepSeek/OpenAI/LangSmith，不需要模型密钥。

在仓库根目录、已安装锁定开发依赖与本地 SDK / Policy / Runtime 的环境中运行：

```text
python examples/existing_agent/run.py --mode baseline
python examples/existing_agent/run.py --mode observe
python examples/existing_agent/run.py --mode allow
python examples/existing_agent/run.py --mode deny
```

每条加 `--async` 可验证原生异步 Agent。默认新建 artifacts/existing-agent 下的独立目录；可用 --runs-dir 指定父目录，不覆盖旧结果。

| 文件 | 职责 |
| --- | --- |
| application.py | 原应用，真实模型/工具循环，无 Aegis 导入 |
| host_before.py / host_after.py | 宿主接线前后，只差一行导入 |
| adapter.py | 包装客户端、工具、图；观测与 Runtime 明确选择 |
| run.py | 宿主管理客户端/SDK生命周期，独立构建 baseline 和目标运行 |
| verify.py | 按本例契约核对 JSONL 和执行计数，错误证据拒绝通过 |

每次运行先独立运行 baseline，再运行目标模式；receipt 中 counts 是目标模式次数，execution_and_validation_ms 包含两次运行与flush/校验，不包含解释器启动、导入、安装或人工接入。baseline 模式不初始化 SDK、不产生 Span；其他模式产生1 Agent / 2 LLM / 1 Tool Span。LLM耗时来自调用前后时间戳，包含客户端与合成HTTP处理，不是模型推理或首Token时间。

observe/allow 保持完整业务消息与次数一致：模型2、工具1。deny 故意改变行为：模型2、业务工具0；已有ToolNode捕获拒绝后模型收尾，equivalent_to_baseline=false是期望结果，工具Span为denied/ERROR，不代表真实工具失败或执行过。

终端只输出状态和receipt路径；JSONL无合成参数/消息正文。receipt不保存业务输出、异常正文、密钥或用户绝对路径。错误返回码1并保存固定失败类别；缺少依赖或参数错误可能在创建receipt前失败，先检查安装和CLI参数。

这个一行差异只计算两个宿主示例的导入替换，不包括adapter.py、初始化/关闭代码、安装或用户真实项目改造。尚未验收人工5分钟接入，已有006/008示例与本配方均属于合成验证。
