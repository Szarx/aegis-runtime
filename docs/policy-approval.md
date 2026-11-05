# 策略驱动的人工审批

Policy v2可声明allow、deny、require_approval；精确匹配范围仍是subject/tool/permission，冲突按deny→require_approval→allow优先，同级按rule ID选定。它是本地宿主绑定策略，不是外部身份认证。缺配置、无匹配、错误继续拒绝。Policy v1保持原二元规则与摘要，第三种规则必须显式使用aegis.policy.v2。

Application v4的工具声明execution=policy、固定tool_revision和graph:null；app.policy_tool显式借用ReviewedClient或AsyncReviewedClient，并要求disclose_arguments=True。必须准备producer/executor两个独立角色及绑定key，不从Trace token推断审批权限。旧配置v1-v3拒绝policy模式/v2策略，升级须明确改版本，配置检查命令为：

```text
python -m aegis_runtime inspect examples/policy-approval/application.json --subject reviewer
python -m aegis_policy explain examples/policy-approval/policy.json --subject reviewer --tool write --permission records.write
```

核心调用接口：

```python
from aegis_runtime.policy_tool import PendingReview

with Application(config, subject="reviewer") as app:
    write = app.policy_tool(existing_write, name="write", client=approval_client,
                            disclose_arguments=True)
    result = write.invoke({"record_id": 1}, summary="更新合成记录")
    if isinstance(result, PendingReview):
        save_ticket(result.record)  # 宿主保存；包含完整审核参数，应按本机敏感文件保管
```

allow绑定完整具名JSON参数/default快照，最后再检查一次allow，然后调用函数并返回原结果。deny抛ActionDenied且零业务执行。require_approval只准备审批并返回PendingReview，无论记录是否已经批准，都不会自动领取或执行。request的同一action_id可显式重准备，但函数不执行；建议宿主在请求前生成并保存ID。invoke的allow分支每次都是一次新调用，不提供业务幂等；不要用invoke替代未知结果的resume重试。

人工决定之后，宿主在原环境或新进程重建同一配置/函数与客户端，显式调用：

```python
result = write.resume(saved_record, {"record_id": 1}, summary="更新合成记录")
print(result.confirmation)  # confirmed 或 unknown
```

异步工具使用await write.invoke / await write.resume，客户端由宿主async with关闭。恢复前重新构造策略、工具版本、完整参数/default、摘要及TTL绑定，并验证record形状和全部绑定；票据不是授权。服务端必须当前已批准、未过期且未消费，之后才可能永久领取一次。待定/拒绝/过期/参数或版本或策略改变都不执行，策略由require_approval变为allow也不能沿用旧策略审批。原reviewed/reviewed_graph模式保留强制审批下限，策略allow不会使它们自动执行。普通Runtime.tool遇第三决策则失败关闭，不能凭装饰器自动开通审批。

并发最多一个成功领取。领取响应丢失、工具取消/部分失败、完成确认丢失都不自动重试业务；unknown不是安全重试信号。异步取消传播，服务端可能仍为claimed；工具失败尽力确认failed，确认不明仍可能claimed。既有单宿主协议不保证跨系统恰好一次或多机恢复。

同一个Action关联请求与执行的不同Trace/Span。审核页的“按Action查询事件”使用Trace凭证重新认证，能看到策略规则/版本、请求快照与执行结果，再定位节点。awaiting_approval明确显示“待审批快照”；即使之后已批准/完成，历史快照也不改写。当前审批状态看审批收件箱。请求Span不执行工具且不进入调用耗时排行，Agent成功返回票据也不代表工具已执行。完整参数只在审批record/本机票据中出现，遥测默认不含原始参数。

工作台case文件v2允许第三决策；check/explain/compare及事件回放的v2输出使用相应v2报告schema，纯v1输入保持v1输出。差异排序deny<require_approval<allow，拒绝改需审批是放宽，允许改需审批是收紧；这是有限样本评估，不自动部署策略或执行原工具。治理协议/API兼容限制见[045契约](../specs/045-policy-approval/contracts/governance-v2.md)。

可复现流程见[原生/真实LangGraph示例](../examples/policy-approval/README.md)。已有本机平台的核心模式无需模型/框架依赖，LangGraph和异步客户端按extra安装；本轮实际安装验收使用缓存官方wheel与新本地wheel，不能代表在线安装或首次人工五分钟接入已达标。生产认证/租户/多机协调仍未交付。
