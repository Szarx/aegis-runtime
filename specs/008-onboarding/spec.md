# SPEC-008：首次本地接入与可重复测量

日期：2026-10-18。先冻结验收口径再实现；不追加真实 Provider 请求，不把机器运行时间称为人类首次接入耗时。

## 目标与范围

用户从本地源码仓库执行一条命令，在全新虚拟环境中安装选定接入依赖、运行已有离线 Agent，自动确认首个有效 Trace。减少新用户需要先了解全套开发依赖、编辑 shell 环境、启动收费模型的步骤。支持 native 和 langgraph 两种 profile；不引入新的 SDK API、框架适配或生产部署能力。

平台启动与首次可见 Dashboard 是独立阶段，需要 Docker Engine 和人工页面操作。当前 Docker 不可用时，仍交付和验证本地安装/Trace 流程，平台阶段如实标为未执行；不能据此勾选 5 分钟人工接入或 10 分钟完整体验目标。

## 行为与约束

1. 入口 `python scripts/quickstart.py --profile native|langgraph`。Python 3.11+，标准库启动；从脚本位置定位 repo，不依赖工作目录。每次在忽略目录 artifacts/onboarding 内创建独立 run 目录与 venv，不覆盖或清理旧环境，不需要修改当前 shell。失败保留可检查的 receipt 和环境；不自动删除任何既有文件。
2. 默认从官方 PyPI 安装，先固定 setuptools，再使用根锁文件作为 constraint 安装本地 SDK 及该 profile 的 extras。native 仅核心；langgraph 选 langgraph+deepseek；不为本地 JSONL 强制安装 Collector、数据库或 OTLP。`--wheelhouse PATH` 使用显式本地 wheel 目录并加 --no-index，禁止网络包解析回退。两种路径都用 --no-build-isolation，已固定的 setuptools 满足本地 build。
3. 每阶段使用独立 subprocess、明确超时，非零/超时立即停止后续步骤；退出码非零。report 只保存 stage 名、状态、耗时、固定错误类别和必要计数，不保存 raw stdout/stderr、命令参数、绝对用户目录、凭证或环境值。进程启动异常也写失败 receipt。失败时给出对应文档的排查入口。
4. 启动子进程不继承 PYTHONPATH/PYTHONHOME，不靠旧 .venv 或 source path 注入掩盖安装问题；关闭示例 LangSmith 跟踪，并移除模型/平台凭证。模型永远合成。langgraph CLI 原有两次 baseline / traced 比较需 equivalent=true 且次数相同；native 保留预期成功和合成失败。
5. 验证目标 JSONL：native 2 Trace / 4 Span、两条 Agent→Tool 父子关系、一个成功/一个错误；langgraph 1 Trace / 4 Span、1 Agent / 2 LLM / 1 Tool、7/3 合成用量、正确父子关系、before/after 调用次数一致。记录有效 Trace 的时间仅在校验完成后成立；坏 JSONL、丢 Span、错误父节点或诊断失败必须使验收失败。
6. receipt schema `aegis.onboarding.v1` 区分 venv / build prerequisite / SDK install / example / validation 阶段，保存总时间、profile、离线 cache/online 安装来源分类、有效 Trace/Span 数、导出诊断及平台/人工验收未执行。安装耗时包括本地包构建；不遗漏必要阶段后声称达到目标。

## 计时口径

| 阶段 | 本轮可自动测量 | 不包含 |
| --- | --- | --- |
| 创建环境与安装 | 全新 venv，按 profile 解析安装；分别标注本地已缓存 wheel 或在线 | 下载 Python、克隆仓库、用户阅读与人工修改 |
| 示例首次有效 Trace | 新进程导入、实际执行、flush、JSONL 校验 | Dashboard 首次展示、人类理解与接入改动 |
| 已有 Agent 接入 | 保留 SPEC-006 三接入点示例与差异 | 本轮不宣称新用户已在 5 分钟完成 |
| 平台与页面 | 有 Docker 时另行测量 | Docker 不可用不伪造成功或复用旧耗时 |

本轮使用已校验本机 wheel 缓存进行 native / langgraph 全新环境测量；在线下载时间未知。已有 LangGraph 框架/模型验收不替代本次新环境安装验证。

## 验收

| AC | 条件 |
| --- | --- |
| 801 | 两种 profile 可在全新 venv 离线缓存安装并运行，启动无需当前 shell 激活或模型凭证 |
| 802 | 自动校验数量、父子关系、状态、用量与业务对照，损坏/缺失数据不能被计为有效 Trace |
| 803 | 缺依赖、进程失败/超时与缺缓存时非零退出、后续业务不执行，receipt 不含原始输出或凭证 |
| 804 | 新环境路径不覆盖旧目录，任意工作目录/含空格路径可用；profile 之外依赖未被硬性引入 |
| 805 | 快速开始文档明确前提、运行、查看记录、故障排查、平台下一步与计时限制；记录实际结果和未验收目标 |

## Docker 恢复后的平台验收补充

用户已启动 Docker，继续同一增量的平台阶段。使用独立 Compose 项目和新数据卷、回环动态端口；先清理 SPEC-007 遗留停止容器，保留其数据卷。不得操作其他项目容器或删除卷。

从执行 compose up --build --wait 前开始连续计时，记录构建/三服务健康、新环境补装 OTLP extra、原生 Agent 执行与首次 HTTP 校验，再由实际浏览器确认列表与详情。已有 Python、源码、Docker 镜像/依赖缓存和 SPEC-008 已安装 SDK 环境作为前提，不伪装成首次下载或冷启动。界面确认耗时包含工具/操作者步骤，是首次确认可见的上界，不是浏览器首屏性能指标；不把上轮 SDK 时间与本次时间相加当作单次完整安装。

原生 profile 原有 2 Trace / 4 Span（成功/合成失败），使用其独立 venv 安装 otlp extra 后发送真实 OTLP，经 PostgreSQL/API/Dashboard 核对；页面首次可见计时后再验证 LangGraph profile 的 1 Trace / 4 Span。模型仍合成，不新增真实 Provider 请求。报告单独保存 platform-validation.json，不覆盖初次机器测量和历史未执行状态；更新当前产品文档的外部阻塞状态。

新增 AC806：新库健康、导出诊断、查询数量/父子/状态、真实浏览器列表/节点可见、分阶段耗时和截图均有证据；同项目 down 后保留新旧卷。AC806 完成只表示缓存环境的平台流程通过，在线下载和人工 5 分钟接入/10 分钟体验目标仍不自动勾选。
