# BeEnjoyIng — 项目概述（原银发活力平台）

## 一句话
面向 40-70 岁中老年人的线下活动社交平台。

## 技术栈
| 层 | 技术 |
|---|------|
| 后端 | Python Flask |
| 数据库 | MySQL 8.0 (localhost:3306) |
| 库名 | silver_vitality（37 张表） |
| 前端 | 微信小程序 |
| 部署 | 腾讯云 CVM 上海 (124.220.16.67) |

## API 规格
- 统一响应：{code: 0, data: {...}, message: ok}
- 认证：JWT token（access_token + refresh_token）
- 登录方式：手机号 + 验证码（无密码注册）
- 路径前缀：/api/v1/

## 74 个 API（9 大模块）
认证(5) → 用户(8) → 活动(16) → 消息(7) → 队长工具(11) → 安全(5) → 通知(3) → 管理后台(12) → 通用(7)

## 开发节奏
按接口逐个开发，每个接口 push 到 dev 分支，用户 review 通过后下一个。

## 数据库
37 张表，utf8mb4，已有种子数据。核心表：users, user_auth, user_profiles, activities, activity_signups, chat_messages 等。
