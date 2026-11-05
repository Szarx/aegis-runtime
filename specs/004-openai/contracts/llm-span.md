# LLM Span v2 契约

OTLP：scope.name=aegis、aegis.mapping.version=aegis.genai.v2、operation=chat、kind=CLIENT、name=`chat <gen_ai.request.model>`。本地 schema_version=aegis.span.v2。原生 v1 Agent/Tool 保持原格式与 INTERNAL；不接受不匹配的 mapping/operation/kind。

字符串属性：原有 error.type、可选 gen_ai.agent.name，加 gen_ai.provider.name=openai、gen_ai.request.model（必需，1–128）、gen_ai.response.model（可选，1–128）、aegis.call.api=responses|chat.completions、aegis.call.mode=stream|non_stream、aegis.call.outcome=completed|incomplete|closed|cancelled|error。其他保留字符串规则沿用 v1，NUL 拒绝。模型输入不合法时追踪使用 unknown_model，原始参数仍交给 SDK 验证，不替调用者更改。

整数属性只有 gen_ai.usage.input_tokens / gen_ai.usage.output_tokens，OTLP int_value，0…2^63-1，bool/浮点/数字字符串/负数拒绝；省略表示未知。Responses 取 usage.input_tokens/output_tokens；Chat 取 usage.prompt_tokens/completion_tokens。重复最终统计覆盖相同字段，不相加。

异常只保存类型；取消保持真实异常类型。Responses failed 使用固定 `openai.response.failed` 类型；incomplete / closed 不伪装成功完成，保持 UNSET 并显示结束原因。completed 与完整消费分开：正常 EOF 未观察到终态为 incomplete；观察终态后 close 保留该终态。

名称、usage 等元数据来自官方 SDK 字段；provider 标明 OpenAI API 接入类别，不作为可信身份，也不代表验证所有自定义 base_url 的模型服务。Agent/Tool 参数、prompt/messages、output/delta、tool calls 原文、response/request ID、地址、headers、API key、异常消息均不采集。

服务端表结构不新增列，attributes JSONB 保存类型化值；迁移 2 扩展 operation/kind 并约束有效配对。查询 Span schema 的枚举扩展，attrs 为严格 str|int；Token 前端为 bigint，显示十进制完整值，不通过 number 舍入。Trace 汇总的时间、状态与数量语义不变，不新增 Token 求和。
