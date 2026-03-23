# # conftest.py
# import os
# import time
# import pytest
# import requests
# import sys
#
# def pytest_addoption(parser):
#     group = parser.getgroup("slack")
#     group.addoption(
#         "--slack-webhook",
#         action="store",
#         default=os.getenv("SLACK_WEBHOOK", ""),
#         help="Slack incoming webhook URL",
#     )
#     group.addoption(
#         "--slack-test",
#         action="store_true",
#         help="Send a quick Slack test message and exit."
#     )
#
# def pytest_configure(config):
#     webhook = config.getoption("--slack-webhook") or os.getenv("SLACK_WEBHOOK", "")
#     config._slack = {
#         "webhook": webhook,
#         "t0": time.time(),
#         "counts": {"passed": 0, "failed": 0, "error": 0, "skipped": 0, "xfailed": 0, "xpassed": 0},
#     }
#     # conftest 로드/웹후크 상태 로그
#     print(f"[SLACK] conftest loaded from {__file__}")
#     print(f"[SLACK] webhook: {'SET' if webhook else 'MISSING'}")
#
# def pytest_cmdline_main(config):
#     if config.getoption("--slack-test"):
#         url = config._slack["webhook"]
#         if not url:
#             pytest.exit("[SLACK] No webhook provided (--slack-webhook or SLACK_WEBHOOK)", returncode=2)
#         r = requests.post(url, json={"text": "✅ Pytest Slack quick test: it works!"}, timeout=5)
#         r.raise_for_status()
#         print("[SLACK] Sent test message.")
#         return 0
#
# def pytest_runtest_logreport(report):
#     # 결과 카운트(터미널리포터 의존 X)
#     cfg = report.config
#     counts = cfg._slack["counts"]
#     # xfail/xpass 처리
#     if hasattr(report, "wasxfail"):
#         if report.skipped:
#             counts["xfailed"] += 1
#         elif report.passed:
#             counts["xpassed"] += 1
#
#     if report.when == "call":
#         if report.passed:
#             counts["passed"] += 1
#         elif report.failed:
#             counts["failed"] += 1
#         elif report.skipped:
#             counts["skipped"] += 1
#     elif report.failed and report.when in ("setup", "teardown"):
#         counts["error"] += 1
#
# def pytest_sessionfinish(session, exitstatus):
#     cfg = session.config
#     url = cfg._slack["webhook"]
#     duration = time.time() - cfg._slack["t0"]
#     counts = cfg._slack["counts"]
#     total = session.testscollected or sum(counts.values())
#
#     print(f"[SLACK] exitstatus={exitstatus} (0=all passed)")
#     print(f"[SLACK] counts={counts}, total={total}, duration={duration:.1f}s")
#     if not url:
#         print("[SLACK] skip send: webhook missing")
#         return
#
#     # 전체 성공일 때만 전송
#     all_green = (exitstatus == 0)
#     if not all_green:
#         print("[SLACK] skip send: not all tests passed")
#         return
#
#     target = " ".join(getattr(cfg, "args", []) or [])
#     text = (
#         f"✅ Pytest 성공{f' ({target})' if target else ''}\n"
#         f"• Passed: {counts['passed']}/{total}\n"
#         f"• Duration: {duration:.1f}s"
#     )
#     try:
#         r = requests.post(url, json={"text": text}, timeout=8)
#         r.raise_for_status()
#         print("[SLACK] Sent success summary.")
#     except Exception as e:
#         print(f"[SLACK] send failed: {e}")
#
#
# print("[SLACK] webhook:", "SET" if os.getenv("SLACK_WEBHOOK_URL") else "MISSING")



# conftest.py
import os, time, json
from datetime import datetime

try:
    import requests
except ImportError:
    requests = None

WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")

def _post_to_slack(text: str):
    if not WEBHOOK:
        print("[SLACK] webhook MISSING - skip")
        return
    if not requests:
        print("[SLACK] requests not installed - skip")
        return
    try:
        resp = requests.post(WEBHOOK, json={"text": text}, timeout=10)
        print(f"[SLACK] http={resp.status_code} body={resp.text[:200]}")
    except Exception as e:
        print("[SLACK] send error:", e)

def pytest_sessionstart(session):
    print("[SLACK] webhook:", "SET" if WEBHOOK else "MISSING")
    session._t0 = time.time()

def pytest_sessionfinish(session, exitstatus):
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    stats = {k: len(v) for k, v in getattr(tr, "stats", {}).items()}
    total = getattr(tr, "_numcollected", 0)
    duration = time.time() - getattr(session, "_t0", time.time())
    nodeids = [item.nodeid for item in getattr(session, "items", [])]
    has_v2 = any("test_dev_b2b_v2.py" in nid or "test_b2b_v3.py" in nid for nid in nodeids)

    print(f"[SLACK] exitstatus={exitstatus} (0=all passed)")
    print(f"[SLACK] counts={stats}, total={total}, duration={duration:.2f}s")
    print(f"[SLACK] has_v2={has_v2}")

    # v2 파일이 포함된 실행이면 성공/실패 모두 전송
    if has_v2:
        ok = (exitstatus == 0)
        status_text = "✅ SUCCESS" if ok else "❌ FAILED"
        msg = (
            f"{status_text} test_dev_b2b_v2\n"
            f"- Exit: {exitstatus}\n"
            f"- Collected: {total}\n"
            f"- Stats: {json.dumps(stats, ensure_ascii=False)}\n"
            f"- 소요시간: {duration:.2f}s\n"
            f"- 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        _post_to_slack(msg)
    else:
        print("[SLACK] skip send: v2 미포함")
