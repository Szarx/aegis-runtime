# Collector连通性与指定Trace诊断

已有SDK环境先用[元数据预检](preflight.md)确认选定包版本；要确认服务是否可访问，从仓库根目录运行标准库命令：

```text
python scripts/platform_check.py --base-url http://127.0.0.1:8000
python scripts/platform_check.py --base-url http://127.0.0.1:8000 --trace-id 这里替换为实际32位小写TraceID --output artifacts/platform-report.json
```

第二行TraceID必须替换为自己的非零小写hex32。artifacts目录须已存在，报告文件须尚不存在；不传--output只打印JSON。凭证通过本机AEGIS_API_TOKEN环境变量提供，与Collector的Trace API token一致，不是审批producer/reviewer/executor凭证。未配置鉴权的本地开发服务可不设置此变量。不要在命令参数或报告中放密钥。

默认顺序检查live、ready和第一页Trace查询，空列表仍可表示查询可用。显式指定Trace后继续读取详情和该Trace的治理事件首页。通过只代表这些只读请求成功，不能证明当前Agent接入、Trace已完整导出、业务安全、页面可见或审批角色正确。报告中的span_count是已接收节点数，missing_parent_count记录缺父数量；security_page_count只覆盖最多100条的首页，security_total和security_has_more说明是否还有记录。健康检查与业务验收需分别判断。

| 失败阶段/分类 | 本机下一步 |
| --- | --- |
| live / network_unavailable 或 network_timeout | 检查服务地址/端口与进程；Compose部署先检查Docker Engine，再检查容器日志 |
| ready / unavailable | 服务可达但数据库等就绪检查失败；核对PostgreSQL容器、连接与迁移 |
| trace_query / unauthorized | 核对当前环境的Trace API token；健康检查成功不能证明查询凭证有效 |
| trace_detail / not_found | 核对TraceID及所连接环境；确认Agent flush/导出诊断，再手动重查 |
| redirect_refused | 使用Collector的最终根地址，检查反向代理；命令不跟随跳转 |
| protocol_error 或 http_error | 核对是否连接正确服务/版本；在本机查看服务日志 |
| invalid_options_or_output | 检查URL、ID、超时、token形状和新报告文件路径 |

参数--timeout-seconds默认3，范围1..30，是每次socket操作超时，不是整个命令的硬性总时限。每份响应最多1MiB；过大Trace会显示protocol_error，需在本机另行排查。HTTP仅允许localhost/127.0.0.1/::1，远端用HTTPS。固定GET路径、无重试/重定向，禁用环境代理直连；需要企业代理的环境应另行配置受支持的接入方案。

报告不记录地址、凭证、Span属性、输入输出、服务名或原始错误正文。0表示选定检查通过；1表示检查或报告保存失败；2表示参数/输出预检错误。已有报告不覆盖，写失败不能算通过。默认三次GET，指定Trace共五次，不执行Agent、模型、审批或遥测写入，也不自动修复服务。

需要新增示例数据时另行运行[合成演示](dashboard-demo.md)，然后从平台取得TraceID再检查；该演示会写入遥测，和本命令的只读语义分开。完整开发快照验证使用[统一验收](snapshot-check.md)，不以本命令代替回归测试。行为与证据见[042任务](../specs/042-platform-diagnostics/tasks.md)。
