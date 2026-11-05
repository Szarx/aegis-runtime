# Runtime 授权研究笔记

查阅：2026-10-18。主要来源：[OWASP Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)。仅整理本项目决策，不保存第三方全文。

该官方指南区分认证与授权，建议默认拒绝、在每次受保护操作检查权限、在实际入口实施检查，安全处理失败并测试授权路径。本项目据此选取最小本地实现：宿主显式提供身份，每次工具调用前精确匹配身份/工具/权限，策略故障不放行，使用执行计数检验拒绝的实际效果。

这些原则不意味着本项目已完成生产认证或完整安全审计。subject 是可信宿主绑定的应用标识，不能来自模型输入；上报身份仅用于展示。绕过包装器和同进程恶意代码不由此模块隔离；审批恢复、持久审计和远程身份属于后续独立设计。

Policy / Runtime 为新本地包，无新增第三方依赖版本。 SDK 自有 aegis.governance.v1 与本地 JSONL v4 只声明本项目契约，不声称新的标准 GenAI 兼容认证。实现与测试见 [SPEC-009](../../specs/009-runtime-policy/spec.md)。
