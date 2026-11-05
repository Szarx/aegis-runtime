# SPEC-031 方案

1. 纯函数过滤TreeRow并计算键盘相邻ID，保留原对象/顺序/深度。组件分别维护完整rows与可见rows，选中状态按可见列表核对。
2. 原生按钮组使用roving tabindex与aria-pressed，keydown只绑定节点按钮，nextTick后聚焦新的可见按钮。
3. App维护会话密度并传递详情行高，Timeline默认兼容旧46；Token卡移除费用占位列，保留原汇总算法。
4. 有意义的纯函数用例和55既有前端方法，类型/构建；复用隔离服务实际验证筛选、键盘、Canvas行高和手机布局。
