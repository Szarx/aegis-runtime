# SPEC-016 任务

状态：已验证，2026-10-23。

- [x] T1601：冻结配方、行为比较和测量口径。
- [x] T1602：独立原 Agent / 适配层 / 对照宿主。
- [x] T1603：CLI、严格receipt验证与失败测试。
- [x] T1604：实际8组运行、受影响回归、文档与证据。

## 验收

实际SDK59、接入契约12（旧8+新增4）、Runtime基础7，共78个不同测试方法全部通过，无跳过。旧目录234中74重跑、160沿用，当前238（含历史35前端方法）。8组子场景/子进程不累加为方法。没有核心库、服务端、SQL或UI修改，不重复声称本轮运行PG/页面/包安装；对应证据沿用015及其历史来源。

| AC | 实际结果 |
| --- | --- |
| 1601 | 真实StateGraph/ToolNode和官方OpenAI SDK合成HTTP，CLI同步/异步各baseline/observe/allow/deny共8次；原application无Aegis导入，客户端/工具注入，独立适配层；观测/allow完整业务消息及次数与baseline一致 |
| 1601 deny | 两次合成模型调用，真实业务工具0次；原框架处理拒绝继续收尾，受控Span为denied/ERROR，结果明确不等价；不因Agent正常返回而判定工具已执行 |
| 1602 | baseline无SDK初始化/Span，其他各1 Agent / 2 CLIENT LLM / 1 Tool，父子关系与7/3合成用量核对，开始/结束时间换算调用耗时；所有诊断为预期，flush/shutdown成功 |
| 1602 失败 | 真实成功JSONL经删除Span、破坏parent/ID/时间/用量、注入合成私有值，或执行次数类型/丢Span诊断/flush损坏后均拒绝；异常receipt固定类别，不记录原异常正文/环境/用户绝对路径 |
| 1603 | 对照宿主机械新增1行/删除1行导入，原应用共享未修改；明确不含适配层实现、SDK生命周期、安装和真实项目改造。独立目录不覆盖既有结果；接入选择表、边界与步骤文档已交付 |

命令（根目录，锁定依赖及本地包已安装）：

```text
python -m unittest discover -s tests/contract -v
python -m unittest discover -s sdk/python/tests -v
python -m unittest discover -s runtime/tests -p test_runtime.py -v
python examples/existing_agent/run.py --mode observe
python examples/existing_agent/run.py --mode deny --async
```

CLI每次独立运行baseline和目标；receipt的counts仅是目标次数。execution_and_validation_ms从进程内对照开始到flush/校验，排除解释器启动和模块导入；本轮未测人工、安装、在线下载或新平台页面。模型耗时为客户端+合成transport调用边界，非真实模型推理/首Token性能。

## 证据与边界

[validation.json](validation.json)含8组完整元数据receipt、计数与继承范围。忽略目录artifacts/existing-agent保存tests.log/tests.json/matrix.json；测试临时目录/原JSONL自动清理，单独CLI冒烟目录保留合成Trace。实际Windows Python3.12.14；原生asyncio/回环测试在允许本机执行的环境运行。没有Docker变更、真实模型请求、用户业务数据或新增第三方版本。62-pin两平台官方缓存哈希、41来源、当前OpenAPI和文档链接另行校验。

本例是依赖注入点已经存在的合成应用，不能当作任意现有Agent一行接入或人工5分钟体验证明。既有编译图只能显式包装入口，不能凭此自动控制未包装工具；真实第三方Agent迁移、Provider、审批流程交互、租户/生产调度仍按各自spec验收。
