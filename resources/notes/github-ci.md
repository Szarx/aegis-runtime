# GitHub私有仓库CI来源

2026-10-23核对官方Actions的固定提交action.yml：[checkout](https://raw.githubusercontent.com/actions/checkout/11bd71901bbe5b1630ceea73d27597364c9af683/action.yml)、[setup-python](https://raw.githubusercontent.com/actions/setup-python/a26af69be951a213d495a4c3e4e4022e16d87065/action.yml)、[setup-node](https://raw.githubusercontent.com/actions/setup-node/49933ea5288caeca8642d1e84afbd3f7d6820020/action.yml)。只保存链接和原创说明，不镜像正文；不是最新版本声明。

配置用固定提交、checkout persist-credentials=false、只读contents权限，不包含发布job或真实模型密钥。官方文档只证明action声明/输入存在，不替代本仓库的GitHub执行。Git客户端直连GitHub查询失败，官方原始文件通过浏览工具可读；实际推送连通性仍待确认。

CI的Python/Postgres/Node测试与本机共用入口，首次Ubuntu远端执行独立验收。本机Windows通过不算远端通过。见 [准备清单](../../docs/github-readiness.md)。
