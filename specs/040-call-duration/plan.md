# SPEC-040 方案

1. callDuration.ts从已接收Span派生最长20条和总数，bigint保持比较及百分比，视觉宽度限制后才转Number。
2. CallDurationRank原生details/表格组件发出定位事件，TraceDetail统一清筛选/选中/焦点及039链接；现有时间线和用量不改。
3. 针对性回归与编译后浏览器定位/0ns/无额外请求/窄屏，整理独立Trace阅读指南和最新索引/证据。
