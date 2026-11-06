# 公开材料与 GitHub 交付

2026-11-06 用户选定 Apache-2.0，并授权 SPEC-050 验收后公开现有仓库。此前 046 已交付私有快照及首轮 CI；“未建立远端”的旧记录只适用于对应历史时点。当前仓库为 [Szarx/aegis-runtime](https://github.com/Szarx/aegis-runtime)，最新交付结果见 [050](../specs/050-public-preview/tasks.md)。

## 哪些可以公开

| 材料 | 处理与理由 |
| --- | --- |
| SDK / Runtime / Policy / Collector / Dashboard 源码 | 公开；产品实现。模型/框架与平台职责清晰，根授权适用于自有代码 |
| tests、合成 fixtures 和 examples | 公开；可复现行为，只有合成身份/token/业务数据；默认不调用真实模型 |
| specs 的需求、方案、任务、兼容快照和无秘密摘要 | 公开归档；技术决策和兼容证据。旧状态不是当前承诺，原始本机报告不随附 |
| README / docs / ADR / roadmap | 公开；当前使用和边界，草案明确标注；不写私人联系方式或本机用户路径 |
| resources 链接、原创笔记、版本/URL/哈希收据 | 公开；追溯依据，不发布整站/文章镜像或第三方安装缓存 |
| 固定官方 ReAct 模板 | 原字节保留、附 MIT 原许可证和文件哈希，明确服务边界替换范围 |
| CI、锁文件、Compose、Dockerfile、环境模板和检查脚本 | 公开；重建环境所需，默认回环与合成凭证，不依赖本机 tmp |
| Apache LICENSE / NOTICE 与第三方声明 | 公开；授权、署名和分发依赖条款；第三方材料不被重新授权 |

## 必须留在本地或私有系统

模型/平台凭证、`.env`、真实输入输出和审批参数、checkpoint/SQLite、原始 Trace/导出包、日志/截图、虚拟环境、node_modules、wheel/npm/镜像缓存、本机临时交付脚本。当前分别由 `.gitignore` 与对象检查拦截；不要把数据写到正常源码扩展名中绕过忽略。

`artifacts/` 的文件名只出现在历史说明中；公开的 validation.json 是有限摘要，不能当作原始报告、签名或来源认证。合成 Trace/Action 标识、历史测试端口与合成角色 token 可公开，不提供访问真实系统的权限。

## 可重复检查

```text
python scripts/public_check.py
python scripts/repository_check.py --history
python scripts/repository_check.py --staged
python scripts/repository_check.py --commit HEAD
```

第一条核对全量 SPEC 目录、分类、授权与本地链接；第二条检查全部可达历史的树，防止只清工作树；后两条比较实际待交付与已提交树。模式扫描有限，不构成秘密永不泄露的证明。工作树、暂存和提交可以不同，必须对实际推送对象检查。

完整本机回归使用 [snapshot_check](snapshot-check.md)，远端 CI 使用固定官方 Actions、最小 contents:read 权限、不保留 checkout 凭证。没有发布包/部署 job，不需要真实模型密钥。公开前等待该提交 CI，并验证无缓存干净检出的三服务与合成数据流；记录失败轮次，不能借用早期结果。

公开交付只快进原 main，不强推或删历史。推送后核对远端 SHA，CI 通过再按授权切换可见性、启用私密漏洞报告并匿名验证。后续公开提交沿用同一流程；正式版本/包注册发布另设验收。
