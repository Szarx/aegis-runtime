# 治理事件离线排查包

有效导出包可进一步用于[SPEC-024候选策略离线回放](event-policy-replay.md)，重算已接收事件的策略决策并保留关联；不会执行原工具。

SPEC-021把[安全事件中心](security-events.md)的查询结果导出为便于排查的本地包。工具只需要Python标准库，不安装LLM、SDK或数据库驱动；服务仍使用原有[SPEC-020协议](../specs/020-security-events/contracts/openapi.json)。可从已有Agent的治理事件开始，也可按[安全事件示例](../examples/security-events/README.md)生成25次尝试。

## 导出与核验

在仓库根目录，确保Collector已运行，并将Trace token设置到本机AEGIS_API_TOKEN环境变量（未配置认证时留空）。地址替换为Collector的实际端口；HTTPS允许远程服务，明文HTTP只允许localhost、127.0.0.1或::1。不要在URL中放凭证，CLI拒绝带账号、查询或片段的地址，也不会跟随重定向。失败不打印响应正文、源URL或凭证。

```text
python -c "from pathlib import Path; Path('artifacts').mkdir(exist_ok=True)"
python scripts/security_export.py export --base-url http://127.0.0.1:8000 --service-name security-events-example --output artifacts/security-export-first
python scripts/security_export.py verify artifacts/security-export-first
```

输出目录必须不存在、父目录必须已存在；旧目录不会覆盖。成功退出码0，stdout给出count和effect/outcome/reason计数；失败退出码1并在stderr输出固定错误说明。export不会运行或审批工具。verify完全离线、不读取token；可在Collector停止后执行。帮助见`python scripts/security_export.py export --help`。

包内三个固定文件：

| 文件 | 用途 |
| --- | --- |
| events.jsonl | 完整白名单事件，每行JSON，纳秒整数保持精度，null保持未知 |
| events.csv | 相同字段顺序的可读表格，null显示空，公式起始文本加单引号转义 |
| manifest.json | 格式版本、查询条件、开始/结束时间、数量/分类汇总、文件长度/SHA-256与局限声明 |

清单不保存源URL或token。事件中仍含应用上报身份、工具、服务及关联ID，分享包时需按自己的数据访问规则处理。CSV只便于查看：Excel等软件可能把ID/纳秒解析成浮点数或删掉前导零，也无法区分null和空字符串；无损处理使用JSONL，并使用支持大整数的解析器。表格软件的再次另存可能改变CSV，导致核验失败。

## 筛选和上限

支持与020相同的精确条件：--subject、--tool、--permission、--service-name、--action-id、--trace-id、--effect、--outcome、--started-after-ns、--started-before-ns。空白不是通配符；不支持查询null。时间是含两端的正int64纳秒。示例：

```text
python scripts/security_export.py export --base-url http://127.0.0.1:8000 --effect deny --tool write_record --max-events 500 --output artifacts/security-denied-first
```

默认最多1000行，可设1..10000。超过上限会失败而非截断，应缩小筛选范围或调整上限。默认开始时间上界取导出开始时本机时间；显式上界晚于本机开始时间时也会截到该时间。时钟偏差或迟到上报可能影响覆盖，应核对清单实际查询条件。

每页100，HTTP I/O超时10秒、响应最多4MiB，不重试。total变化、重复/乱序、分页长度/offset不符或行不满足筛选都会失败；网络阶段不创建输出目录。通过检查也不代表跨页数据库快照：同数量替换、迟到写入、并发修改等可能无法检测。清单只描述本次收到的记录，不保证已接入或未接入调用全部到齐。

## 完整性与失败恢复

文件在新目录中独占写入，manifest最后完成。捕获到写入失败会清理本次文件；进程被强制终止可能留下残包，verify会拒绝。不要手动补清单把残包当成功；重新导出到另一个新目录。

verify只读取固定文件，拒绝文件/目录符号链接、过大清单/数据文件、文件哈希或长度变化、事件形状/排序/重复/筛选错误、CSV不对应JSONL、数量/汇总不符。核验不会导入Collector、产生业务副作用或修复文件。哈希与清单同处一包，能一起被修改，**不能证明来源、认证身份或防篡改审计**；没有数字签名、审计保留或数据库快照承诺。

测试、真实HTTP/PostgreSQL导出和边界见[SPEC-021验收](../specs/021-security-export/tasks.md)。
