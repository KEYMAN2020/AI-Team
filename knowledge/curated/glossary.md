# 领域词汇表

> 参考 UI/UX Pro Max 设计知识库（67 种风格、161 种配色、57 种字体、99 条 UX 准则）整理。
> Product 和 UX 角色在编写需求、设计规范时使用以下标准术语。

## 设计风格（Design Styles）

**Minimalism & Swiss Style**：极简主义 + 瑞士风格，以大量留白、几何网格、无衬线字体、高对比度为特征，强调功能性和清晰度（例：Enterprise SaaS 后台、文档站点）

**Glassmorphism**：玻璃拟态，通过 backdrop-filter: blur() 制造磨砂玻璃质感，叠加半透明层和 vibrant 背景，常见于现代 SaaS 和金融仪表盘（例：macOS Big Sur 设计语言）

**Neumorphism**：新拟物，又称 Soft UI，通过双层阴影（内凹 + 外凸）模拟浮雕/蚀刻效果，适合健康类、冥想类应用（例：健康追踪 App）

**Brutalism**：粗野主义，故意使用原始风格——默认字体、可见边框、高对比、无装饰，追求功能优先的直白表达（例：开发者工具网站）

**Neubrutalism**：新粗野主义，粗黑边框、纯色填充、无渐变、厚阴影，比 Brutalism 更活泼，带流行艺术感觉（例：中小型初创网站）

**Flat Design**：扁平设计，2D 风格、无阴影渐变、纯色块、简洁图标，Microsoft Metro / Material Design 早期风格代表（例：Windows 8 / Android 早期界面）

**Claymorphism**：粘土拟态，软 3D 效果、厚边框（3-4px）、双阴影，圆润可爱像橡皮泥玩具（例：儿童教育 App）

**Skeuomorphism**：拟物设计，通过真实纹理、深度、光影模拟现实物体（皮革、纸张、旋钮），iOS 早期风格（例：旧版 iOS 计算器、iBooks 书架）

**Cyberpunk UI**：赛博朋克，霓虹配色、深色背景、终端风格字体、扫描线效果、故障艺术，常结合霓虹蓝/紫/粉（例：游戏 HUD、科技展示）

**Bento Box Grid**：便当盒网格，受 Apple 启发的不对称模块化卡片布局，强调视觉层级和信息组织（例：Apple 官网、个人简介页）

**Material You / MD3**：Material Design 3，以 tonal 色板、药丸形状组件、柔和曲线、动态取色为特征，Google 最新设计语言（例：Android 系统 UI）

**Glassmorphism / Liquid Glass**：动态玻璃拟态，glassmorphism 演化形态，增加流动形变动效，半透明层叠加多个层级产生深度感（例：高端品牌展示页）

**Dark Mode (OLED)**：OLED 深色模式，使用纯黑色（#000000）背景以节省 OLED 屏幕功耗，搭配高对比白色文字和柔和强调色（例：移动端阅读、游戏界面）

**Biomimetic / Organic 2.0**：仿生有机设计，受自然启发的细胞状、流体质感、呼吸动效，常结合生成式算法（例：生物科技公司展示）

**Spatial UI (VisionOS)**：空间用户界面，Apple Vision Pro 设计语言，玻璃材质、深度层级、注视交互、手势控制（例：visionOS 系统界面）

**Zero Interface**：零界面，AI 驱动的隐形界面设计理念，语音优先、手势控制、无可见 UI 元素（例：AI 语音助手、智能家居）

**Kinetic Typography**：动态排版，通过文字动画（移动、变形、滚动触发）传递信息的视觉技术（例：产品宣传视频、品牌首页 Hero 区）

**Vaporwave**：蒸汽波风格，复古未来主义，80/90 年代怀旧，霓虹黄昏渐变、故障效果、希腊雕像元素（例：音乐网站、NFT 展示页）

**Brutalism / Anti-Polish Raw**：反精致原始美学，手绘、拼贴、扫描纹理、故意不完美，追求真实感和人文温度（例：独立创作人网站）

**Micro-interactions**：微交互，界面中小而精确的动画反馈（按钮点击弹性、开关过渡、加载状态），提升用户体验的质感（例：点赞动画、消息提示）

## 配色系统（Color Systems）

**Color Palette / Design Tokens**：设计系统中的色彩规范，包含 Primary / Secondary / Accent / Background / Foreground / Card / Muted / Border / Destructive / Ring 等 17 个语义化色阶 token（例：Tailwind CSS shadcn/ui 配色体系）

**Primary / 主色**：品牌核心色，用于主要操作按钮、导航高亮和关键 UI 元素，通常选择有辨识度的饱和色（例：蓝色 #2563EB 用于信任感强的 SaaS 产品）

**Accent / 强调色**：用于 CTA 按钮、优惠标记、关键转化路径的高对比色，通常与主色互补（例：橙色 #EA580C 与蓝色主色搭配）

**Destructive / 危险色**：用于删除操作、错误提示、危险按钮的红色系语义色（例：红色 #DC2626 用于不可逆操作）

**Muted / 柔和色**：用于次要背景、分割线、禁用状态的低对比度颜色（例：灰色 #E2E8F0 作为分割线色）

**Ring / 焦点环色**：输入框和可交互元素聚焦时的轮廓色，用于键盘导航可见性（例：#2563EB 与主色一致）

**Tonal Palette**：Material You 引入的色调色板概念，从壁纸图片提取主色后自动生成 5 档亮色和 4 档暗色，替代传统的 Primary / Secondary 二分法（例：Android 12+ 动态取色）

**Gradient Mesh / Aurora**：渐变网格 / 极光效果，多色渐变区域通过控制点形成连续流畅的色彩过渡，常用于品牌背景和 Hero 区域（例：Stripe 官网背景）

## 字体排版（Typography）

**Font Pairing / 字体搭配**：选择两种或以上字体组合使用（标题字体 + 正文字体），通过对比创造视觉层级（例：Playfair Display 标题 + Inter 正文）

**Sans + Sans / 无衬线配对**：双无衬线字体组合，风格一致但笔画特征不同，适合现代、专业、清洁感的设计（例：Space Grotesk 标题 + DM Sans 正文）

**Serif + Sans / 衬线加无衬线**：衬线标题 + 无衬线正文，经典高级感搭配，适合奢侈品牌、编辑出版、高端服务（例：Playfair Display + Inter）

**Mono + Sans / 等宽加无衬线**：等宽字体标题 + 无衬线正文，技术感和工业感强烈，适合开发者工具、技术博客、初创科技公司（例：JetBrains Mono + Inter）

**Display + Sans / 展示体加无衬线**：展示字体标题 + 无衬线正文，个性化强，适合创意品牌、时尚、媒体（例：Custom display font + Open Sans）

**Line Height / 行高**：行间距，通常设置为字体大小的 1.5-1.75 倍保证可读性，移动端建议 ≥ 1.5（例：16px 字号对应 24-28px 行高）

**Line Length / 行长**：每行文字最大宽度，英文建议 45-75 字符，中文建议 30-45 字，超行长降低阅读效率（例：正文容器 max-width: 720px）

**Font Size Scale / 字号比例尺**：预设的字体大小层级系统，常用 4px 步进（12/14/16/18/20/24/30/36/48/60/72px）或 Modular Scale（1.25 倍率），确保排版一致性（例：Tailwind 字号系统）

**Google Fonts**：Google 提供的开源字体库，包含 1500+ 字体，支持通过 CSS @import 或 link 标签引入（例：@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300..900')）

## UX 设计模式（UX Patterns）

**Onboarding / 用户引导**：新用户首次使用时的引导流程，应给予用户自由跳过/探索的权利，而非强制教学（例：App 首次启动的 3 步功能简介）

**Forms / 表单设计**：包含标签位置（顶部优于左侧）、错误提示位置（字段下方）、实时验证、输入类型优化（type=email/tel/number）、自动填充支持等最佳实践（例：注册表单字段验证）

**Navigation / 导航**：平滑滚动（scroll-behavior: smooth）、粘性导航不遮挡内容（padding-top 补偿）、当前页面高亮表示、返回按钮正确行为、锚点深度链接（例：单页网站导航栏）

**Loading States / 加载状态**：骨架屏优先于转圈加载，Skeleton screen 提供内容结构预览，减少感知等待时间（例：Facebook / LinkedIn 内容加载）

**Empty States / 空状态**：无数据时的友好提示，包含插图、引导文案、操作按钮，避免空白页面带来的困惑（例：任务列表为空时显示「创建你的第一个任务」）

**Toast Notifications / 轻提示**：短暂出现的消息通知（2-4 秒自动消失），用于非关键操作反馈，不打断用户当前流程（例：设置保存成功提示）

**Error Recovery / 错误恢复**：用户操作出错后提供明确的恢复路径，不要仅显示错误码（例：网络请求失败时显示「重试」按钮）

**Skeleton Screen / 骨架屏**：内容加载完成前用灰色块模拟页面布局，让用户感知内容即将到来，减少跳出率（例：新闻列表加载时的灰色占位块）

**Progressive Disclosure / 渐进式披露**：信息分层次展示，先显示关键内容，次要信息通过「展开/更多」交互暴露，避免信息过载（例：设置页高级选项默认折叠）

**Accessibility / 无障碍**：WCAG 2.1 AA（4.5:1 对比度）及以上标准，包含键盘导航、屏幕阅读器支持（ARIA 标签）、足够的触摸目标（44px+）

**Touch Target / 触摸目标**：移动端可点击元素最小尺寸 44x44px（Apple HIG）/ 48x48px（Material Design），间距 8px 以上防止误触（例：移动端按钮和图标）

**Pull to Refresh / 下拉刷新**：移动端标准刷新交互，提供加载状态指示和防抖（debounce），避免重复请求（例：社交媒体时间线刷新）

**Mobile First / 移动优先**：先设计小屏幕布局再渐进增强到大屏幕，确保核心功能在移动端完整可用（例：响应式仪表盘设计）

**Responsive Breakpoints / 响应式断点**：标准屏幕宽度断点，sm: 640px / md: 768px / lg: 1024px / xl: 1280px / 2xl: 1536px（Tailwind 标准）

**Keyboard Navigation / 键盘导航**：所有可交互元素可通过 Tab/Shift+Tab 遍历，Enter/Space 激活，Escape 关闭，焦点环（:focus-visible）可视化（例：Web 应用无障碍导航）

## 数据可视化（Charts & Data Viz）

**Line Chart / 折线图**：展示时间序列数据的趋势变化，适合 ≥4 个数据点，多系列用不同线型（实线/虚线/点线）+ 形状区分，<1000 点用 SVG，≥1000 点用 Canvas（例：月度收入趋势）

**Bar Chart / 柱状图**：比较离散分类的数值大小，水平条形适合长标签（20-50 类），垂直柱状适合 ≤20 类，值标签默认显示（例：各季度销售额对比）

**Pie Chart / 饼图**：展示部分与整体的比例关系，最多 6 块扇区，从 12 点钟方向开始排列，差异 <5% 的扇区建议用堆积条替代（例：市场份额分布）

**Donut Chart / 环形图**：饼图变体，中间空心区域可显示总数或关键指标，视觉占比感知比饼图更准确（例：预算分配比例）

**Area Chart / 面积图**：折线图变体，填充区域强调数量累积感，适合展示总量变化和趋势叠加（例：网站流量趋势 + 各渠道贡献）

**Scatter Plot / 散点图**：展示两个变量间的相关性分布，可添加趋势线（线性回归），适合大数据量下的模式发现（例：广告花费 vs 转化率）

**Heat Map / 热力图**：用颜色编码矩阵单元值的大小，适合展示行列交叉数据的密度/强度分布（例：用户点击热区、地理位置密度）

**Stacked Bar / 堆积柱状图**：多分类叠加展示总量及内部构成，适合展示整体变化和各部分贡献（例：月度营收按产品线拆分）

**Funnel Chart / 漏斗图**：展示流程各阶段的用户流失/转化，每个阶段宽度代表数量，适合转化率分析和用户行为路径（例：注册转化漏斗：访问→注册→付费）

## 设计系统（Design System）

**Design Tokens / 设计令牌**：设计系统中的原子化变量，包含颜色、间距、字体大小、圆角、阴影等，是设计和代码之间的单一事实来源（例：--primary: #2563EB; --spacing-4: 1rem）

**Design System / 设计系统**：可复用的组件库 + 设计令牌 + 使用规范 + 文档的完整体系，确保多产品视觉一致性（例：Material Design、shadcn/ui、Radix UI）

**Component Library / 组件库**：设计系统中可复用的 UI 组件集合，每个组件有明确的 Props API、样式变体、使用示例和可访问性要求（例：shadcn/ui 组件库、Ant Design）

**Z-Index Scale / 层级比例尺**：CSS 堆叠上下文的预设层级系统，确保弹窗、下拉菜单、通知等浮动元素正确覆盖，常用值：dropdown 1000 / sticky 1100 / modal 1200 / toast 1300 / tooltip 1400

**Color Token / 颜色令牌**：语义化命名的颜色变量，避免直接使用色值。层级：原始色(blue-500) → 语义色(primary) → 组件色(button-bg)（例：--primary = #2563EB; --button-bg = var(--primary)）

## 页面模式（Page Patterns）

**Landing Page / 着陆页**：营销型单页，典型结构为 Hero（大标题+CTA）+ Features（核心功能展示）+ Social Proof（客户评价）+ CTA（再次引导转化）（例：SaaS 产品官网）

**Hero Section / 英雄区**：页面首屏核心区域，通常包含大标题、副标题、主 CTA 按钮、背景视觉（视频/图片/动画），3-5 秒内传达核心价值（例：产品首页首屏大标题）

**Dashboard / 仪表盘**：数据密集型页面，将 KPIs、图表、数据表、状态指示器组织在网格布局中，按信息层级从左上到右下排列（例：Sales Dashboard、Analytics Dashboard）

**Feature Showcase / 功能展示页**：以 Feature Card 网格展示产品功能，每张卡片包含图标、标题、简述、可选演示动效，适合产品主页功能区（例：Notion 功能展示）

**Pricing Page / 定价页**：价格方案对比页面，推荐方案（Most Popular）视觉高亮，包含方案对比表和 FAQ 区（例：Figma 定价页）
