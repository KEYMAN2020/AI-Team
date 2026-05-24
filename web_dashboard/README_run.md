# n8n_0524_0026 本地运行骨架

本项目首期采用 **Flask + SQLite** 单体架构，提供最小可运行后端骨架依赖与启动方式。

## 1. 准备环境

- Python 3.10+
- pip

建议使用虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

## 2. 安装依赖

```bash
pip install -r outputs/requirements.txt
```

## 3. 配置环境变量

复制模板并按需修改：

```bash
cp outputs/.env.example .env
```

重点修改：
- `SECRET_KEY`：必须改为高强度随机值
- `DATABASE_URL`：默认 SQLite，本地可直接用

## 4. 启动服务（开发模式）

```bash
bash outputs/scripts/start.sh
```

默认监听：`http://127.0.0.1:5000`

## 5. 启动服务（生产模拟）

```bash
bash outputs/scripts/start_prod.sh
```

## 6. 健康检查

根据上游约定，健康检查接口：

```bash
curl http://127.0.0.1:5000/api/v1/health
```

预期响应示例：

```json
{"code":0,"message":"ok","data":{"status":"up"}}
```

---

## 建议目录（后续补齐）

```text
app.py
outputs/
  requirements.txt
  .env.example
  scripts/
    start.sh
    start_prod.sh
```

> 说明：当前任务目标是搭建“本地可运行骨架”。若尚未有 `app.py`，请由后端补充最小 Flask 应用入口。
