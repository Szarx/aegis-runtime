# 接入前检查环境

在仓库根目录用准备运行Agent的同一个解释器执行：

```text
python scripts/doctor.py
python scripts/doctor.py --profile langgraph --json
python scripts/doctor.py --profile reviewed-async-graph --json
```

命令只依赖Python标准库，要求仓库lock与三个本地包pyproject仍在原位置。支持Python>=3.11，本轮实际验证3.12.14；旧版本报告unsupported。它不导入Aegis/框架、不运行Agent、不调用模型、不访问网络或SQL，也不安装/更新包。默认不检查凭证、不读.env，不要求LLM密钥。

| profile | 检查集合 |
| --- | --- |
| native | SDK、OTel API/SDK/语义版本、typing-extensions，共5包 |
| langgraph | native，加LangGraph/core/checkpoint/prebuilt/sdk及OpenAI/httpx2，共12包 |
| reviewed-async-graph | native，加图5包、Policy/Runtime、HTTPX和SQLite/aiosqlite/sqlite-vec，共16包 |

报告只比较这些发行包的元数据与本仓库已验证版本。mismatch表示偏离当前验收基线，不代表其他版本必然不可用；不输出实际不匹配版本，防止意外泄露任意元数据。没有要求安装Collector/数据库/模型服务，也没有覆盖所有传递依赖、额外extras或动态导入。native通过后，业务所需的可选profile仍可能失败。

## 读取结果

| 状态 | 含义与处理 |
| --- | --- |
| matched | 此项符合选定基线；包存在不证明能够import或执行 |
| missing | 当前解释器找不到发行包元数据；检查是否使用了正确venv，并按安装文档补装 |
| mismatch | 与仓库基线不同；优先在独立环境按锁定版本复现，避免直接修改生产环境 |
| unavailable | 无法读取基线或包元数据；检查仓库完整性/安装，原异常路径不会回显 |
| unsupported | Python低于3.11；不继续检查包 |
| invalid | 显式配置形状或凭证冲突检查未通过 |
| not_run | 此项未检查，不能按成功解释 |

退出码0仅表示所选检查通过，1表示未通过或报告保存失败，参数错误为2。检查不会自动修复环境或运行安装命令。

显式保存报告时使用新文件，父目录需已存在：

```text
python scripts/doctor.py --json --output artifacts/my-preflight.json
```

文件独占创建，已有文件/同名符号链接不覆盖；保存失败返回1并输出固定状态，终端不回显目标路径或异常正文。默认只向stdout输出，不主动保存报告。报告包含公开包名/预期版本、检查状态和未检查范围；没有凭证值、环境变量dump、本机绝对路径或任意异常文本。

## 可选审批宿主配置检查

```text
python scripts/doctor.py --profile reviewed-async-graph --check-reviewed-env --json
```

仅检查当前进程的AEGIS_APPROVAL_REQUEST_TOKEN / AEGIS_APPROVAL_EXECUTION_TOKEN是非空可打印ASCII且不同，以及AEGIS_APPROVAL_BINDING_KEY可解析为至少32字节的十六进制值。不输出值、长度或指纹；该检查不会认证凭证，也不验证Collector侧reviewer、Trace token、角色隔离、endpoint或策略。其他审批配置仍按 [异步图接入](async-graph.md) 完整验证。不要把凭证传给命令参数或发到聊天中。

检查通过后继续运行 [独立Agent配方](../examples/existing_agent/README.md)，核对实际业务结果、调用次数和Trace。需要完整依赖一致性时另运行 `python -m pip check`，需要平台时按 [部署](../deploy/docker/README.md) 验证；这些步骤不包含在doctor结果中。人工5分钟接入、真实Provider或生产安全认证仍未由此验收。

测试与边界见 [SPEC-017](../specs/017-preflight/tasks.md)。
