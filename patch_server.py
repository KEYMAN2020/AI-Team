"""Patch server.py to add clean state functionality."""
with open("/opt/ai-team/server.py", "r") as f:
    content = f.read()

# Change 1: Add clean param to _handle_run
content = content.replace(
    'webhook_url = data.get("webhook_url")',
    'webhook_url = data.get("webhook_url")\n        clean = data.get("clean", False)  # \xe2\x86\x90 \xe6\x96\xb0\xe5\xa2\x9e\xef\xbc\x9a\xe5\xbc\xba\xe5\x88\xb6\xe6\xb8\x85\xe7\x90\x86\xe6\x97\xa7\xe7\x8a\xb6\xe6\x80\x81'
)

# Change 2: Pass clean to thread
content = content.replace(
    'args=(task_id, task_desc, project_name, provider, webhook_url),',
    'args=(task_id, task_desc, project_name, provider, webhook_url, clean),'
)

# Change 3: Update function signature
old_sig = "def _run_async_task(task_id: str, task_desc: str, project_name: str,\n                    provider: str | None, webhook_url: str | None):"
new_sig = "def _run_async_task(task_id: str, task_desc: str, project_name: str,\n                    provider: str | None, webhook_url: str | None,\n                    clean: bool = False):"
content = content.replace(old_sig, new_sig)

# Change 4: Add cleanup block before resume detection
old_checkpoint = "        # \xe6\x96\xad\xe7\x82\xb9\xe7\xbb\xad\xe8\xb7\x91\xe6\xa3\x80\xe6\xb5\x8b\xef\xbc\x9a\xe5\xa6\x82\xe6\x9e\x9c master.json \xe5\xad\x98\xe5\x9c\xa8\xe4\xb8\x94\xe9\xa1\xb9\xe7\x9b\xae\xe6\x9c\xaa\xe5\xae\x8c\xe6\x88\x90\xef\xbc\x8c\xe7\x9b\xb4\xe6\x8e\xa5\xe6\x81\xa2\xe5\xa4\x8d\n        if MASTER_PATH.exists():"

cleanup_block = """
        # \xe2\x94\x80\xe2\x94\x80 \xe6\xb8\x85\xe7\x90\x86\xe6\x97\xa7\xe7\x8a\xb6\xe6\x80\x81\xef\xbc\x88clean=True \xe6\x97\xb6\xef\xbc\x89 \xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80\xe2\x94\x80
        if MASTER_PATH.exists() and clean:
            import shutil
            state_dir = MASTER_PATH.parent
            print(f"\U0001f9f9 clean=True\uff0c\u6e05\u7406\u65e7\u72b6\u6001\uff1a{state_dir}")
            for d in [state_dir / "snapshots", state_dir / "summaries"]:
                if d.exists():
                    shutil.rmtree(d)
                    print(f"  \u2713 \u5220\u9664\u4e86 {d}")
            for f in state_dir.glob("_*.json"):
                f.unlink()
            for fn in ["messages.jsonl"]:
                fp = state_dir / fn
                if fp.exists():
                    fp.unlink()
            if MASTER_PATH.exists():
                MASTER_PATH.unlink()
                print(f"  \u2713 \u5220\u9664\u4e86 master.json\uff0c\u4e0b\u6b21\u5c06\u4ece\u5934\u5f00\u59cb")
            outputs_dir = Path("/app/outputs")
            if outputs_dir.exists():
                for f in outputs_dir.iterdir():
                    if f.is_file():
                        f.unlink()
                    elif f.is_dir():
                        shutil.rmtree(f)
                print(f"  \u2713 \u6e05\u7406\u4e86 outputs/")
            print(f"  \u2713 \u72b6\u6001\u6e05\u7406\u5b8c\u6210")

        # \u65ad\u70b9\u7eed\u8dd1\u68c0\u6d4b\uff1a\u5982\u679c master.json \u5b58\u5728\u4e14\u9879\u76ee\u672a\u5b8c\u6210\uff0c\u76f4\u63a5\u6062\u590d
        if MASTER_PATH.exists():"""

content = content.replace(old_checkpoint, cleanup_block)

# Also need to add Path import if it's not there
if "from pathlib import Path" not in content:
    content = content.replace(
        "import shutil",
        "from pathlib import Path\nimport shutil"
    )

with open("/opt/ai-team/server.py", "w") as f:
    f.write(content)

print("server.py patched successfully")
print(f"Total lines: {len(content.splitlines())}")
