"""Temporary local helper to receive a LINE webhook and print userId/groupId/roomId."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from flask import Flask, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")


@app.get("/")
def index() -> str:
    return "LINE webhook receiver is running. Set /webhook as the LINE Webhook URL."


@app.post("/webhook")
def webhook() -> tuple[str, int]:
    payload: dict[str, Any] = request.get_json(silent=True) or {}
    print("\n=== LINE webhook received ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    for event in payload.get("events", []):
        source = event.get("source", {})
        for key in ("userId", "groupId", "roomId"):
            if source.get(key):
                print(f"\nコピーするID ({key}): {source[key]}\n")

    return "OK", 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)

