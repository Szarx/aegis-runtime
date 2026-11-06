# SPEC-048 外部 Agent 首次接入验收

选用 langchain-ai/react-agent 官方模板固定提交，保存 MIT 许可证和文件哈希。自动化验收使用合成模型与搜索服务。

- AC4801 校验上游源码后，在独立产物目录复制运行项目。外部服务边界替换限定 tools.py 和 utils.py，graph/state/context/prompts 保持原字节。分别记录边界适配与 Aegis 宿主代码。
- AC4802 实际执行上游异步 ReAct 图。baseline 与 observe/allow 的消息内容、工具参数、业务调用次数一致。deny 确认业务零执行。审批在 ToolNode 内 interrupt，未批准零执行，独立人工决定后宿主显式恢复，完成确认后同一票据再次恢复被阻止。多工具并发恢复和持久化重启另行验收。
- AC4803 提供可运行 CLI 和接入指南。真实 HTTP/PostgreSQL 校验 Trace、LLM、治理信号、精确审批状态。新环境安装后可复现。
- AC4804 自动计时包含复制、适配、导入、运行和导出等待，安装单独记录。人工阅读、首次手工改造和真实 Provider 耗时由用户实测。报告描述合成外部服务与本机内存 checkpoint 的范围。
