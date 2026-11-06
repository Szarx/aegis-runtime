# SPEC-050 任务与验收

状态：已验证并公开交付，2026-11-06。

- [x] 5001：001–049 逐项分类为可公开技术档案，当前入口与历史事实分离；50 项目录与 654 个候选分类、822 条本地链接通过。
- [x] 5002：Apache-2.0；四个实际非 editable 安装包包含 LICENSE/NOTICE；第三方 MIT 模板原字节和浏览器依赖完整声明核对；安全报告入口已启用。
- [x] 5003：工作树、实际暂存与提交字节、全部可达历史检查通过；历史删除秘密仍阻断、分支覆盖、目录缺漏、越界链接与隔离清理边界有失败测试。无原始日志/凭证/用户数据提交。
- [x] 5004：全新源码导出与在线 PyPI 安装通过；干净 GitHub checkout 无缓存在线构建三服务，迁移 1–4、认证、15 Trace / 32 Span / 13 事件、父子关系、同源代理、资源/第三方声明和重启持久化通过。
- [x] 5005：完整本机统一回归 393 Python + 109 前端，共 502，零失败/错误/跳过；类型/构建/预算通过。实际公开运行时提交的 Python、Dashboard、local-platform 三项 Linux CI 全通过。
- [x] 5006：原 main 快进更新，不改写旧历史；远端 SHA 核对。CI 通过后公开仓库，匿名读取 README/LICENSE 与提交字节一致，GitHub 识别 Apache-2.0，私密漏洞报告启用，临时部署密钥已撤销。

## 交付证据

运行时公开提交为 `82ed907d8ccd6e248451195778d64e9afd2e6705`，其 [完整 CI](https://github.com/Szarx/aegis-runtime/actions/runs/42193107104) 三个 job 成功。仓库为 [Szarx/aegis-runtime](https://github.com/Szarx/aegis-runtime)。本文件、需求状态与目录随后仅回写交付证据；后续归档提交状态可在 [Actions](https://github.com/Szarx/aegis-runtime/actions) 查看。

[validation.json](validation.json) 记录实际摘要、远端作业与匿名读取哈希。本机冻结候选 653 文件摘要前后相同，归档后候选为 654；其后 README、Docker public 复制及 smoke 计数修正由真实三服务和最终运行时提交 CI 验证，不冒称是原摘要的同一字节集。原始日志和缓存保留在忽略目录，不作为公开源码。

## 保留的失败与边界

本机首轮 Docker Hub 认证端点超时；次轮 npm 容器联网 ECONNRESET。明确使用已有官方基础镜像和已核验 npm 内容缓存的本地回退最终通过，不能当作在线干净构建成功；线上门槛由 GitHub 干净 checkout 实际完成。

首次 smoke 断言漏计模型图自身的一条 allow 事件，导致 [首次 CI](https://github.com/Szarx/aegis-runtime/actions/runs/42192305168) 的平台 job 失败。修正后在全新隔离项目核对精确 15/32/13，不重试旧业务动作；旧失败报告保留。

真实生产 Nginx 页面核对了无认证合成演示、返回工作区、连接、15 条列表和模型/受控工具轨迹。全部 Provider 调用为合成边界，无新真实模型请求；公开是早期源码预览，未发布 PyPI/npm 包，不具备生产身份/多租户、完整审计、持久传输或分布式恢复保证，见 [能力边界](../../docs/capabilities.md)。

原始日志/截图、凭证、审批/业务数据、checkpoint、依赖缓存、虚拟环境和临时交付脚本继续排除。所有历史技术 SPEC 保留当时口径。完成本 SPEC 后停止，不启动下一项。
