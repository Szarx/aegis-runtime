# SPEC-021 任务

状态：已验证，2026-10-23。

- [x] 定义完整场景与有界/隐私/并发/文件完整性边界。
- [x] 导出CLI、协议校验、清单/CSV及离线verify。
- [x] 故障/完整性测试和真实HTTP/PG多页导出。
- [x] 文档示例、回归、证据及临时环境清理。

## 功能与入口

标准库CLI贯通现有API、分页读取、筛选、白名单验证、独占目录、JSONL/CSV/manifest输出、分类汇总与离线核验。操作见[使用指南](../../docs/security-export.md)。服务API、四迁移、SDK、Runtime和Dashboard均未修改，020快照继续为当前契约；不创建GitHub远端或使用模型凭证。

## 验收说明

新契约测试12个、新真实PG测试1个，不把子场景或CLI进程重复计数。原目录272方法加13共285。全部重跑通过：234个Python（含41真实PG）和51个前端，无失败/错误/跳过；见[validation.json](validation.json)。

AC2101：全部精确筛选/时间上界与上限；变化total、重复/乱序/短页、错offset/limit/额外字段拒绝；已有目录不覆盖、写失败清理。实际HTTP302不跟随，401正文及凭证不回显，URL/凭证控制字符拒绝。首次测试错误地预期缺manifest会抛OSError，实际按契约抛ExportError；修正断言类型后通过，没有削弱失败处理。

AC2102：1790000000000000001纳秒JSONL精度、null保留、CSV公式转义、空包/计数/分类；数据改动、残包、过滤不符和重算哈希但CSV不对应JSONL均拒绝。独立`python -S`进程已在纯标准库模式成功核验合成单行包；不能替代真实服务验收。

AC2103：真实HTTP/PG集成方法通过实际CLI导出101事件（100+1两页）和subject筛选100事件，关闭服务后执行两个离线verify；原API契约与全部数据库回归在统一入口运行。

边界：跨页一致性检查不能提供数据库快照或事件完整性；清单哈希不认证来源，重写整包可通过本地校验。CSV便于查看，无损数据以JSONL为准。没有新Docker镜像/包构建或UI改动；类型/生产页面证据沿用020，不冒称本轮新增页面验收。


详细本机证据：artifacts/check/result.json与tests.log、artifacts/security-export-frontend.json、artifacts/security-export/stdlib.json及docker.json。62 pins、44来源与两平台缓存哈希未变，pip check及候选文件检查通过。专用aegis-spec021-check健康、测试schema清零后关闭容器/网络，卷保留；用户现有服务未动。无真实模型请求、GitHub远端或CI运行。
