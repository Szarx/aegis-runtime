# SPEC-035 任务

状态：已验证，2026-10-26。

- [x] 冻结合成数据、角色/输出与失败边界。
- [x] CLI编排、文档和契约。
- [x] 真实HTTP/PG及浏览器展示。
- [x] 完整回归、产物检查与就绪证据。

完整入口重跑339 Python（59 SDK、20 Policy、119 Runtime、32 Collector、57契约、52真实PG）零失败/错误/skip，前端64方法、类型/构建/预算通过，共403。新增5 Python方法含检查器超时证据保留。初次回归遇到极快合成模型0ns的旧断言，增加显式50ms transport延迟稳定测量，默认仍0；另一次子套件启动异常无完整日志，补齐异常类型/超时输出记录后整套通过，不把单独套件通过当作全套结果。

真实CLI到独立HTTP/PG生成6 Trace/14Span、6治理事件和2待审核动作，最大int64完整保留、可领取状态但未决定/领取。保留的本机UI另运行同样5次尝试的演示，浏览器核对合成审批2条以及新Trace的2模型/1工具/1Agent、输入14/输出6。动作10分钟自然过期，无恢复宿主、无真实Provider请求。

证据在artifacts/check、artifacts/ui035/check、artifacts/ui035/demo，浏览器截图model-chain.png/reproducible-demo.png；汇总见[validation.json](validation.json)。文档/依赖/协议/有限候选检查通过。未创建GitHub远端、提交或推送，私有开发快照可准备上传，公开许可仍未定。
