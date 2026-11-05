# 合成单次执行示例

仅向仓库忽略的 artifacts/reviewed-execution/tool-calls.jsonl 追加合成记录，不调用LLM或外部业务系统。失败场景先写一条记录再抛异常，证明failed也可能已有部分副作用。不要自动重试。

按 [执行审批接入](../../docs/reviewed-execution.md) 配置本机producer/reviewer/executor三种独立凭证，宿主显式提供AEGIS_APPROVAL_BINDING_KEY（至少32字节的十六进制值）。安装本地SDK/Policy/Runtime包。首次准备：

```text
python examples/reviewed-execution/agent.py prepare
```

记下输出action_id，在Dashboard“执行审批”查看完整参数、工具版本并批准；准备不会调用工具。然后在同一配置下显式恢复：

```text
python examples/reviewed-execution/agent.py resume --action-id YOUR_ACTION_ID
```

成功只写一次，重复恢复被拒绝。`--value` 默认 synthetic-updated；prepare/resume 必须相同。两边都加 `--fail` 可验证写入后业务异常；返回码2，重复恢复仍拒绝。`--endpoint` 仅允许回环HTTP，例如本地测试使用动态端口时需指定完整origin，不含路径。

固定演示参数含64位整数9223372036854775807，页面应按原值展示。所有参数明确披露给本机服务/审核人；不要将secret用于此例。confirmed与unknown的含义、领取响应未知和进程退出处理见接入说明；unknown时不得重试工具。
