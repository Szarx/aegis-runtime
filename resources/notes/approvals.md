# 审批准备的参考与边界

查阅：2026-10-18。原始来源：[OWASP Transaction Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html)。只保存原创整理，不保存文章镜像。

该资料强调让用户识别关键交易数据、在服务端控制允许的状态转换、保护授权绑定和限制有效期。Aegis 的工程取舍是先做不可覆盖的动作绑定、独立审核凭证、数据库时钟与行锁，再设计单次执行确认。

这是对设计原则的应用，不是 OWASP 认证或完整交易授权实现。当前 summary 与 HMAC 无法替代真实副作用动作的充分可读参数预览，固定 reviewer 也不提供多用户认证。SPEC-010 明确不执行工具；后续 spec 必须补齐审阅上下文、单次领取、参数/身份/策略重新核对以及未知执行结果处理。决策见 [ADR-0004](../../docs/adr/0004-approval-preparation.md)。

SPEC-011补充独立完整参数协议与永久消费领取：宿主显式披露可读实参，服务端限制状态转换与有效期，执行前再次核对绑定/策略；结果未知不自动重试。这些为本项目工程取舍，不构成该资料认证或跨外部系统恰好一次保证。详见 [ADR-0005](../../docs/adr/0005-reviewed-execution.md)。
