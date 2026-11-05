# 策略验收后接入Runtime

本例先以声明式用例验收Policy，再构造真实Runtime运行同一组请求。工具只返回合成字符串并增加内存计数，无LLM、网络或业务系统。7个用例中1次允许、6次拒绝；每次运行新增7个Agent和7个治理Span。

仓库根目录安装本地包后：

```text
python -m pip install -r requirements-dev.lock
python -m pip install --no-build-isolation --no-deps -e ./sdk/python -e ./policy-engine -e ./runtime
python -m aegis_policy check examples/policy-workbench/policy.json --cases examples/policy-workbench/cases.json
python examples/policy-workbench/agent.py --output artifacts/policy-workbench/sync.jsonl
python examples/policy-workbench/agent.py --async --output artifacts/policy-workbench/async.jsonl
```

check通过7项，规则覆盖显示allow-admin未被用例选中；这是覆盖不足的提示，不是不可达证明。两个Agent命令各输出cases=7、business_calls=1、exported_spans=14，拒绝路径未进入业务函数。SDK的JSONL文件按原有行为追加，需要独立运行证据时选择新文件。模型与审批凭证均无需配置。

修改cases.json使预期与实际不符时，check返回1并显示差异；Agent在初始化SDK/Runtime之前停止，不把验收失败当作允许。不要用错误预期修改来绕过策略。CLI检查本身不执行工具；示例Agent工具只用于计数证明。

编写自己的用例、explain、报告/退出码、指纹与覆盖边界见[工作台指南](../../docs/policy-workbench.md)。实际Runtime接入仍由应用可信宿主绑定身份，报告不能认证身份或替代审批绑定。
