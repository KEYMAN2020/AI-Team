"""Submit API task to ai-team with clean=True (force clean old state)"""
import json
import urllib.request

task = {
    "task": (
        "Implement API for BeEnjoyIng.\n\n"
        "Requirements:\n"
        "- Python Flask, unified response format {code, data, message}\n"
        "- Use references/logger.py for structured logging\n"
        "- Put code in backend/ directory\n"
        "- Only the specified API, do not over-generate"
    ),
    "provider": "any",
    "project_name": "BeEnjoyIng-API",
    "clean": True
}

req = urllib.request.Request(
    "http://localhost:8123/run",
    data=json.dumps(task).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
resp = urllib.request.urlopen(req)
result = json.loads(resp.read())
print(json.dumps(result, indent=2, ensure_ascii=False))
