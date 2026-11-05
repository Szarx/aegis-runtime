# SPEC-008 方案

- 标准库脚本创建唯一 run 目录并调用当前 Python 的 venv，直接使用新环境 Python，不激活 shell、不更改旧环境。
- 安装使用 pip 的 --isolated、显式官方 index 或本地 --no-index，以及现有 constraints；不更改依赖版本或重新抓取资料。
- 复用原生及真实 LangGraph 离线示例，保留其业务对照；在父进程中校验 JSONL 数量、身份关系和诊断后记录首次有效 Trace。既有 SDK/Collector/UI 不修改。
- 所有阶段带超时，失败立即返回并持久化 metadata-only receipt；子进程输出仅供内存解析已知 JSON，不复制异常消息。固定故障原因与排查文档相连。
- 有意义的测试覆盖不正确 Trace、缺包/超时停止和凭证输出不泄漏；实际全新环境分别验证两种 profile。Docker 不可用作为平台阶段的外部状态记录，不启动桌面应用或伪造端到端完成。

- Docker 恢复后按新增 AC806 使用独立 Compose 项目和新库，连续测量构建/健康、原 venv 补装 OTLP、首次查询与浏览器确认；保存单独平台摘要与截图。仅临时测量辅助脚本写入 tmp，不为验收增加新产品 API。
