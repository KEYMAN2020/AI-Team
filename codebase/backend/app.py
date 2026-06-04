"""Flask app for BeEnjoyIng API #1: POST /api/v1/auth/send-code.

This module intentionally implements only the requested business endpoint.
A lightweight GET /health endpoint is also provided for container orchestration
and CI/CD deployment health checks.

Run locally:
    cd backend
    pip install -r requirements.txt
    python app.py
"""

from __future__ import annotations

import re
import secrets
import sys
import time
from pathlib import Path
from threading import Lock
from typing import Any

from flask import Flask, jsonify, request

# Allow importing the shared structured logger from ../references/logger.py
ROOT_DIR = Path(__file__).resolve().parent.parent
REFERENCES_DIR = ROOT_DIR / "references"
if str(REFERENCES_DIR) not in sys.path:
    sys.path.insert(0, str(REFERENCES_DIR))

from logger import init_logger  # noqa: E402

PROJECT_ID = "proj_20260602_2340"
CODE_TTL_SECONDS = 300
PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")

app = Flask(__name__)
slog = init_logger(PROJECT_ID)

# In-memory verification-code store:
# {phone: {"code": "123456", "expires_at": 1710000000.0}}
_code_store: dict[str, dict[str, Any]] = {}
_store_lock = Lock()


def make_response(code: int = 0, data: Any | None = None, message: str = "success", http_status: int = 200):
    """Return the project's unified response format."""
    return jsonify({"code": code, "data": data if data is not None else {}, "message": message}), http_status


def is_valid_chinese_phone(phone: Any) -> bool:
    """Validate mainland China mobile phone number: 1[3-9]XXXXXXXXX."""
    return isinstance(phone, str) and PHONE_PATTERN.fullmatch(phone) is not None


def generate_code() -> str:
    """Generate a cryptographically strong 6-digit verification code."""
    return f"{secrets.randbelow(1_000_000):06d}"


def purge_expired_codes(now: float | None = None) -> None:
    """Remove expired codes from memory."""
    current = now if now is not None else time.time()
    expired_phones = [phone for phone, item in _code_store.items() if item["expires_at"] <= current]
    for phone in expired_phones:
        _code_store.pop(phone, None)


@app.get("/health")
def health():
    """Health endpoint for Docker/Kubernetes/CI smoke checks."""
    return jsonify({"status": "ok"})


@app.post("/api/v1/auth/send-code")
def send_code():
    """Send a mock SMS verification code to a validated Chinese phone number."""
    payload = request.get_json(silent=True) or {}
    phone = payload.get("phone")

    if not is_valid_chinese_phone(phone):
        slog.log(
            "warn",
            event="validation_failed",
            role="backend",
            dispatch_id="API-1",
            phase="executing",
            summary="Invalid phone number for send-code",
            phone=phone,
        )
        return make_response(code=400, data={}, message="Invalid phone number", http_status=400)

    verification_code = generate_code()
    expires_at = time.time() + CODE_TTL_SECONDS

    with _store_lock:
        purge_expired_codes()
        _code_store[phone] = {"code": verification_code, "expires_at": expires_at}

    # Mock SMS provider: print the code to console as required.
    print(f"[MockSMS] phone={phone} code={verification_code} expire_in={CODE_TTL_SECONDS}", flush=True)

    slog.log(
        "info",
        event="sms_code_generated",
        role="backend",
        dispatch_id="API-1",
        phase="executing",
        summary="Mock SMS verification code generated",
        phone=phone,
        expire_in=CODE_TTL_SECONDS,
    )

    return make_response(code=0, data={"expire_in": CODE_TTL_SECONDS}, message="success")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
