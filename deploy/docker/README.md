# 本地部署

[SPEC-002](../../specs/002-collector/spec.md) 提供 PostgreSQL 16 + Collector，[SPEC-003](../../specs/003-dashboard/spec.md) 加入 Vue Dashboard / Nginx 同源代理。当前 Compose 启动这三个服务。

## 启动与示例

仓库根目录，Docker Desktop / Compose 可用时：

```text
docker compose up -d --build --wait
```

默认 Dashboard 为 `http://127.0.0.1:8080`，Collector 为 `http://127.0.0.1:8000`，PostgreSQL 为 `127.0.0.1:5433`。可将根目录 `.env.example` 复制为 `.env` 后调整端口和本地凭证；`.env` 不提交。端口仅绑定回环地址，Collector 和 Nginx 均使用非 root 用户。若修改数据库密码，当前连接 URL 配置需使用 URL 安全字符。

按 [SDK 说明](../../sdk/python/README.md) 安装本地 SDK 与 OTLP 可选依赖，然后运行：

```powershell
$env:AEGIS_API_TOKEN = "aegis-local-dev"
python examples/native-python/agent.py --endpoint http://127.0.0.1:8000/v1/traces
$headers = @{ Authorization = "Bearer $env:AEGIS_API_TOKEN" }
Invoke-RestMethod http://127.0.0.1:8000/api/v1/traces -Headers $headers
```

一次示例新增 2 个 Trace / 4 个 Span。打开 Dashboard 输入相同 token，连接后查看成功和失败执行、父子树、时间线和节点详情；刷新页面需重新输入 token。也可用返回的 trace_id 请求 `/api/v1/traces/{trace_id}`；Collector 的 `/docs` 查看 API。Bearer 值必须与 Compose 配置一致，示例从环境变量读取，不能写入遥测。

Dashboard 在官方 Node 22 构建阶段执行 npm ci、类型检查和生产构建，再由 Nginx 静态服务运行。它只代理同源 /api 到 Collector，不把 token 写入 JavaScript，也不需要开放 CORS。仅启动后端可用 `docker compose up -d --build --wait postgres collector`；本机前端开发见 [Dashboard](../../dashboard/README.md)。

## 数据与停止

Collector 在启动时执行迁移 1 + 2，等待数据库健康后启动。迁移 2 保留原生数据并允许 LLM；readiness 要求两项迁移均完成。`postgres_data` 卷保留数据库，重启 Collector 不丢失记录。

```text
docker compose restart collector
docker compose down
```

`down` 保留数据库卷。再次启动使用已有数据和初始化时的数据库密码；修改环境变量不会自动修改已有数据库用户。只在明确需要清空本项目数据时才删除对应卷。

PostgreSQL 固定官方镜像 digest。Python 基础镜像使用 3.12-slim，本次下载校验记录见 [镜像来源](../../resources/downloads/python-image.json)，它不代表后续同名 tag 不变。依赖由根目录锁文件安装，可选 [wheelhouse](wheelhouse/README.md) 支持已校验的离线构建。构建默认需要访问官方镜像库和 PyPI。

前端 Node / Nginx 来源见 [Dashboard 资源笔记](../../resources/notes/dashboard.md)，npm 默认从官方 registry 按锁文件安装；可选 [独立 npm 缓存](npm-cache/README.md) 支持离线安装。缓存不进入最终 Nginx 运行镜像。

OpenAI 离线示例也可使用同一 endpoint，见 [示例说明](../../examples/openai/README.md)。本地开发配置尚无 TLS、多租户或生产权限管理；DeepSeek 限定范围真实调用见 SPEC-005，LangGraph 真实框架/合成模型见 SPEC-006/007；框架内真实 Provider 与人工首次接入另行验收。后端证据见 [SPEC-002](../../specs/002-collector/tasks.md)，Dashboard 见 [SPEC-003](../../specs/003-dashboard/tasks.md)，LLM / 用量与本轮三服务部署见 [SPEC-004](../../specs/004-openai/tasks.md)。

## SPEC-008 平台体验续验

用户恢复 Docker 后，在独立项目/新数据库上执行带构建和健康等待的启动，补装两种快速开始环境的 OTLP extra，实际核对 3 Trace / 8 Span。三服务健康约 26.2 秒、首次查询约 44.3 秒、页面列表/详情确认上界约 107.9 秒；已有镜像/包缓存与 SDK 环境，不包含在线下载或人类首次接入。详细步骤与连续计时见 [008](../../specs/008-onboarding/tasks.md)。测试容器已停止移除，新旧数据库卷均保留。

## 可选审批准备：SPEC-010

Compose 默认不给审批角色设置凭证。启用时同时提供互异且与 AEGIS_API_TOKEN 不同的 AEGIS_APPROVAL_REQUEST_TOKEN / AEGIS_APPROVAL_REVIEW_TOKEN，AEGIS_APPROVAL_REVIEWER 默认为 local-reviewer。只配置一种/复用凭证会拒绝启动。数据库当前迁移为 {1,2,3}，保留卷和旧 Span。重建 Collector / Dashboard 后打开“审批准备”，配置与密钥管理见 [审批接入](../../docs/approvals.md)。批准记录不执行工具。

## 可选同步执行审批：SPEC-011

在既有两种审批凭证之外，显式设置AEGIS_APPROVAL_EXECUTION_TOKEN（不可与任何其他角色/Trace token复用），AEGIS_APPROVAL_EXECUTOR默认local-executor。缺执行凭证只关闭新协议，旧010仍可用。当前迁移{1,2,3,4}，新表不升级旧准备记录。重建服务后已领取动作保持消费/未知，不能重试。完整参数将显式存入数据库，默认Span/旧010不采集它们；见 [接入](../../docs/reviewed-execution.md)。
