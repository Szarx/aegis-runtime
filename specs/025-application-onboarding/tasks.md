# SPEC-025 任务

状态：已验证，2026-10-25。

- [x] 扩大为配置、生命周期、检查、框架和平台的完整接入场景。
- [x] 配置与只读inspect、托管Application和诊断。
- [x] 原生/真实LangGraph同步异步示例、行为与生命周期验证。
- [x] 真实平台/导出/候选回放、独立安装与完整回归。
- [x] 指南/架构/机器证据、候选文件检查及环境清理。

## 完整场景交付

本轮扩大为配置/Policy快照、工具绑定、SDK资源所有权、只读检查、原业务/宿主分离示例、真实框架八组合、平台事件查询/导出/停服回放和独立安装的统一验收。README快速开始恢复先运行基础命令，再按场景导航。

新增23方法（Runtime19、契约3、真实PG1），原314全部重跑；286 Python（SDK59、Policy20、Runtime86、Collector32、契约46、真实PG43）与51前端，共337方法全部通过，无失败/错误/跳过。生命周期测试清理一处无关断言后19项重新通过，不重复计入方法。机器结果见[validation.json](validation.json)。

| AC | 实测证据 |
| --- | --- |
| 2501 | 严格JSON/大小/字段/标识/重复配置、相对路径与不可变Policy、直接构造校验；inspect不启动SDK或创建文件，token/端点/路径不回显，依赖/环境缺失blocked，输入输出错误2；已有SDK不被接管或关闭 |
| 2502 | 配置权限固定、未知/重复/生成器拒绝，签名/返回对象/异常身份保持；Agent/Tool上下文与内容白名单；async在原任务await、取消归还计数；线程/任务未结束拒绝关闭；关闭后入口失效，flush/关闭故障不重跑业务，重试清理不关闭后来他人SDK |
| 2503 | 原生/真实StateGraph+ToolNode×sync/async×reader/blocked八组独立进程；基线业务1次，允许1次且结果一致、拒绝0次且有意改变结果；每组2Span父子正确，cwd变化不改变配置相对路径 |
| 2504 | 八组合通过真实OTLP/Collector/PG产生8Trace/16Span/8事件、允许4/拒绝4；查询全部Trace关联后导出8事件并停服。原Policy回放退出0/8不变，放宽候选退出1/4放宽+4不变 |

## 安装与兼容证据

重新构建Runtime wheel，SHA-256为9d87ea28425d0bb6a56a810e313150bf3b478e05d4ed80c1524bada49a9e9c83。全新venv从已验证本地缓存安装SDK015、Policy023和当前Runtime wheel，pip check通过；仅8个已安装分发（含pip），没有LangGraph/OpenAI/HTTPX/OTLP。-I模块检查实际从新环境导入，原生允许1/拒绝0、各2Span及关闭成功；缺OTLP元数据在inspect被检出。所有旧Runtime Python源码字节与015包相同，新功能以application/__main__追加。

这是离线缓存安装验收，没有在线下载或人类首次接入计时。真实LangGraph/OTLP在完整开发环境和平台回归中验证；不把核心新环境冒称已装这些可选项。SDK/Policy/Collector实现、UI/API与四迁移保持；前端测试重跑，类型/构建/页面继承020。没有新服务镜像构建声明。

本机明细：artifacts/check/result.json与tests.log、artifacts/application-onboarding-frontend.json、artifacts/application-onboarding/installation.json、docker.json及新环境产生的配置/JSONL。生成物不提交。62 pins、44来源、双平台缓存哈希与历史59条收据不变；OpenAPI保持020/旧011兼容，文档/候选文件检查和pip check通过。

专用aegis-spec025-check健康、测试schema清零后关闭容器/网络，卷保留；用户原有平台未动。新venv仅作本机可复验产物保留，没有全局包安装、真实LLM、策略部署、审批执行或GitHub远端/推送/CI。

边界：配置来自可信宿主，身份不是外部认证；原始未包装工具不受保护，清单不等于自动绑定。关闭前必须等待工作，违规退出可报busy并保留活动会话。生命周期是同步的、当前不托管stream/async context；高级图流与审批仍使用原显式入口。元数据检查不是网络健康或生产治理保证。
