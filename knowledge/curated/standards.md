# 编码规范

> 所有成员遵守本规范。CR（代码审查员）在 Review 时以此为基准。

## 通用规范

- **命名**：变量/函数用 camelCase（JS/TS）或 snake_case（Python），类用 PascalCase
- **函数长度**：单个函数不超过 50 行，超过则拆分
- **注释**：公共函数必须有 docstring/JSDoc，复杂逻辑必须有行内注释
- **魔法数字**：禁止，提取为具名常量
- **错误处理**：不允许空 catch，至少记录日志
- **提交信息**：`[类型] 简短描述`，类型为 feat/fix/refactor/test/docs/chore

## 前端规范（FE）

- 组件文件：PascalCase，每文件一个组件
- Props 必须有类型声明（TypeScript 或 PropTypes）
- 禁止在组件内直接调用 API，统一通过 service 层
- CSS：使用项目约定的 CSS-in-JS 或 CSS Module，禁止内联样式（除动态值）
- 所有用户输入必须做 XSS 防护
- 每个组件必须有对应的单元测试文件（*.test.tsx）

## 后端规范（BE）

- API 响应格式统一：`{"data": ..., "code": 0, "msg": "ok"}`
- 错误码定义在 `constants/errors.py` 中，禁止硬编码
- 数据库操作必须通过 ORM，禁止拼接 SQL 字符串
- 敏感字段（密码、token）禁止出现在日志中
- 所有外部输入必须经过 Pydantic/Zod 等校验
- 每个 service 方法必须有单元测试，覆盖正向+异常路径

## 数据库规范（DBA/BE）

- 表名：复数 snake_case（users, order_items）
- 必填字段：id、created_at、updated_at
- 外键字段命名：`{table_name}_id`
- 索引命名：`idx_{table}_{field}`
- Migration 必须包含回滚脚本

## 测试规范（QA/FE/BE）

- 单元测试覆盖率目标：核心逻辑 ≥ 80%
- 测试命名：`test_[被测函数]_[场景]_[预期结果]`
- 禁止在测试中连接真实数据库，使用 mock 或测试数据库
- 每个 Bug 修复必须附带回归测试用例
