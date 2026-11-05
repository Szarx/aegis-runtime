# SPEC-023：策略变更影响评估

2026-10-24，已验证。完整场景：提供基准/候选v1策略与基准预期套件，比较结构及用例决策，保存可审查JSON并用于CI门禁。无策略发布、热加载、网络、LLM或新授权语义。

公共aegis_policy.comparison.compare_policies(before,after,cases)和CLI `python -m aegis_policy compare BEFORE AFTER --cases CASES [--output REPORT]`。沿用022文件上限/严格套件、规范指纹和独占报告；旧check/explain及evaluate保持。套件expected用于校验基准，不当作候选的新批准。

规则按ID比较规范成员集合，输出新增/删除/修改/不变ID及modified_details字段名；同ID的effect或成员改变为modified，规则/成员次序不算修改。包含revision与指纹变化标志，两个策略版本字符串相同也必须比较实际配置。

逐用例保留before/after决策、matched_rules、基准预期匹配状态。分类widened（deny→allow）、narrowed（allow→deny）、decision_changed（effect相同但reason或rule_id不同）、unchanged；revision变化单列，不把仅版本变化算决策变化。统计分类及基准不符，保留两侧有限用例覆盖。

报告aegis.policy-comparison.v1，status只有unchanged或review_required；只有规范指纹完全相同且基准预期全部匹配才unchanged/退出0，其余有效报告review_required/退出1，包括未被用例触及的规则变化及仅revision变化。输入/输出失败退出2且固定错误。报告不声称全空间等价、安全批准或生产完整性；枚举用例无法穷尽组合，新配置不可自动启用。

报告输出配置规则/用例标识及决策，不回显源路径、完整策略、工具参数或读取环境凭证。继承1MiB输入、128规则/128用例、8MiB报告文件上限与写失败清理；策略解释本身无业务副作用。

AC2301：结构规范化、内容/版本变化与同revision修改检测，严格输入/输出和基准预期门禁。
AC2302：四种决策分类、有限覆盖、缺配置、确定顺序、不修改输入及旧check/explain兼容。
AC2303：完整示例/CI退出码、真实CLI和同步/异步Runtime前后执行次数对照、独立包安装、回归文档与机器证据。
