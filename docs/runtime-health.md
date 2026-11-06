# 运行与采集健康

SDK 初始化后，显式启用独立健康通道。健康 endpoint 与 OTLP endpoint 分开指定，使用当前 Collector 的 Trace 凭证。

```python
sdk = aegis.init("my-agent", endpoint=collector_url + "/v1/traces",
                 headers={"Authorization": "Bearer " + token})
instance_id = sdk.start_health_reporting(
    collector_url + "/v1/health", token=token, interval_seconds=10)
```

业务线程只维护活动状态。单独的后台线程每 10 秒发送活动数、最多 16 个 Trace 标识和累计诊断计数。单次网络等待最多 1 秒。健康请求失败不改变业务结果，之后成功上报时显示累计失败次数。进程完全失联时，页面只能依据最后接收时间判断心跳中断。

在 Dashboard 用 Trace 凭证连接，选择「运行与采集健康」。超过 45 秒未收到新序号时显示「心跳中断」。活动数来自上次快照，可能包含崩溃前未结束的调用。活动链接可进入 Trace，尚未结束的 Span 可能还没有完成上报。

「待导出」包含队列及当前批次。「累计丢弃」表示队列满载或关闭时未接收的已结束 Span。「累计失败 Span」与「导出失败次数」来自导出器。累计值以宿主实例为单位，成功恢复后保留历史计数。采集健康不决定业务执行或审批资格。

运行合成示例

```text
python examples/runtime-health/agent.py --collector http://127.0.0.1:8000 --seconds 60
```

在示例结束前打开健康页，可以看到活动 Trace。活动数在 Span 结束时清零。SDK 关闭时后台尽力发送一次最终快照，随后停止心跳，最后收到的快照最终转为心跳中断。最终快照也受网络和进程退出影响。

## 存储与部署范围

当前 Collector 每个进程保存最多 1024 个实例，满载时淘汰最久未更新的实例。旧序号和相同序号不续期。实例使用随机 ID，宿主重启创建新实例。Collector 重启后清空健康快照，活动宿主后续上报重建记录。

该接口用于单 Collector 部署。多 worker 或多副本需要共享健康存储后再启用统一查询。健康内容是宿主上报的观测元数据。持久历史审计与业务结果核对另有各自的数据路径。
