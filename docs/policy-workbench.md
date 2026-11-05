# 策略开发与验收工作台

SPEC-022为现有aegis.policy.v1提供文件检查、单次决策解释、批量用例验收与JSON报告。工作台只依赖Python标准库，不使用LLM、网络、数据库、工具参数或用户Python代码。策略格式和Runtime的allow/deny行为不变。

需要比较基准与候选时，使用[SPEC-023策略变更评估](policy-comparison.md)，查看规则结构及用例放宽/收紧，按CI退出码安排审查。原check/explain保持。

## 安装与使用

仓库根目录，激活Python 3.11+环境后安装本地Policy包：

```text
python -m pip install --no-build-isolation --no-deps -e ./policy-engine
python -m aegis_policy check examples/policy-workbench/policy.json
python -m aegis_policy check examples/policy-workbench/policy.json --cases examples/policy-workbench/cases.json
python -m aegis_policy explain examples/policy-workbench/policy.json --subject blocked --tool lookup --permission orders.read
```

第一条check仅验证策略文件，cases_total=0，不代表通过了业务验收。第二条运行7个声明式用例。第三条显示同时匹配deny-blocked和allow-read，实际选择deny-blocked；工作台的explain成功退出码表示解释计算成功，即使解释结果为deny也返回0。省略subject或permission表示缺失，不推断默认身份或权限。

需要保存报告时，先创建父目录，再选择不存在的输出文件：

```text
python -c "from pathlib import Path; Path('artifacts').mkdir(exist_ok=True)"
python -m aegis_policy check examples/policy-workbench/policy.json --cases examples/policy-workbench/cases.json --output artifacts/policy-check-first.json
```

报告仍同时输出stdout。check全部匹配或仅策略校验成功返回0；用例结果与预期不符返回1并保留actual/expected报告，便于CI失败排查；文件/格式/输出错误返回2，stderr为固定错误、不回显内容或路径。输出使用独占创建，不覆盖任何已有文件；写入或关闭失败会删除本次未完成文件。进程强制终止仍可能残留不完整文件，重新生成时使用新路径。

## 用例格式

套件的schema_version为aegis.policy-cases.v1，cases必须有1..128个唯一id用例。所有字段必填，不接受额外字段：

```json
{
  "schema_version": "aegis.policy-cases.v1",
  "cases": [
    {
      "id": "read-allowed",
      "subject": "reader",
      "tool": "lookup",
      "permission": "orders.read",
      "expected": {
        "effect": "allow",
        "reason": "explicit_allow",
        "rule_id": "allow-read"
      }
    }
  ]
}
```

subject和permission可为null，tool必须是标识。expected包含effect、reason、rule_id；显式allow/deny需要规则ID，其他原因rule_id为null。只验收已有纯策略结果：explicit_allow、explicit_deny、no_match、identity_missing、permission_missing，不模拟缺策略或求值故障。无通配符、条件表达式、require_approval或任意Python导入。

策略与用例文件均为UTF-8 JSON、最多1MiB，拒绝重复键、未知字段/版本、无效类型/标识及超限。策略仍最多128条规则、每个匹配列表1..128项，详见[Policy格式](../policy-engine/README.md)。库调用可使用`aegis_policy.workbench.load_policy/load_cases/check_cases/explain/fingerprint`，每次check复制套件快照，不修改调用方输入或Policy。

## 理解决策与报告

解释复用原Policy.evaluate：精确匹配subject/tool/permission，deny优先，同效果按规则ID排序。matched_rules列出所有实际匹配规则及selected，缺身份/权限时不匹配任何规则。报告格式aegis.policy-report.v1，包含策略版本/指纹、case实际与预期、通过数及有限覆盖。

coverage里的matched_rule_ids、selected_rule_ids和not_selected_by_cases只针对本次用例。示例的allow-admin未被选中，说明应考虑补充用例，不能据此断言生产永不触达或规则可删除。工作台不检查工具副作用、宿主身份绑定或分布式执行正确性；[示例Agent](../examples/policy-workbench/README.md)再把同一批用例交给真实同步/异步Runtime验证。

policy_fingerprint对包含revision的规范JSON做SHA-256：规则按ID、匹配成员按文本排序，忽略空白和输入顺序，修订或成员变化会改变指纹。它仅便于本地报告比较，没有签名、来源认证或审批授权效果，**不能替代既有ReviewedTool的策略绑定摘要/HMAC**。Runtime仍由宿主显式绑定Policy和subject，不自动加载工作台报告或远程更新策略。

报告只含配置标识、决策、匹配规则与指纹，不含完整策略列表、源路径或工具参数，也不读取模型/审批凭证。规则和用例标识本身可能是私有配置，分享报告需按项目访问规则处理。报告写入上限8MiB；完整测试、安装和兼容边界见[SPEC-022验收](../specs/022-policy-workbench/tasks.md)。
