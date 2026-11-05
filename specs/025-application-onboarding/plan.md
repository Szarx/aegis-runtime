# SPEC-025 方案

Runtime包增加配置和Application模块，不修改原Runtime/Policy求值器。不可变配置对象校验所有直接构造入口，文件加载固定Policy快照。JSONL与OTLP装配复用既有SDK，资源归Application自身SDK句柄；不会调用全局shutdown清理他人会话。

RLock保护状态/绑定和进行中调用计数，函数包装复用Runtime.tool/aegis.observe并保留sync/async类型；调用租约覆盖await/finally，close只在计数0时转换状态。关闭不重跑业务，错误/超时仅影响诊断。全局SDK仍由原init原子拒绝二次初始化。

CLI inspect只读取配置/Policy与元数据/显式环境引用。示例用两个业务工具的配置，显式绑定实际调用工具；真实LangGraph ToolNode处理已包装工具，不把synthetic模型节点伪装成LLM调用。验收覆盖8组合、故障和生命周期，以及真实平台→导出→回放闭环。UI/API/四迁移保持，Runtime wheel重新构建安装验证。
