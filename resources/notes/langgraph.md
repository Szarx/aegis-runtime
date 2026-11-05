# LangGraph 首批接入依据

查阅/验证：2026-10-17，Asia/Shanghai，用于 SPEC-006。

- [官方 Quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart)：图状态、模型节点、工具循环与条件路由；本项目用合成 transport 代替真实模型，实际框架保留。
- [官方 Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)：stream / astream、stream modes 与 1.2 新事件流；本轮明确不声称这些 API 已支持，需独立冻结生命周期。
- [官方 PyPI LangGraph 1.2.15](https://pypi.org/project/langgraph/1.2.15/)：固定发行与依赖元数据；安装后核对 CompiledStateGraph.with_config 实际返回编译图副本，ToolNode 的公开错误处理参数与 convert_to_openai_messages。

Graph reference 页面本轮打开失败，不用其未读取内容作为证据。实际安装基线 LangGraph 1.2.15、langchain-core 1.6.12、langgraph-prebuilt 1.1.1、checkpoint 4.3.0、sdk 0.4.8、langsmith 0.14.11，Python 3.12.14。可选集成不由核心 import 加载。

## 依赖凭据与验证

原有 39 包版本保持不变，新增 20 个必要包，根锁文件共 59 pins。官方 PyPI metadata 与下载字节 SHA256 对照，保留 004 历史清单：

- [Windows CPython 3.12](../downloads/spec006-python-windows.json)。
- [Linux CPython 3.12 x86_64](../downloads/spec006-python-linux.json)，Collector 镜像 59 包离线安装通过。

使用实际 StateGraph / ToolNode 测试，不手写假框架回调。采用公开 invoke / ainvoke 边界，保留宿主 callbacks，模型/工具只由已有显式 Wrapper / Decorator 记录；避免长生命周期 callback context 和重复 Span。

框架确实运行，但模型响应是合成数据；没有新增真实 Provider 请求。没有 state/config/messages、正文或凭证进入遥测。安装/构建缓存和截图在 gitignore 内；下载元数据与原始整理笔记可提交，不镜像整篇第三方文档。
