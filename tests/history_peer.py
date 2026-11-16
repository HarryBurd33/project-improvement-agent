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
                if mode == "exact_mixed":
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
