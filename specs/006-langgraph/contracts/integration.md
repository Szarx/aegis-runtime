# 显式 StateGraph 接入契约

三个观测接入点如下，不改图节点与路由；初始化、导出配置和清理另计：

```diff
+ import aegis
+ from aegis.openai import wrap_openai
+ from aegis.langgraph import observe_graph

+ client = wrap_openai(client, provider="deepseek")
+ lookup_order = aegis.tool(lookup_order, permission="orders.read")
  order_tool = StructuredTool.from_function(lookup_order)
  # 原有 StateGraph 节点、边与编译保持不变。
  graph = builder.compile()
+ graph = observe_graph(graph, name="order-agent")
  result = graph.invoke(input_state, config=config)
```

这份最小差异含 3 个 import 和 3 个接入语句，共 6 行新增，不含空行、SDK init / flush / shutdown，也不代表任意项目都只需 6 行。工具先包装函数再创建 StructuredTool；已有 StructuredTool 对象不由 observe_graph 自动发现或改写。已有 Aegis 模型代理可直接复用，重复 wrap 幂等。

observe_graph 只在 invoke / ainvoke 周围建立 v1 Agent Span；with_config 保留代理。原回调与全部调用参数照常进入框架；Agent 不采集 state/config/messages。范围外 stream / astream / batch / with_retry 等原方法委托不自动创建 Agent Span，返回的原图/绑定也不保证保持包装；需要新 spec 验证后扩展。

显式 LLM / Tool 在真实框架上下文中关联到 Agent。图中的纯路由/状态步骤不生成假 LLM 或假 Tool；没有接入装饰器的工具不自动追踪。模型只由已有 Wrapper 负责，框架不重复创建第二份 Span。

基准仅为本地已安装环境中“baseline 构造/调用 + traced 构造/调用到首次 flush”的计时；不包含环境安装、平台启动或人工修改，不能据此声称新用户 5 分钟接入达标。实际观测见 [tasks](../tasks.md)。
