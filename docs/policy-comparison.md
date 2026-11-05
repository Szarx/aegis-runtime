# 策略变更影响评估

SPEC-023扩展[策略工作台](policy-workbench.md)：比较基准和候选策略，核对基准预期，输出规则差异、用例行为变化及审查状态。它只使用Python标准库和原Policy.evaluate，不调用模型、网络或业务工具，不修改运行中的策略。

## 完整流程

安装本地Policy包，在仓库根目录运行：

```text
python -m pip install --no-build-isolation --no-deps -e ./policy-engine
python -m aegis_policy check examples/policy-comparison/before.json --cases examples/policy-comparison/cases.json
python -m aegis_policy compare examples/policy-comparison/before.json examples/policy-comparison/candidate.json --cases examples/policy-comparison/cases.json
```

check基准的8项用例通过；compare示例预期返回1和review_required，这是有效的待审查结果。它识别2次deny→allow放宽、1次allow→deny收紧、1次同效果原因变化、4次决策不变。新增但未被用例触及的allow-future仍出现在规则差异和候选覆盖中。完整文件见[示例说明](../examples/policy-comparison/README.md)。

需要保存报告时，先建立父目录，输出文件须不存在：

```text
python -c "from pathlib import Path; Path('artifacts').mkdir(exist_ok=True)"
python -m aegis_policy compare examples/policy-comparison/before.json examples/policy-comparison/candidate.json --cases examples/policy-comparison/cases.json --output artifacts/policy-comparison-first.json
```

报告同时输出stdout。输出独占创建、最多8MiB，拒绝覆盖；写入或关闭失败会移除本次不完整文件。强制终止可能残留文件，应重新生成到新路径。输入继承022的严格UTF-8 JSON、每文件1MiB、最多128规则/128用例等边界。

## 报告内容

格式aegis.policy-comparison.v1，包含两侧revision/规范指纹/规则数/有限覆盖、configuration_changed、revision_changed、rule_changes、cases和汇总。规则按ID排序，用例保留套件输入顺序。

| 字段 | 含义 |
| --- | --- |
| rule_changes.added/removed | 新增/删除的规则ID |
| rule_changes.modified | 同ID的effect或匹配成员改变 |
| rule_changes.modified_details | 改动涉及effect、subjects、tools、permissions中的哪些字段，不复制完整成员列表 |
| rule_changes.unchanged | ID、effect、规范成员均一致 |
| cases[].before/after | 两侧实际决策及匹配/选中规则 |
| baseline_mismatches | 基准实际结果与套件expected不符的用例数 |
| counts | widened/narrowed/decision_changed/unchanged数量 |

分类只比较effect、reason、rule_id。deny→allow是widened，allow→deny是narrowed；effect相同但reason或rule_id变化为decision_changed；三者都相同为unchanged。仅revision变化会记录revision_changed，不把全部用例虚报为行为变化。

规则和成员次序、JSON空白不影响规范指纹。相同revision下改成员或effect仍被识别；只改revision也会产生新指纹并要求审查。未触及的规则变化同样不能自动放行。

## CI退出码与人工审查

| 退出码 | 状态 | 使用方式 |
| --- | --- | --- |
| 0 | unchanged | 两侧规范指纹一致，而且基准预期全部匹配；只表示本次配置/基准检查未要求审查 |
| 1 | review_required | 有配置/版本差异或基准预期不符，报告有效，交由维护者审查 |
| 2 | error | 文件/格式/输出不可用，stderr固定错误，不当作有效差异报告 |

比较必须提供cases。套件expected描述**基准**，不是批准候选的声明；基准预期不符时，即使两侧策略相同，也返回1。仅修改expected不能让有配置变化的候选返回0。CI可运行compare并把1作为人工审查门槛，将报告作为本机或CI产物查看；工具没有“批准后启用”开关，也不替你更新基准或部署策略。

维护者应核对完整策略文件、差异和覆盖不足，再通过正常代码审查决定是否接受新基准。实际应用仍由可信宿主显式构造Runtime(policy, subject)，已有审批绑定与单次领取语义保持。更新策略后要重新准备与之绑定的审批，不能把比较指纹当作旧审批仍有效的依据。

## 覆盖与信任边界

这是有限用例的影响评估，不是全空间等价证明、生产授权审计或自动安全批准。unchanged分类只表示该用例三个决策字段没变；未选中的规则不能据此删除。结构差异提示仍需检查未被用例覆盖的行为。

规范指纹可用于配置比较，没有来源认证、签名或审批效力。报告输出配置中的规则/用例标识和决策，不包含源路径、完整策略成员、工具参数或环境凭证；这些标识也可能是私有配置，分享时仍需遵循项目访问规则。

实际Runtime对照、安装与回归证据见[SPEC-023验收](../specs/023-policy-comparison/tasks.md)。
