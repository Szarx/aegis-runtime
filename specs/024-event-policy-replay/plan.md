# SPEC-024 方案

抽取021已有验证函数为read_bundle，在函数末尾返回manifest/rows；verify_bundle保持只返回manifest，所有旧校验逻辑保留。回放脚本读取验证快照后遍历，直接调用已有不可变Policy.evaluate，不依赖SDK/Runtime/Collector。

报告逐事件保留已接收的白名单；候选只新增决策/分类。输出复用工作台write_report，保守状态把空包和revision不符交给审查。导出manifest摘要采用规范JSON，明确不等于原文件字节哈希或来源认证。

测试覆盖受控历史包、真实CLI和真实SDK/HTTP/PG导出链；停服后执行两候选回放，验证无网络/原工具。平台/迁移/UI/Policy核心保持，脚本与021函数兼容回归，独立target只装既有Policy包验收。
