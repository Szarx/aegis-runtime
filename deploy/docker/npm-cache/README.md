# 可选 npm 缓存

默认此目录只有说明，Dashboard 镜像在线执行 npm ci。若放入独立的 npm `_cacache/`，镜像改为 `npm ci --offline --cache /npm-cache`，仍由 package-lock 的 integrity 检查每个包；缺包即失败，不静默下载或改变版本。

本次缓存来自官方 registry，包含普通依赖和 Linux x64 的 Rolldown / lightningcss 可选二进制。缓存不入 Git；切换平台或依赖后须重新准备完整缓存，或移出缓存后采用在线构建。不要复制包含私有 registry 内容的个人全局缓存。

源码输入是 dashboard/package.json / package-lock.json，缓存只是可丢弃的构建加速。本轮版本与证据见 [SPEC-003](../../../specs/003-dashboard/tasks.md)。
