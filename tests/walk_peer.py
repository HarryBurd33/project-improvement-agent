"""Synthetic provider for closed-history traversal subprocess tests."""
import json
import os
from pathlib import Path
import signal
import sys
import time


def emit(value):
    print(json.dumps(value), flush=True)


def turn(name, status="completed", completed=12):
    return {"id": name, "status": status, "startedAt": 9, "completedAt": completed,
            "items": [], "itemsView": "notLoaded", "error": {"message": "PRIVATE_ERROR"}}


def item(turn_id, name, kind="userMessage"):
    data = {"id": name, "type": kind}
    if kind == "userMessage":
        data["content"] = [{"type": "text", "text": "Exact π 🌱\n  "},
                           {"type": "localImage", "path": "PRIVATE_ATTACHMENT"}]
    else:
        data["text"] = "PRIVATE_NONUSER"
    return {"turnId": turn_id, "startedAtMs": 10, "completedAtMs": 12, "item": data}


def page(log, method, params, mode):
    if method == "thread/turns/list":
        inventory = [turn("one"), turn("two", status="interrupted"), turn("after", "inProgress", None)]
        if mode == "changed" or (mode == "final_changed" and sum(
            json.loads(row).get("method") == "thread/turns/list" for row in Path(log.name).read_text().splitlines()
        ) > 1):
            inventory[0]["completedAt"] = 20
        if mode == "missing_cutoff":
            inventory.pop()
        if mode == "long_inventory":
            inventory = [turn(f"older-{index}") for index in range(20)] + inventory
        if mode == "active":
            inventory[0]["status"] = "inProgress"
            inventory[0]["completedAt"] = None
        cursor = params.get("cursor")
        start = int(cursor.split("-")[-1]) if cursor else 0
        end = min(len(inventory), start + params["limit"])
        return inventory[start:end], f"inventory-{end}" if end < len(inventory) else None
    assert method == "thread/items/list"
    turn_id = params["turnId"]
    assert turn_id in {"one", "two"} or (mode == "long_inventory" and turn_id.startswith("older-"))
    if mode == "pending":
        time.sleep(10)
    if mode in ("batch_halve", "batch_single_overcap") and turn_id == "one" and not params.get("cursor"):
        first = item(turn_id, "one-large", "reasoning")
        if params["limit"] > 1 or mode == "batch_single_overcap":
            first["item"]["text"] += "x" * 4194304
        records = [first]
    elif mode == "fallback" and turn_id == "one" and not params.get("cursor"):
        first = item(turn_id, "one-large", "reasoning")
        first["item"]["text"] *= 18000
        records = [first]
    elif turn_id == "one" and not params.get("cursor"):
        kind = "agentMessage" if mode == "assistant" else "reasoning"
        records = [item(turn_id, "one-user"), item(turn_id, "one-other", kind)]
    elif turn_id == "one":
        records = [item(turn_id, "one-user" if mode == "item_duplicate" else "one-last")]
    else:
        records = []
    if turn_id == "one" and not params.get("cursor"):
        cursor = "one-next"
    elif mode == "cycle" and turn_id == "one":
        cursor = "one-next"
    else:
        cursor = None
    return records, cursor


def main():
    mode = os.environ["PIA_WALK_MODE"]
    with open(os.environ["PIA_WALK_LOG"], "a", encoding="utf-8", buffering=1) as log:
        log.write(json.dumps({"argv": sys.argv[1:], "pid": os.getpid()}) + "\n")
        for line in sys.stdin:
            request = json.loads(line)
            log.write(json.dumps(request) + "\n")
            method = request["method"]
            if method == "initialize":
                emit({"method": "fake/progress", "params": {"body": "PRIVATE_NOTIFICATION"}, "emittedAtMs": 1})
                emit({"id": request["id"], "result": {"userAgent": "codex-cli/0.166.0"}})
            elif method == "initialized":
                continue
            else:
                records, cursor = page(log, method, request["params"], mode)
                emit({"id": request["id"], "result": {"data": records, "nextCursor": cursor}})


if __name__ == "__main__":
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main()
