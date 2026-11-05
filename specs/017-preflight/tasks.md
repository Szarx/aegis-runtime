# SPEC-017 任务

状态：已验证，2026-10-23。

- [x] T1701：冻结只读检查、报告隐私与验收边界。
- [x] T1702：标准库doctor与显式配置检查。
- [x] T1703：失败/隐私/退出码及真实CLI验证。
- [x] T1704：接入文档、受影响回归与机器证据。

## 实际验收

本轮18个接入契约方法全部通过，无跳过：原onboarding8、016配方4、新预检6。旧238中12重跑、226沿用，目录244（包含沿用35前端方法）。七次真实doctor CLI、旧配方八次CLI和子场景不重复累加方法数。未改核心包/服务端/SQL/UI，不声称本轮重跑SDK/Runtime/PG/页面或wheel安装。

| AC | 实际结果 |
| --- | --- |
| 1701 | native5 / langgraph12 / reviewed-async-graph16个关键发行包与锁及本地版本核对；missing/mismatch/unavailable分别失败，包异常/任意实际版本不回显；模拟Python3.10直接unsupported，不读取包；缺失或损坏仓库基线失败关闭 |
| 1702 | 默认不读环境凭证；显式producer/executor非空ASCII/不同及key形状检查，缺失/换行/相同令牌/短key/非hex均失败，值/长度/哈希不进入输出；metadata阶段禁止导入任何模块仍通过，不导入Agent/框架 |
| 1703 CLI | 当前venv native、langgraph、reviewed-async-graph匹配；当前解释器-I -S只有标准库，native报告missing并退出1；既有015独立核心环境native通过，无需框架包；显式配置清空后退出1，合成有效形状退出0。共7次真实CLI |
| 1703 报告 | 首次显式输出JSON与stdout相同，第二次同目标退出1、原文件字节不变；失败固定类别且不回显路径。文本/JSON指导下一步，不自动修复，不作网络/认证或接入成功结论 |

首次六项测试在共同setUp中发现版本格式检查误拒绝锁中的0.66b1；修正为支持当前基线中的beta/rc/dev表示后六项通过，再完整18项回归全通过。没有修改锁或放宽匹配规则来绕过失败；发行包实际版本仍须精确一致。旧Python分支模拟验证，实际解释器为Windows Python3.12.14。

执行入口：

```text
python -m unittest discover -s tests/contract -v
python scripts/doctor.py --json
python scripts/doctor.py --profile langgraph --json
python scripts/doctor.py --profile reviewed-async-graph --json
```

测试中的015独立核心venv是本机可选附加场景；新环境缺少该忽略目录时仅不运行这个附加CLI，不要求把本机缓存加入仓库。本轮已实际运行并保留证据。

## 证据与边界

[validation.json](validation.json)含计数、7组CLI固定字段报告与继承范围，忽略目录artifacts/preflight保存tests.log/tests.json/cli.json。测试临时报告自动清理；默认doctor不保存文件，显式输出需父目录已存在且目标不存在。三profile都只验证列出的元数据，不覆盖完整传递依赖/动态import/二进制或业务行为。

本轮无模型/网络/SQL请求、无Docker操作、无包安装/修改、无新第三方版本。旧配方回归仍使用合成HTTP，不访问Provider。62-pin两平台缓存哈希、41来源、当前OpenAPI、文档链接、凭证模式与pip check另行核对。核心包与平台证据按016/015和历史来源继承，人工接入5分钟仍待实测。
