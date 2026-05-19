# 前端开发最佳实践

## 组件设计原则
- 单一职责：一个组件只做一件事
- 受控/非受控：状态提升到最近的公共父组件
- 组合优于继承：用 children/slot 实现复用
- Props 向下，Events 向上（单向数据流）

## 状态管理
- 本地 UI 状态：useState（不需要共享的状态）
- 跨组件状态：Context / Zustand（轻量）/ Redux（复杂场景）
- 服务端状态：React Query / SWR（自动缓存、重试、同步）

## 性能优化
- 大列表：虚拟滚动（react-virtual / vue-virtual-scroller）
- 重渲染：React.memo / useMemo / useCallback（先 profile 再优化）
- 代码分割：路由级别懒加载（React.lazy + Suspense）
- 图片：WebP 格式，懒加载，合适尺寸

## 错误处理
- API 调用：统一错误拦截（axios interceptor），用户友好提示
- 边界情况：ErrorBoundary 捕获渲染错误
- Loading/Empty/Error 三态：每个数据依赖区域都要处理

## 可访问性（a11y）
- 语义化 HTML：button 做按钮，a 做链接
- 图片必须有 alt 属性
- 表单 label 关联 input（for/id）
- 键盘可操作：所有交互元素可 Tab 到达
- 颜色对比度：正文 ≥ 4.5:1（WCAG AA 标准）
