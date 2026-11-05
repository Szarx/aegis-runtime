# 历史治理事件的候选策略回放

SPEC-024把[治理事件导出包](security-export.md)与[Policy工作台](policy-workbench.md)连接起来。它核验已导出的事件，用候选策略重新计算subject/tool/permission决策，保留Trace/Span/Action关联和原业务结果，帮助评估策略修改对已接收事件的影响。

“回放”在这里仅表示纯策略求值，不重新执行原工具、调用模型、提交审批、连接Collector或自动安装候选策略。脚本只依赖Python标准库和无第三方依赖的本地Policy包；生成示例事件时才需要SDK/Runtime及平台。

## 从真实事件开始

仓库根目录，安装本地Policy包并准备目录：

```text
python -m pip install --no-build-isolation --no-deps -e ./policy-engine
python -c "from pathlib import Path; Path('artifacts').mkdir(exist_ok=True)"
```

先按[安全事件Agent](../examples/security-events/README.md)启动平台并上报，或使用已有接入Agent的事件。配置了Collector认证时，只在导出步骤通过本机AEGIS_API_TOKEN提供Trace token。替换实际Collector地址后导出：

```text
python scripts/security_export.py export --base-url http://127.0.0.1:8000 --service-name security-events-example --output artifacts/events-first
python scripts/security_export.py verify artifacts/events-first
python scripts/replay_security.py artifacts/events-first --policy examples/event-policy-replay/candidate.json --output artifacts/replay-first.json
```

导出步骤需要平台在线；verify和replay完全离线，可在Collector停止后执行，也不读取环境凭证。回放会再次核验包，因此前一步verify是方便检查，不是必需前置。示例预期review_required、退出1，这是有效的待审查报告。stdout是分类/原outcome摘要，完整关联结果保存在新JSON文件。

## 核验、上限与输出

必须提供021格式的整个目录，包含manifest.json、events.jsonl、events.csv。固定文件哈希/长度、JSONL形状/筛选/顺序/重复、CSV及汇总全部核验后，才把同一次读取的事件快照交给Policy；不会校验后再重新打开JSONL。旧verify命令保持兼容。

默认最多回放1000条，--max-events可设1..10000；匹配包超过上限直接失败，不截断。应在导出时缩小筛选范围，或明确调整有界上限。每个事件文件沿用021的64MiB读取上限，报告文件最多8MiB；即使事件数符合上限，过大的报告也会失败。

输出父目录需存在，目标文件必须不存在，独占创建并保持旧文件。输入/输出失败返回2并输出固定错误，不打印原内容、源路径或凭证；写入或关闭失败清理本次残文件。进程被强制终止仍可能留下不完整文件，应重新生成到新路径。源包和候选策略都只读。

## 理解报告

格式aegis.event-policy-replay.v1，包含候选revision/规范指纹、来源文件哈希与manifest规范JSON摘要、原outcome汇总和逐事件结果。manifest_canonical_sha256是解析后规范JSON的摘要，不等于原manifest文件的字节哈希，也不认证来源。

每个结果保留16字段事件白名单，增加candidate_decision、category、revision_matches。相同Action的不同Trace/Span尝试分别保留。原事件的completed/error/cancelled/denied仍表示当时的上报结果，不改成候选执行结果。

| category | 含义 |
| --- | --- |
| widened | 记录deny，候选Policy为allow |
| narrowed | 记录allow，候选Policy为deny |
| decision_changed | effect相同，reason或rule_id不同 |
| unchanged | effect、reason、rule_id均相同 |

revision差异单独统计，不把仅版本变化虚报为所有事件决策变化。缺身份/权限仍失败关闭；历史policy_unavailable或policy_error作为上报记录保留，不假装重现当时的加载或求值故障。当前候选是已验证的可用Policy。

| 退出码 | 状态 | 边界 |
| --- | --- | --- |
| 0 | unchanged_for_received_events | 非空包内所有决策及revision匹配，只描述这些事件 |
| 1 | review_required | 存在决策变化、revision差异或事件包为空，报告有效 |
| 2 | error | 包/策略/上限/输出失败，无有效新报告 |

## 信任与使用范围

遥测身份、策略版本和结果来自应用上报，来源包没有当时完整Policy或可信身份凭据。相同revision也可能对应不同配置，不能据此证明策略一致。导出可能缺失调用、存在迟到记录或跨页变化，哈希只能核对清单和文件一致性，不能防止整包重写。

退出0不保证未出现过的输入、安全批准或真实工具执行成功。widened只是候选Policy可能允许这个三元组；真实执行还受宿主身份、审批、工具实现和环境影响。候选结果不能解除已消费的审批领取或成为新授权凭据。

[SPEC-023策略比较](policy-comparison.md)使用两份完整配置和声明式基准，任何规范配置差异都要求审查；本功能只有历史事件和一份候选，不能发现未被历史事件触及的新规则。两者适合联合使用。

报告仅保留原白名单和候选决策，不增加工具实参、prompt或异常正文，但身份/服务/关联ID仍可能是私有元数据，分享时需按项目访问规则处理。真实SDK/HTTP/PG导出与停服回放证据见[SPEC-024验收](../specs/024-event-policy-replay/tasks.md)。
