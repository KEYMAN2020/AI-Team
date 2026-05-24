# 项目骨架目录（MVP）

```text
project/
├─ app/
│  ├─ __init__.py
│  ├─ config.py
│  ├─ extensions.py
│  ├─ common/
│  │  ├─ response.py          # 统一响应封装
│  │  ├─ errors.py            # 错误码与异常定义（单一来源）
│  │  ├─ auth.py              # login_required 装饰器
│  │  └─ middleware.py        # 全局错误处理/request_id
│  ├─ models/
│  │  ├─ user.py
│  │  ├─ activity.py
│  │  ├─ activity_participant.py
│  │  └─ subscription.py
│  ├─ repositories/
│  │  ├─ user_repository.py
│  │  ├─ activity_repository.py
│  │  ├─ activity_participant_repository.py
│  │  └─ subscription_repository.py
│  ├─ services/
│  │  ├─ auth_service.py
│  │  ├─ activity_service.py
│  │  └─ subscription_service.py
│  └─ controllers/
│     └─ v1/
│        ├─ auth_controller.py
│        ├─ activity_controller.py
│        └─ subscription_controller.py
├─ migrations/
├─ tests/
│  ├─ api/
│  └─ services/
├─ requirements.txt
├─ run.py
└─ README.md
```

## 关键占位文件建议
- `app/common/errors.py`：定义 0/1xxxx/2xxxx/3xxxx/5xxxx 错误码常量，禁止散落硬编码。
- `app/common/middleware.py`：统一异常映射、输出 `code/message/data`。
- `app/services/activity_service.py`：报名事务里先校验活动状态与名额，再写 participant，确保唯一约束兜底。
