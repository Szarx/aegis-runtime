# 统一配置的图调用与状态流

[操作指南](../../docs/managed-graph-stream.md)包含四种调用、完整/提前关闭、允许/拒绝、业务失败和平台查询。[business.py](business.py)无Aegis导入，接受宿主注入的模型客户端与工具装配函数；[run.py](run.py)用Application、显式模型Wrapper和真实StateGraph/ToolNode运行接入前后对照。

[application.json](application.json)保留v1格式，[policy.json](policy.json)只允许reader读取合成订单。模型使用官方SDK进程内合成transport，无真实LLM或业务服务访问；LangSmith关闭。完整运行产生2模型+1工具+1Agent，提前关闭只有1模型+1Agent。参数/消息/返回仅用于业务，不输出到终端或遥测。

从仓库根目录运行：`python examples/managed-graph/run.py --mode stream`；可选invoke/ainvoke/astream、--subject blocked、--fail-tool、--early-close（只适用于updates流）、--stream-mode values/combined、--version v1/v2。返回0表示合成对照验证通过，1为失败。默认JSONL追加到忽略的artifacts目录。

提前退出务必关闭流；清理失败保留租约，需要原循环显式重试close/aclose后才能退出Application。图/客户端由宿主拥有。详细安装、时间口径及故障边界见指南。

--model-delay-ms 0..250可模拟固定transport延迟，默认0；时间验收使用50ms避免极快请求落在同一Windows时钟刻度。async延迟原生await，不改变SDK时间字段；这些延迟不是真实模型性能。
