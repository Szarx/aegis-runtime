# SPEC-017：接入前的元数据检查

日期：2026-10-23。新增仓库命令scripts/doctor.py，只使用标准库，检查当前解释器Python>=3.11、选定profile的发行包版本与仓库锁/本地分发版本是否一致。profile为native、langgraph、reviewed-async-graph；明确只覆盖列出的包，不冒充完整依赖求解/import smoke/真实接入验证。

默认不读环境凭证、不导入应用/框架、不执行Agent/SQL/网络/子进程、不安装或修改任何包、不创建文件。可选--check-reviewed-env只检查宿主producer/executor令牌为非空可打印ASCII且不同，以及十六进制绑定key>=32字节；仅用于reviewed-async-graph。不认证凭证、不验证reviewer/server配置，不输出值/长度/哈希。

文本/JSON只输出固定检查标识、预期公开版本与matched/missing/mismatch/unavailable/not_run状态，不输出实际不匹配元数据或异常正文，防止异常/恶意包元数据泄露本机信息。读取仓库固定lock和pyproject作为基线；基线损坏/缺失失败关闭。stdout默认只读；显式--output通过独占创建保存同一JSON，已有目标不覆盖，写失败退出非0。

退出0表示选定检查通过；1检查未通过或报告保存失败；CLI参数错误2。Python不支持时不继续检查。包元数据存在不证明模块可导入、二进制可用、Collector/Docker在线或业务安全；报告单独列出not_checked边界。修复建议是固定文档引用，不自动运行命令。

AC1701：三profile与锁/本地包对应，missing/mismatch/unavailable/旧Python/损坏基线可辨识且不误报成功。
AC1702：可选凭证形状/冲突检查，敏感值与异常正文不进入终端/JSON；无应用导入/网络/包修改。
AC1703：真实当前环境、标准库模式和既有独立核心环境CLI、独占报告/退出码、受影响回归和文档/机器证据。无新依赖/SQL/API/UI变更。
