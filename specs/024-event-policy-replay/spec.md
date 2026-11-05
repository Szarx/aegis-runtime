# SPEC-024：历史治理事件的候选策略回放

2026-10-25，已验证。完整工作流：真实Agent治理遥测→Collector→021导出包→离线核验→候选Policy纯求值→关联事件和差异报告。这里回放只表示重新计算策略决策，不执行原工具、模型或审批，不自动启用策略。

仓库CLI `python scripts/replay_security.py BUNDLE --policy CANDIDATE --output REPORT [--max-events N]`，只依赖标准库和本地Policy包；无端点、网络或凭证读取。默认上限1000、范围1..10000，超过上限不截断。输出独占JSON文件、最多8MiB；失败清理和不覆盖语义沿用022，stdout只输出摘要。成功无差异退出0，需审查退出1，输入/输出失败退出2。

021新增read_bundle函数，返回同一次有界读取中已验证的manifest和事件快照；verify_bundle原接口/CLI不变。校验固定文件、字节哈希、JSONL/CSV/汇总/筛选/顺序与重复后才交给回放，不在校验后再打开事件文件。

报告aegis.event-policy-replay.v1，保留每事件白名单、candidate_decision、category及revision匹配。按(trace_id,span_id)保留独立尝试，不按Action合并。只重算subject/tool/permission的Policy.evaluate：widened为记录deny→候选allow，narrowed为记录allow→候选deny，decision_changed为effect相同而reason/rule_id变化，unchanged为三字段相同；revision不同单独统计。

报告包含候选revision/规范指纹、来源manifest规范JSON摘要及已验证文件哈希、原outcome汇总、分类与revision不符数量。原业务完成/error/cancelled保持记录，不预测候选执行结果。空事件包、任何决策变化或revision不同均review_required/1；仅非空且全部决策/版本匹配才unchanged_for_received_events/0。

记录是应用上报元数据，没有可信基准策略全文，不能验证当时身份/策略是否真实，不能从相同revision推断配置相同。来源哈希不是签名，有限事件不是跨页快照或完整授权日志，报告不提供部署/审批授权。只披露原白名单/候选决策，不含源路径、工具参数或模型/审批凭证。

AC2401：校验快照读取兼容、损坏/超限/重复/协议失败关闭、独占输出与错误隐私。
AC2402：分类/版本/空包、结果保留、Action多尝试、纳秒精度及不执行工具。
AC2403：真实SDK→HTTP/PG→导出→停服离线回放，允许/拒绝候选对照；独立依赖环境、全回归与文档证据。
