# Be EnjoyIng API 规格书 v1.0

## 基础信息

- **基础URL**: `/api/v1`
- **响应格式**: `{"code": 0, "data": {...}, "message": "ok"}`
- **错误码**: 0=成功, 1001=参数错误, 1002=未授权, 1003=无权限, 1004=资源不存在, 1005=冲突, 2001=业务错误
- **认证方式**: Bearer JWT (access_token)，refresh_token 用于续期
- **日志**: 所有接口必须记录 operation_logs 表，记录 user_id、action、params、ip、user_agent、result

---

## 第一层：认证模块（Auth）

### API-01 发送验证码
- `POST /auth/send-code`
- 请求: `{"phone": "13800138000", "purpose": "login|register|reset_password"}`
- 响应: `{"expire_in": 300}`

### API-02 用户注册
- `POST /auth/register`
- 请求: `{"phone": "13800138000", "code": "123456", "password": "abc123", "nickname": "张三", "avatar_url": "..."}`
- 说明: 写 users + user_auth + user_profiles 三张表，默认 role=user

### API-03 密码登录
- `POST /auth/login`
- 请求: `{"phone": "13800138000", "password": "abc123"}`
- 响应: `{"access_token": "...", "refresh_token": "...", "expires_in": 7200}`

### API-04 验证码登录
- `POST /auth/login-code`
- 请求: `{"phone": "13800138000", "code": "123456"}`
- 响应: 同上

### API-05 刷新Token
- `POST /auth/refresh`
- 请求: `{"refresh_token": "..."}`
- 响应: `{"access_token": "...", "expires_in": 7200}`

### API-06 登出
- `POST /auth/logout`
- 请求头: `Authorization: Bearer <token>`
- 说明: 把 refresh_token 标记为已撤销

### API-07 重置密码
- `POST /auth/reset-password`
- 请求: `{"phone": "13800138000", "code": "123456", "new_password": "abc456"}`
- 说明: 更新 user_auth.password_hash

### API-08 修改密码
- `POST /auth/change-password`
- 请求头: `Authorization`
- 请求: `{"old_password": "abc123", "new_password": "abc456"}`

### API-09 实名认证
- `POST /auth/verify-identity`
- 请求头: `Authorization`
- 请求: `{"real_name": "张三", "id_number": "110101199001011234"}`
- 说明: 写 user_identities 表，实名认证后 user_profiles.verified = 1

---

## 第二层：用户模块（Users）

### API-10 获取个人信息
- `GET /users/me`
- 请求头: `Authorization`
- 说明: 联表 users + user_profiles + user_stats

### API-11 完整更新资料
- `PUT /users/me`
- 请求头: `Authorization`
- 请求: `{"nickname": "...", "gender": "M|F", "birthday": "1960-01-01", "city": "北京", "bio": "...", "avatar_url": "..."}`
- 说明: 更新 user_profiles，部分字段也在 users 表

### API-12 部分更新资料
- `PATCH /users/me`
- 请求头: `Authorization`
- 同 PUT 但只更新提供的字段

### API-13 他人公开资料
- `GET /users/{user_id}/public`
- 请求头: `Authorization`（可选）
- 说明: 只返回公开字段（nickname, avatar, gender 等，不含手机号）

### API-14 用户统计
- `GET /users/{user_id}/stats`
- 说明: 返回 user_stats 表中的统计信息

### API-15 搜索用户
- `GET /users/search?keyword=张三&page=1&size=20`
- 请求头: `Authorization`
- 说明: 按昵称搜索，分页

### API-16 上传头像
- `POST /users/upload-avatar`
- 请求头: `Authorization`
- 请求: `multipart/form-data` 含 `file` 字段
- 响应: `{"url": "..."}`

### API-17 发送好友申请
- `POST /users/friends/request`
- 请求头: `Authorization`
- 请求: `{"target_user_id": 123, "message": "..."}`
- 说明: 写 user_friends，status=pending

### API-18 处理好友申请
- `PUT /users/friends/request/{request_id}`
- 请求头: `Authorization`
- 请求: `{"action": "accept|reject"}`
- 说明: 更新 user_friends.status

### API-19 好友列表
- `GET /users/friends?page=1&size=20`
- 请求头: `Authorization`
- 说明: 只返回 status=accepted

### API-20 删除好友
- `DELETE /users/friends/{friend_id}`
- 请求头: `Authorization`

### API-21 私信列表
- `GET /users/messages?page=1&size=20`
- 请求头: `Authorization`
- 说明: 读取 user_private_messages，按会话聚合

### API-22 发送私信
- `POST /users/messages`
- 请求头: `Authorization`
- 请求: `{"receiver_id": 123, "content": "..."}`
- 说明: 写 user_private_messages

### API-23 举报用户
- `POST /users/{user_id}/report`
- 请求头: `Authorization`
- 请求: `{"reason": "...", "description": "..."}`
- 说明: 写 operation_logs 标记举报

---

## 第三层：活动模块（Activities）

### API-24 创建活动
- `POST /activities`
- 请求头: `Authorization`（需 captain 或 admin）
- 请求: `{"title": "...", "category_id": 1, "description": "...", "start_time": "2026-06-15T09:00:00", "end_time": "...", "location": "...", "max_participants": 50, "fee": 0.00, "images": [...]}`
- 说明: 写 activities 表，同时可以写 activity_tag_refs

### API-25 活动列表
- `GET /activities?category_id=1&city=北京&page=1&size=20&status=upcoming`
- 说明: status 取值 upcoming|ongoing|completed|cancelled

### API-26 活动详情
- `GET /activities/{id}`

### API-27 更新活动
- `PUT /activities/{id}`
- 请求头: `Authorization`（创建者或 admin）

### API-28 删除活动
- `DELETE /activities/{id}`
- 请求头: `Authorization`

### API-29 活动分类列表
- `GET /activities/categories`
- 说明: 读取 activity_categories

### API-30 报名活动
- `POST /activities/{id}/signup`
- 请求头: `Authorization`
- 说明: 写 activity_signups，status=confirmed

### API-31 取消报名
- `POST /activities/{id}/cancel-signup`
- 请求头: `Authorization`
- 说明: activity_signups.status=cancelled

### API-32 报名列表
- `GET /activities/{id}/signups?page=1&size=20`
- 请求头: `Authorization`

### API-33 签到
- `POST /activities/{id}/checkin`
- 请求头: `Authorization`
- 说明: 写 activity_checkins

### API-34 收藏/取消收藏
- `POST /activities/{id}/favorite`
- 请求头: `Authorization`
- 说明: toggle — 存在则删除，不存在则插入 activity_favorites

### API-35 评分
- `POST /activities/{id}/rate`
- 请求头: `Authorization`
- 请求: `{"score": 4.5}`
- 说明: 写 activity_ratings

### API-36 评价
- `POST /activities/{id}/review`
- 请求头: `Authorization`
- 请求: `{"content": "...", "images": [...]}`
- 说明: 写 activity_reviews

### API-37 评价列表
- `GET /activities/{id}/reviews?page=1&size=20`

### API-38 举报活动
- `POST /activities/{id}/report`
- 请求头: `Authorization`
- 请求: `{"reason": "...", "description": "..."}`

### API-39 加入候补
- `POST /activities/{id}/waitlist`
- 请求头: `Authorization`
- 说明: 写 activity_waitlist

### API-40 活动相册
- `GET /activities/{id}/albums`
- 说明: 读取 activity_albums

### API-41 上传照片到相册
- `POST /activities/{id}/albums`
- 请求头: `Authorization`
- 请求: `multipart/form-data`

### API-42 删除照片
- `DELETE /activities/{id}/albums/{album_id}`
- 请求头: `Authorization`

### API-43 活动标签
- `GET /activities/tags`
- 说明: 读取 activity_tags

### API-44 附近活动
- `GET /activities/nearby?lat=39.9042&lng=116.4074&radius=5000`
- 说明: 按地理位置搜索

### API-45 我的活动
- `GET /activities/my?status=upcoming&page=1&size=20`
- 请求头: `Authorization`
- 说明: 当前用户报名的活动

### API-46 历史活动
- `GET /activities/history?page=1&size=20`
- 请求头: `Authorization`

### API-47 推荐活动
- `GET /activities/recommended?page=1&size=10`
- 说明: 基于用户偏好推荐

---

## 第四层：聊天模块（Chat）

### API-48 创建群聊
- `POST /chat/groups`
- 请求头: `Authorization`
- 请求: `{"name": "...", "activity_id": null}`
- 说明: 写 chat_groups + chat_group_members

### API-49 群聊列表
- `GET /chat/groups?page=1&size=20`
- 请求头: `Authorization`

### API-50 加入群聊
- `POST /chat/groups/{id}/join`
- 请求头: `Authorization`

### API-51 退出群聊
- `POST /chat/groups/{id}/leave`
- 请求头: `Authorization`

### API-52 聊天记录
- `GET /chat/groups/{id}/messages?page=1&size=50`
- 请求头: `Authorization`
- 说明: 读取 chat_messages

### API-53 发送消息
- `POST /chat/groups/{id}/messages`
- 请求头: `Authorization`
- 请求: `{"content": "...", "msg_type": "text|image|system"}`

---

## 第五层：领队模块（Captain）

### API-54 申请领队
- `POST /captain/apply`
- 请求头: `Authorization`
- 请求: `{"real_name": "...", "id_number": "...", "experience": "...", "certificates": [...]}`
- 说明: 写 captain_applications

### API-55 申请列表（管理）
- `GET /captain/applications?status=pending&page=1&size=20`
- 请求头: `Authorization`（admin）

### API-56 审核申请
- `PUT /captain/applications/{id}/review`
- 请求头: `Authorization`（admin）
- 请求: `{"status": "approved|rejected", "remark": "..."}`
- 说明: 通过后写 captain_profiles

### API-57 领队列表
- `GET /captain/profiles?page=1&size=20`

### API-58 领队详情
- `GET /captain/profiles/{id}`

### API-59 培训记录
- `POST /captain/training`
- 请求头: `Authorization`（admin）
- 请求: `{"captain_id": 1, "training_date": "...", "content": "...", "result": "pass|fail"}`
- 说明: 写 captain_training

---

## 第六层：合作伙伴模块（Partner）

### API-60 注册合作伙伴
- `POST /partners`
- 请求头: `Authorization`（admin）
- 请求: `{"name": "...", "contact": "...", "phone": "...", "type": "venue|sponsor|media"}`
- 说明: 写 partner_profiles

### API-61 合作伙伴列表
- `GET /partners?type=venue&page=1&size=20`

### API-62 更新合作伙伴
- `PUT /partners/{id}`
- 请求头: `Authorization`（admin）

### API-63 合作街道列表
- `GET /partners/streets?city=北京`
- 说明: 读取 partner_streets

---

## 第七层：支付与订阅（Payment）

### API-64 创建支付
- `POST /payments`
- 请求头: `Authorization`
- 请求: `{"order_type": "activity_fee|subscription|insurance", "order_id": 1, "amount": 99.00, "payment_method": "wechat|alipay"}`
- 说明: 写 payment_records

### API-65 支付记录
- `GET /payments?page=1&size=20`
- 请求头: `Authorization`

### API-66 支付详情
- `GET /payments/{id}`
- 请求头: `Authorization`

### API-67 开通会员
- `POST /subscriptions`
- 请求头: `Authorization`
- 请求: `{"plan": "monthly|quarterly|yearly", "payment_id": 1}`
- 说明: 写 premium_subscriptions

### API-68 会员状态
- `GET /subscriptions/status`
- 请求头: `Authorization`
- 说明: 返回当前会员等级、过期时间

### API-69 投保
- `POST /insurance`
- 请求头: `Authorization`
- 请求: `{"activity_id": 1, "policy_type": "accident"}`
- 说明: 写 insurance_records

### API-70 保险记录
- `GET /insurance/records?page=1&size=20`
- 请求头: `Authorization`

---

## 第八层：健康与通知（Health & Notification）

### API-71 健康申报
- `POST /health/declare`
- 请求头: `Authorization`
- 请求: `{"temperature": 36.5, "symptoms": [], "has_contact_risk": false}`
- 说明: 写 health_declarations

### API-72 健康记录
- `GET /health/declarations?page=1&size=20`
- 请求头: `Authorization`

### API-73 通知列表
- `GET /notifications?page=1&size=20`
- 请求头: `Authorization`
- 说明: 读取 notifications

### API-74 标记已读
- `PUT /notifications/{id}/read`
- 请求头: `Authorization`

### API-75 全部已读
- `PUT /notifications/read-all`
- 请求头: `Authorization`

---

## 第九层：系统与配置（System）

### API-76 系统配置
- `GET /system/config?keys=site_name,contact_phone`
- 说明: 读取 system_config，公开配置

### API-77 地区数据
- `GET /regions?parent_id=0`
- 说明: 读取 regions，按层级查省/市/区

---

## 附录：通用规则

1. **日志**：每个接口写 operation_logs 表，字段：user_id, action（模块+接口名）, params（请求参数JSON）, ip, user_agent, result（success/fail）, created_at
2. **分页**：请求参数 page（默认1）, size（默认20），响应加 `{"total": N, "page": P, "size": S, "items": [...]}`
3. **认证**：需要登录的接口统一用 `@jwt_required()` 装饰器，从 access_token 解码 user_id
4. **文件上传**：图片上传返回 URL，存储路径 `/uploads/{module}/{date}/{filename}`
5. **软删除**：所有 DELETE 接口做软删除（设置 deleted_at 时间戳），不物理删除
6. **代码结构**：每个模块一个 Blueprint 文件（如 auth_routes.py, activity_routes.py），在 app.py 中注册
