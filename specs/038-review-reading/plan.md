# SPEC-038 方案

1. reviewQueue纯函数在已有筛选后排序，原始顺序复制返回；时间戳与Action ID作为确定键。
2. 收件箱维护本页sort和查询完成时间，sort加入确认重置watch。DOM time显示完整本地时间，不增加本机到期授权逻辑或轮询。
3. Action CopyValue和绑定details缩短展开区；完整参数/显式确认/决定方法不变。测试后准备新合成pending，真实浏览器只核对不提交决定。
