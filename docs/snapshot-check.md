# 私有开发快照统一验收

先安装[开发依赖](../requirements-dev.lock)、四个本地Python包及Dashboard的npm锁定依赖，并准备专用可删除测试schema的PostgreSQL。命令不安装依赖、不启动数据库、不请求真实模型或发布仓库；不要指向生产数据库。

从仓库根目录运行（数据库URL通过本机环境变量AEGIS_TEST_DATABASE_URL提供，不写入命令/聊天）：

```text
python scripts/snapshot_check.py --postgres --node "C:\Program Files\nodejs\node.exe"
```

Node在PATH中可省略--node。默认输出新建artifacts/snapshot-check/随机ID；--output可选择artifacts内尚不存在的子目录。拒绝覆盖已有目录。不要同时运行多份检查器或在运行中编辑候选文件，Dashboard构建目录仍由项目共享。

依次执行pip check、有限候选检查、完整Python/专用PG、前端单测/类型/构建/预算，最后对照运行前后的Git候选文件路径/字节摘要。任一步失败、缺失/不完整报告、skip、超时或源变化均退出1；预检问题退出2，全部通过退出0。result.json记录运行中阶段和结果；各阶段stdout/stderr分开保存在同一目录。异常不在汇总中复制私密诊断，但第三方工具日志仍应按本机诊断内容保管。

Python进入套件前先执行有界只读数据库连接/SELECT 1，数据库不可用时固定报错退出2，不输出连接串。快照父入口将子检查非零退出视为本次失败，不把缺数据库视作skip通过。前端完成后会重新核对实际资源哈希，候选检查计数须与启动时源摘要一致。

Python子检查使用独立python/目录，前端使用dashboard/目录，不借用旧receipt。Python必须六套件有测试、无skip且汇总一致；前端必须tests/types/build完整和固定预算通过。最终摘要只证明本机这次检查，不能证明Git历史无秘密、暂存区相同、远端CI通过或平台可生产部署。授权与公开许可继续按[私有仓库准备](github-readiness.md)。

超时终止直接子进程；其派生进程可能仍在收尾，先查进程/阶段日志再重跑，避免并发数据库测试。单套Python测试仍由原检查器限制900秒，总阶段6000秒；前端阶段1000秒，原子步骤各300秒。检查不重置UI数据；各测试负责专用schema清理。报告不是签名或不可篡改证明。

源摘要包括当时Git跟踪文件与非忽略untracked候选，不包含被忽略的构建/缓存/本地配置；后续编辑文档/代码也会改变摘要。归档验收记录后应对最终候选重新运行，以最终报告对应的摘要为准。细节与当前验收进度见[041任务](../specs/041-snapshot-check/tasks.md)。
