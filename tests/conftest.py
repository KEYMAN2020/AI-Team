"""
conftest.py — pytest 共享 fixtures
"""
import sys
import os
from pathlib import Path

# 确保 references/ 目录在 sys.path 中，以便测试模块能正常 import
PROJECT_ROOT = Path(__file__).resolve().parent.parent
REFERENCES_DIR = PROJECT_ROOT / "references"
if str(REFERENCES_DIR) not in sys.path:
    sys.path.insert(0, str(REFERENCES_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
