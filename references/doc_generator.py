"""
doc_generator.py — 接口文档生成器
====================================
从 ARCH 的接口定义 + BE 的实现代码，自动生成：
  1. OpenAPI 3.0 规范（YAML）
  2. Markdown 可读文档
  3. Postman Collection（可直接导入测试）

触发时机：
  - BE 完成实现后调用 update_api_doc() 更新规范
  - ARCH 初次调用 init_api_doc() 生成基础规范框架
  - QA 可直接使用生成的 Postman Collection 进行接口测试

输出路径：
  outputs/api/
  ├── openapi.yaml      OpenAPI 3.0 规范
  ├── api_docs.md       Markdown 文档（人类可读）
  └── postman.json      Postman Collection
"""

import json
import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

API_OUTPUT_DIR = Path("outputs/api")


# ── 初始化（ARCH 调用）──────────────────────────

def init_api_doc(project_name: str, version: str = "1.0.0",
                 description: str = "", base_url: str = "http://localhost:8000") -> str:
    """
    ARCH 在完成接口设计后调用，生成 OpenAPI 框架。
    输出：outputs/api/openapi.yaml
    """
    API_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": project_name,
            "version": version,
            "description": description or f"{project_name} API 文档",
            "contact": {"name": "AI Dev Team"},
            "x-generated-at": datetime.now().isoformat(),
        },
        "servers": [
            {"url": base_url, "description": "开发环境"},
            {"url": base_url.replace("localhost", "api.staging"), "description": "测试环境"},
        ],
        "paths": {},
        "components": {
            "schemas": {},
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            },
        },
        "security": [{"BearerAuth": []}],
        "tags": [],
    }

    yaml_path = API_OUTPUT_DIR / "openapi.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(spec, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print(f"✅ OpenAPI 框架已初始化：{yaml_path}")
    return str(yaml_path)


def add_endpoint(method: str, path: str, summary: str,
                 tag: str, request_body: Optional[dict] = None,
                 responses: Optional[dict] = None,
                 parameters: Optional[list] = None,
                 requires_auth: bool = True) -> None:
    """
    ARCH 或 BE 添加一个接口定义到 OpenAPI 规范。

    用法示例：
    add_endpoint(
        method="POST", path="/api/v1/users/login",
        summary="用户登录",
        tag="用户认证",
        request_body={
            "email": {"type": "string", "example": "user@example.com"},
            "password": {"type": "string", "example": "••••••••"},
        },
        responses={
            "200": {"token": "JWT token", "user": {"id": 1, "name": "张三"}},
            "401": {"code": 20001, "msg": "密码错误"},
        },
        requires_auth=False,
    )
    """
    yaml_path = API_OUTPUT_DIR / "openapi.yaml"
    if not yaml_path.exists():
        print("⚠️ 请先调用 init_api_doc() 初始化")
        return

    with open(yaml_path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    # 构建 operation
    operation = {
        "summary": summary,
        "tags": [tag],
        "operationId": _to_operation_id(method, path),
    }
    if not requires_auth:
        operation["security"] = []

    if parameters:
        operation["parameters"] = parameters

    if request_body:
        operation["requestBody"] = {
            "required": True,
            "content": {
                "application/json": {
                    "schema": _dict_to_schema(request_body)
                }
            }
        }

    # 构建响应
    operation["responses"] = {}
    for status_code, resp_data in (responses or {"200": {"msg": "ok"}}).items():
        operation["responses"][str(status_code)] = {
            "description": _status_desc(str(status_code)),
            "content": {
                "application/json": {
                    "schema": _dict_to_schema(resp_data),
                    "example": resp_data,
                }
            }
        }

    # 写入 paths
    if path not in spec["paths"]:
        spec["paths"][path] = {}
    spec["paths"][path][method.lower()] = operation

    # 添加 tag
    if tag not in [t.get("name") for t in spec.get("tags", [])]:
        spec.setdefault("tags", []).append({"name": tag})

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(spec, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    print(f"✅ 接口已记录：{method.upper()} {path}")


# ── 文档生成（完成实现后调用）──────────────────

def generate_markdown_docs() -> str:
    """
    从 openapi.yaml 生成 Markdown 格式的接口文档。
    输出：outputs/api/api_docs.md
    """
    yaml_path = API_OUTPUT_DIR / "openapi.yaml"
    if not yaml_path.exists():
        return "❌ openapi.yaml 不存在，请先调用 init_api_doc()"

    with open(yaml_path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    info = spec.get("info", {})
    lines = [
        f"# {info.get('title', '项目')} 接口文档",
        f"\n> 版本：{info.get('version', '1.0.0')} | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"\n{info.get('description', '')}",
        "\n---\n",
        "## 目录\n",
    ]

    # 按 tag 分组
    paths = spec.get("paths", {})
    tag_groups: dict[str, list] = {}

    for path, methods in paths.items():
        for method, op in methods.items():
            tag = op.get("tags", ["其他"])[0]
            tag_groups.setdefault(tag, []).append((method.upper(), path, op))

    # 目录
    for tag in tag_groups:
        anchor = tag.replace(" ", "-").lower()
        lines.append(f"- [{tag}](#{anchor})")
    lines.append("\n---\n")

    # 鉴权说明
    lines.extend([
        "## 鉴权说明\n",
        "除标注「无需鉴权」的接口外，所有接口需在 Header 携带 JWT Token：\n",
        "```\nAuthorization: Bearer <token>\n```\n",
        "---\n",
    ])

    # 接口详情
    for tag, endpoints in tag_groups.items():
        lines.append(f"## {tag}\n")
        for method, path, op in endpoints:
            lines.append(f"### {method} `{path}`\n")
            lines.append(f"**{op.get('summary', '')}**\n")

            auth_note = "（无需鉴权）" if op.get("security") == [] else ""
            if auth_note:
                lines.append(f"> {auth_note}\n")

            # 路径/查询参数
            params = op.get("parameters", [])
            if params:
                lines.append("**参数**\n")
                lines.append("| 名称 | 位置 | 类型 | 必须 | 说明 |")
                lines.append("|------|------|------|------|------|")
                for p in params:
                    required = "✓" if p.get("required") else ""
                    ptype = p.get("schema", {}).get("type", "string")
                    lines.append(f"| {p.get('name')} | {p.get('in')} | {ptype} | {required} | {p.get('description','')} |")
                lines.append("")

            # 请求体
            req_body = op.get("requestBody", {})
            if req_body:
                schema = req_body.get("content", {}).get("application/json", {}).get("schema", {})
                lines.append("**请求体**\n")
                lines.append("```json")
                lines.append(json.dumps(_schema_to_example(schema), ensure_ascii=False, indent=2))
                lines.append("```\n")

            # 响应
            lines.append("**响应**\n")
            for status, resp in op.get("responses", {}).items():
                example = resp.get("content", {}).get("application/json", {}).get("example", {})
                lines.append(f"**{status} {_status_desc(status)}**")
                lines.append("```json")
                lines.append(json.dumps(example, ensure_ascii=False, indent=2))
                lines.append("```\n")

            lines.append("---\n")

    content = "\n".join(lines)
    out_path = API_OUTPUT_DIR / "api_docs.md"
    out_path.write_text(content, encoding="utf-8")
    print(f"✅ Markdown 文档已生成：{out_path}")
    return str(out_path)


def generate_postman_collection() -> str:
    """
    从 openapi.yaml 生成 Postman Collection。
    输出：outputs/api/postman.json
    """
    yaml_path = API_OUTPUT_DIR / "openapi.yaml"
    if not yaml_path.exists():
        return "❌ openapi.yaml 不存在"

    with open(yaml_path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    info = spec.get("info", {})
    server = spec.get("servers", [{"url": "http://localhost:8000"}])[0]["url"]

    collection = {
        "info": {
            "name": info.get("title", "API Collection"),
            "description": info.get("description", ""),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": "base_url", "value": server},
            {"key": "token", "value": "YOUR_JWT_TOKEN_HERE"},
        ],
        "auth": {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{token}}", "type": "string"}],
        },
        "item": [],
    }

    # 按 tag 分组
    tag_groups: dict[str, list] = {}
    for path, methods in spec.get("paths", {}).items():
        for method, op in methods.items():
            tag = op.get("tags", ["其他"])[0]
            tag_groups.setdefault(tag, []).append((method.upper(), path, op))

    for tag, endpoints in tag_groups.items():
        folder = {"name": tag, "item": []}
        for method, path, op in endpoints:
            req_body = op.get("requestBody", {})
            example = req_body.get("content", {}).get("application/json", {}).get("schema", {})

            item = {
                "name": op.get("summary", f"{method} {path}"),
                "request": {
                    "method": method,
                    "url": {
                        "raw": f"{{{{base_url}}}}{path}",
                        "host": ["{{base_url}}"],
                        "path": [p for p in path.split("/") if p],
                    },
                    "header": [{"key": "Content-Type", "value": "application/json"}],
                },
            }

            if req_body:
                item["request"]["body"] = {
                    "mode": "raw",
                    "raw": json.dumps(_schema_to_example(example), ensure_ascii=False, indent=2),
                    "options": {"raw": {"language": "json"}},
                }

            # 无需鉴权的接口取消 token
            if op.get("security") == []:
                item["request"]["auth"] = {"type": "noauth"}

            folder["item"].append(item)
        collection["item"].append(folder)

    out_path = API_OUTPUT_DIR / "postman.json"
    out_path.write_text(json.dumps(collection, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ Postman Collection 已生成：{out_path}")
    return str(out_path)


def generate_all_docs() -> dict:
    """一键生成所有接口文档。"""
    results = {
        "openapi":  str(API_OUTPUT_DIR / "openapi.yaml"),
        "markdown": generate_markdown_docs(),
        "postman":  generate_postman_collection(),
    }
    print(f"\n📚 接口文档全部生成完成：\n" + "\n".join(f"  {k}: {v}" for k, v in results.items()))
    return results


# ── 辅助函数 ─────────────────────────────────────

def _to_operation_id(method: str, path: str) -> str:
    parts = [p for p in path.split("/") if p and not p.startswith("{")]
    return method.lower() + "".join(p.capitalize() for p in parts)

def _dict_to_schema(d: dict) -> dict:
    if not isinstance(d, dict):
        return {"type": "string"}
    properties = {}
    for k, v in d.items():
        if isinstance(v, dict):
            properties[k] = _dict_to_schema(v)
        elif isinstance(v, str):
            properties[k] = {"type": "string", "example": v}
        elif isinstance(v, int):
            properties[k] = {"type": "integer", "example": v}
        elif isinstance(v, bool):
            properties[k] = {"type": "boolean", "example": v}
        elif isinstance(v, list):
            properties[k] = {"type": "array", "items": {"type": "object"}}
        else:
            properties[k] = {"type": "string"}
    return {"type": "object", "properties": properties}

def _schema_to_example(schema: dict) -> dict:
    if not schema or not isinstance(schema, dict):
        return {}
    result = {}
    for k, v in schema.get("properties", {}).items():
        if "example" in v:
            result[k] = v["example"]
        elif v.get("type") == "string":
            result[k] = "string"
        elif v.get("type") == "integer":
            result[k] = 0
        elif v.get("type") == "boolean":
            result[k] = True
        elif v.get("type") == "object":
            result[k] = {}
        elif v.get("type") == "array":
            result[k] = []
    return result

def _status_desc(code: str) -> str:
    return {
        "200": "成功", "201": "创建成功", "204": "无内容",
        "400": "参数错误", "401": "未认证", "403": "无权限",
        "404": "资源不存在", "409": "冲突", "422": "校验失败",
        "500": "服务器错误",
    }.get(code, "")


# ── CLI ──────────────────────────────────────────

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"

    if cmd == "init":
        name = sys.argv[2] if len(sys.argv) > 2 else "My API"
        init_api_doc(name)
    elif cmd == "generate":
        generate_all_docs()
    elif cmd == "markdown":
        print(generate_markdown_docs())
    elif cmd == "postman":
        print(generate_postman_collection())
    else:
        print("""
接口文档生成器
  python doc_generator.py init "项目名"    初始化 OpenAPI 框架
  python doc_generator.py generate         生成所有文档（Markdown + Postman）
  python doc_generator.py markdown         只生成 Markdown
  python doc_generator.py postman          只生成 Postman Collection
""")
