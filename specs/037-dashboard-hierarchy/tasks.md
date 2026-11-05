# SPEC-037 任务

状态：已验证，2026-10-26。

- [x] 冻结首屏/披露/精度与条件保留边界。
- [x] 共用查询面板、Trace/用量层级和回归。
- [x] 桌面几何、窄屏/键盘/草稿实际验收。
- [x] 统一质量、文档/机器证据。

新增4前端方法，72方法/类型/构建/预算通过；339 Python完整回归继承035，目录411。本轮无服务/协议/依赖变化。

生产preview实际1280×720：模型Trace执行链标题top410.27px，首节点top559.84/bottom605.84，首屏可见。覆盖说明Enter可展开，节点只看2模型时总输入14/输出6不变。桌面查询初始open；390px事件查询初始closed，实际页面宽375。Enter开关、输入write_record草稿、收起再展开仍保留；提交前summary未应用，提交后已应用1项、结果32→30。清空回32和未应用；手机Trace查询也初始closed，视口恢复1280后保持closed，不强制覆盖用户状态。

真实截图artifacts/ui037/trace-first-screen.png、mobile-events-first-screen.png、mobile-applied-query.png、mobile-traces-first-screen.png。质量和摘要见artifacts/ui037/check及[validation.json](validation.json)。完整无障碍认证、更多浏览器与大规模性能不在本轮范围。
