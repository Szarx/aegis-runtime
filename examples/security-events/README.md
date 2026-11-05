# 安全事件示例Agent

运行真实Runtime和SDK/OTLP，生成安全事件中心可查询的合成数据，无LLM、外部模型凭证或实际业务存储。`write_record`只增加内存计数；异常/取消分别模拟已经进入业务函数的情况。

## 运行

先按[快速开始](../../docs/quickstart.md)启动Collector、PostgreSQL及Dashboard。仓库根目录激活开发环境，安装SDK、Policy、Runtime与Collector：

```text
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e ./sdk/python -e ./policy-engine -e ./runtime -e ./collector
python examples/security-events/agent.py --endpoint http://127.0.0.1:8000/v1/traces --count 25
```

地址需要替换为本机Collector实际端口；配置了Collector Trace token时，先在本机环境变量AEGIS_API_TOKEN中设置同一个值，不要写进源码、命令参数或聊天。Dashboard以同一Trace token连接，打开“安全事件”。示例只读取这一个变量，不需要审批凭证。

默认25次尝试，每种5次：允许完成、显式拒绝、允许后异常、允许后取消、缺身份拒绝。预期completed5、denied10、error5、cancelled5、business_calls15；SDK成功导出50Span，事件总数新增25。每次重新运行会创建新Trace和Action，已有数据不会被清空；用服务security-events-example精确筛选。count允许1..100。

## 验收

需要离线排查时，按[导出指南](../../docs/security-export.md)使用服务筛选导出事件并离线verify。该CLI只用标准库，不运行Agent或工具；原始整数使用JSONL保真。

页面第一页20条、第二页5条；筛选拒绝10条，异常/取消各5条，上报身份demo-agent20条。点击任一事件可看到Agent与治理工具两个Span。未绑定身份保持null；拒绝不进入业务函数。JSON输出包含计数及SDK诊断，导出失败时进程返回非零；这只能证明传输结果，仍应查询Collector确认存储。

同一Action可有多条治理记录，查询按Trace/Span区分。事件只是已上报遥测，不是可信认证或不可篡改审计。详细API与边界见[安全事件说明](../../docs/security-events.md)及[SPEC-020](../../specs/020-security-events/spec.md)。
