# 合成审批准备示例

本例只创建数据库记录，不调用业务工具或模型。批准不会改变现有 Runtime 策略。

先按 [审批接入](../../docs/approvals.md) 配置 Collector 的独立 producer/reviewer 凭证，并安装 SDK、Policy、Runtime。宿主显式提供至少 32 字节绑定密钥；本例从本机 AEGIS_APPROVAL_BINDING_KEY 读取十六进制值，生产配置应由宿主管理，勿提交到仓库。

```text
python examples/approval-records/prepare.py --endpoint http://127.0.0.1:8000
```

默认生成新 action_id。仅在同一请求的网络结果未知时显式用 `--action-id` 重试，不能更改参数、策略、摘要或有效期。打开 Dashboard 的“审批准备”，使用 reviewer token 查看并记录决定。刷新页面后需重新提供 reviewer token。summary 不自动包含参数，HMAC 无法直接还原参数，当前示例不构成真实业务执行授权。
