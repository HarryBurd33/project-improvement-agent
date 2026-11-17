"""Deterministic stdio peer for the selected-history subprocess tests."""
import json
import os
import signal
import sys
import time


def emit(value):
    print(json.dumps(value), flush=True)


def entry(identity, kind="userMessage", turn="fake-turn"):
    item = {"id": identity, "type": kind}
    if kind == "userMessage":
        item["content"] = [{"type": "text", "text": "Exact user text\nπ\t  "},
                           {"type": "localImage", "path": "PRIVATE_USER_ATTACHMENT"}]
    else:
        item["text"] = "PRIVATE_NONUSER_PAYLOAD"
        item["arguments"] = {"instruction": "PRIVATE_NONUSER_PAYLOAD"}
    return {"turnId": turn, "startedAtMs": 10, "item": item}


def assistant_rows(mode):
    selected = entry("selected-answer", "agentMessage")
    selected["completedAtMs"] = 23
    item = selected["item"]
    item["text"] = "Exact selected reply π 🌱\n  "
    item["phase"] = "final_answer"
    if mode == "assistant_commentary":
        item["phase"] = "commentary"
    elif mode == "assistant_partial":
        item["phase"] = "partial_answer"
    elif mode == "assistant_phase_omitted":
        del item["phase"]
    elif mode == "assistant_phase_null":
        item["phase"] = None
        item["text"] = ""
    elif mode == "assistant_wrong_type":
        item["type"] = "reasoning"
    elif mode == "assistant_bad_phase":
        item["phase"] = {"body": "PRIVATE_PHASE"}
    elif mode == "assistant_bad_text":
        item["text"] = ["PRIVATE_BAD_TEXT"]
    elif mode == "assistant_wrong_turn":
        selected["turnId"] = "other-turn"
    rows = [entry("user"), selected, entry("other-answer", "agentMessage"),
            entry("analysis", "reasoning"), entry("tool", "functionCallOutput")]
    if mode == "assistant_missing":
        rows.remove(selected)
    elif mode == "assistant_duplicate":
        rows[2] = selected
    elif mode == "assistant_bad_neighbor":
        rows[-1]["completedAtMs"] = "PRIVATE_BAD_NEIGHBOR"
    return rows


def main():
    mode = os.environ["PIA_TEST_SCENARIO"]
    with open(os.environ["PIA_TEST_TRANSCRIPT"], "a", encoding="utf-8") as log:
        log.write(json.dumps({"argv": sys.argv[1:], "pid": os.getpid()}) + "\n")
        log.flush()
        for raw in sys.stdin:
            request = json.loads(raw)
            log.write(json.dumps(request) + "\n")
            log.flush()
            req_id = request.get("id")
            if request["method"] == "initialize":
                if mode.startswith("assistant_") or mode in ("exact_mixed", "large_user", "large_batch"):
                    os.write(sys.stderr.fileno(), b"PRIVATE_STDERR" * 3)
                emit({"method": "remoteControl/status/changed", "params": {"body": "PRIVATE_NOTIFICATION"},
                      "emittedAtMs": 10})
                emit({"id": req_id, "result": {"userAgent": "codex-cli/0.166.0", "private": "PRIVATE_INITIALIZE"}})
                continue
            if request["method"] == "initialized":
                continue
            if mode == "ignore_term":
                signal.signal(signal.SIGTERM, signal.SIG_IGN)
                time.sleep(10)
            if mode == "timeout":
                time.sleep(10)
            if mode == "exit":
                return
            if mode == "truncated":
                print('{"id":', end="", flush=True)
                return
            if mode == "rpc":
                emit({"id": req_id, "error": {"code": -1, "message": "PRIVATE_RPC_ERROR", "data": ["PRIVATE_RPC_ERROR"]}})
                continue
            if mode == "server_request":
                emit({"id": 7, "method": "item/commandExecution/requestApproval", "params": {"body": "PRIVATE_APPROVAL"}})
                continue
            if mode == "wrong_id":
                req_id += 10
            if mode == "bad_json":
                print('not json PRIVATE_MALFORMED', flush=True)
                continue
            if mode == "stderr_limit" or (mode == "mixed_limit" and req_id == 3):
                os.write(sys.stderr.fileno(), b"PRIVATE_STDERR" * 1000)
                emit({"method": "irrelevant/progress", "params": {"body": "PRIVATE_NOTIFICATION" * 600}})
            if mode == "notification_limit":
                emit({"method": "irrelevant/progress", "params": {"body": "PRIVATE_NOTIFICATION" * 600}})
            if request["method"] == "thread/turns/list":
                data = [{"id": "fake-turn", "status": "completed", "items": [],
                         "error": {"message": "PRIVATE_TURN_ERROR"}, "startedAt": 8}]
                if mode == "turn_view_full":
                    data[0]["itemsView"] = "full"
                elif mode == "turn_view_summary":
                    data[0]["itemsView"] = "summary"
                elif mode == "turn_view_explicit":
                    data[0]["itemsView"] = "notLoaded"
                emit({"id": req_id, "result": {"data": data, "nextCursor": None}})
                continue
            if mode.startswith("assistant_"):
                emit({"id": req_id, "result": {"data": assistant_rows(mode), "nextCursor": "assistant-next",
                                               "unrecognized": {"body": "PRIVATE_RESULT"}}})
                continue
            if mode in ("large_batch", "large_batch_repeat"):
                user = entry("batch-user")
                user["item"]["content"][0]["text"] = "Exact batch π 🌱\n  " * 9000
                other = entry("batch-other", "reasoning")
                other["item"]["text"] *= 9000
                cursor = request["params"]["cursor"] if mode == "large_batch_repeat" else "batch-next"
                emit({"id": req_id, "result": {"data": [user, other], "nextCursor": cursor}})
                continue
            if mode in ("large_user", "large_nonuser", "large_overcap"):
                if mode == "large_user":
                    row = entry("large-user")
                    row["item"]["content"][0]["text"] = "Exact selected π 🌱\n  " * 12000
                    row["completedAtMs"] = 42
                else:
                    row = entry("large-other", "reasoning")
                    if mode == "large_overcap":
                        row["item"]["text"] += "x" * (4 * 1024 * 1024)
                    else:
                        row["item"]["text"] *= 18000
                emit({"id": req_id, "result": {"data": [row], "nextCursor": "opaque#1 ?\t"}})
                continue
            if mode == "missing_cursor":
                emit({"id": req_id, "result": {"data": [entry("first")]}})
                continue
            if mode == "empty":
                data, cursor = [], None
            elif mode == "empty_cursor":
                data, cursor = [], "do-not-adopt"
            elif mode == "wrong_turn":
                data, cursor = [entry("wrong", turn="some-other-turn")], "do-not-adopt"
            elif mode == "bad_cursor":
                data, cursor = [entry("wrong")], {"a": 2}
            elif mode == "overreturn":
                data, cursor = [entry("first"), entry("second"), entry("third")], "do-not-adopt"
            elif req_id == 2:
                data, cursor = [entry("first"), entry("proof", "reasoning")], "opaque#1 ?\t"
            elif mode == "repeat":
                data, cursor = [entry("second")], request["params"]["cursor"]
            elif mode == "dup_record":
                data, cursor = [entry("first")], "do-not-adopt"
            else:
                data, cursor = [entry("second")], None
            emit({"id": req_id, "result": {"data": data, "nextCursor": cursor, "backwardsCursor": None}})


if __name__ == "__main__":
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    main()
