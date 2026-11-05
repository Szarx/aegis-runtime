# 前端工作台设计参考

查阅2026-10-26；仅记录设计原则，不保存文章正文或复制第三方代码。现有44条协议/依赖来源索引保持；这些为额外视觉研究来源。

- [Supabase Tables](https://supabase.com/design-system/docs/ui-patterns/tables)：结构化数据优先、可扫描列、表格语义与筛选/分页放在数据附近。用于029的紧凑表格和030交互。
- [Grafana Table](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/visualizations/table/)：同一表格中清晰区分数据类型和状态，支持日志/Trace阅读。用于数值对齐和语义状态，不引入其实现。
- [Langfuse](https://langfuse.com/docs)：观测产品中的Trace/详情工作流作为信息架构参照；未复制其品牌、代码或假设当前版本兼容性。

Aegis取舍：深色中性基底、单一强调色、字号层级克制、细边框、明确状态文本、操作接近数据。移除营销区、无意义编号、空指标和字形图标。本地字体、自绘SVG，无远程资源。移动端保留全部导航，表格横滚局限容器。

034补充查阅官方[文字对比度解释](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)与[目标尺寸解释](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)（2026-10-26）。只对明确覆盖的文字tokens测4.5:1、小型控件采用26px命中目标；保留状态文本，不宣称整站认证或以局部测试替代完整辅助技术验收。

036查阅[OWASP CSV Injection](https://community.owasp.org/attacks/CSV_Injection)（2026-10-26）：公式前缀、控制字符、分隔符/引号都影响CSV解释，重新保存和不同表格软件可能改变转义效果。Aegis对本页CSV逐格双引号转义并为受测危险前缀加单引号，覆盖全角符号；这会改变CSV字段，不是所有软件/二次保存的通用安全保证。JSONL保留原始值与整数精度，CSV供受控文本导入阅读。
