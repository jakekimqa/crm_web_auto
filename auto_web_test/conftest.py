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
import os, time
from datetime import datetime
from pathlib import Path
import pytest

# .env 파일 자동 로드
try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).parent / ".env.dev"
    if _env_file.exists():
        load_dotenv(_env_file, override=False)
except ImportError:
    pass

try:
    import requests
except ImportError:
    requests = None

WEBHOOK = os.getenv("SLACK_WEBHOOK_URL")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL")
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "..", "qa_artifacts", "screenshots")
ACTIVE_SESSION = None

def _post_to_slack(text: str):
    """메시지 전송 후 thread_ts 반환 (Slack API 사용 시)"""
    if not WEBHOOK and not SLACK_BOT_TOKEN:
        print("[SLACK] webhook/token MISSING - skip")
        return None
    if not requests:
        print("[SLACK] requests not installed - skip")
        return None

    # Bot Token이 있으면 chat.postMessage API 사용 (thread_ts 반환 가능)
    if SLACK_BOT_TOKEN and SLACK_CHANNEL:
        try:
            resp = requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                json={"channel": SLACK_CHANNEL, "text": text},
                timeout=10,
            )
            data = resp.json()
            ts = data.get("ts")
            print(f"[SLACK] API http={resp.status_code} ok={data.get('ok')} ts={ts}")
            return ts
        except Exception as e:
            print("[SLACK] API send error:", e)
            return None

    # Webhook fallback (thread_ts 반환 불가)
    try:
        resp = requests.post(WEBHOOK, json={"text": text}, timeout=10)
        print(f"[SLACK] http={resp.status_code} body={resp.text[:200]}")
    except Exception as e:
        print("[SLACK] send error:", e)
    return None

def _upload_fail_screenshots(fail_cases, thread_ts):
    """실패 케이스의 스크린샷을 Slack 쓰레드에 업로드"""
    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL:
        print("[SLACK] BOT_TOKEN/CHANNEL 미설정 — 스크린샷 업로드 스킵")
        # 스크린샷 경로만 출력
        for case_name in fail_cases:
            shots = _find_screenshots_for_case(case_name)
            if shots:
                print(f"[SLACK] 실패 스크린샷 ({case_name}): {shots}")
        return
    if not requests:
        return

    for case_name in fail_cases:
        shots = _find_screenshots_for_case(case_name)
        for shot_path in shots:
            try:
                with open(shot_path, "rb") as f:
                    resp = requests.post(
                        "https://slack.com/api/files.upload",
                        headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                        data={
                            "channels": SLACK_CHANNEL,
                            "thread_ts": thread_ts,
                            "title": f"[FAIL] {case_name} - {os.path.basename(shot_path)}",
                            "initial_comment": f"❌ `{case_name}` 실패 스크린샷",
                        },
                        files={"file": (os.path.basename(shot_path), f, "image/png")},
                        timeout=30,
                    )
                data = resp.json()
                print(f"[SLACK] upload {os.path.basename(shot_path)}: ok={data.get('ok')}")
            except Exception as e:
                print(f"[SLACK] upload error ({shot_path}): {e}")

def _find_screenshots_for_case(case_name):
    """케이스 이름에 해당하는 최근 스크린샷 찾기"""
    import glob
    shot_dir = os.path.abspath(SCREENSHOT_DIR)
    if not os.path.isdir(shot_dir):
        return []
    # 모든 png 파일에서 최근 것 반환
    all_pngs = sorted(glob.glob(os.path.join(shot_dir, "*.png")), key=os.path.getmtime, reverse=True)
    # 최근 5개까지 반환 (실패 시점에 가장 가까운 스크린샷)
    return all_pngs[:5]

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """테스트 실패 시 자동 스크린샷 캡처"""
    import pytest
    outcome = yield
    report = outcome.get_result()
    if report.when == "call" and report.failed:
        # runner fixture에서 page 가져오기
        runner = item.funcargs.get("runner")
        if runner and hasattr(runner, "page") and runner.page and not runner.page.is_closed():
            shot_dir = os.path.abspath(SCREENSHOT_DIR)
            os.makedirs(shot_dir, exist_ok=True)
            test_name = item.name
            shot_path = os.path.join(shot_dir, f"FAIL_{test_name}.png")
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                loop.run_until_complete(runner.page.screenshot(path=shot_path))
                print(f"[SCREENSHOT] 실패 스크린샷 저장: {shot_path}")
            except Exception as e:
                print(f"[SCREENSHOT] 스크린샷 캡처 실패: {e}")


def pytest_sessionstart(session):
    global ACTIVE_SESSION
    print("[SLACK] webhook:", "SET" if WEBHOOK else "MISSING")
    session._t0 = time.time()
    session._case_results = {}
    ACTIVE_SESSION = session


def pytest_runtest_logreport(report):
    session = ACTIVE_SESSION
    if session is None:
        return

    cases = getattr(session, "_case_results", None)
    if cases is None:
        session._case_results = {}
        cases = session._case_results

    nodeid = report.nodeid
    name = nodeid.split("::")[-1]
    item = cases.get(nodeid, {"name": name, "status": "UNKNOWN", "duration": 0.0})

    # call 단계가 실제 테스트 결과의 기준
    if report.when == "call":
        if getattr(report, "wasxfail", False):
            item["status"] = "XPASS" if report.passed else "XFAIL"
        elif report.passed:
            item["status"] = "PASS"
        elif report.failed:
            item["status"] = "FAIL"
        elif report.skipped:
            item["status"] = "SKIP"
        item["duration"] = float(getattr(report, "duration", 0.0))
    # setup 실패/스킵으로 call 단계에 못 들어간 케이스 처리
    elif report.when == "setup" and report.outcome in ("failed", "skipped"):
        item["status"] = "ERROR" if report.failed else "SKIP"
        item["duration"] = float(getattr(report, "duration", 0.0))

    cases[nodeid] = item

def pytest_sessionfinish(session, exitstatus):
    tr = session.config.pluginmanager.get_plugin("terminalreporter")
    stats = {k: len(v) for k, v in getattr(tr, "stats", {}).items()}
    total = getattr(tr, "_numcollected", 0)
    duration = time.time() - getattr(session, "_t0", time.time())
    nodeids = [item.nodeid for item in getattr(session, "items", [])]
    has_v2 = any("test_b2b_v2.py" in nid for nid in nodeids)
    case_results = getattr(session, "_case_results", {})

    print(f"[SLACK] exitstatus={exitstatus} (0=all passed)")
    print(f"[SLACK] counts={stats}, total={total}, duration={duration:.2f}s")
    print(f"[SLACK] has_v2={has_v2}")

    # v2 또는 v3 파일이 포함된 실행이면 성공/실패 모두 전송
    has_v3 = any("test_b2b_v3.py" in nid for nid in nodeids)
    target_files = []
    if has_v2:
        target_files.append("test_b2b_v2.py")
    if has_v3:
        target_files.append("test_b2b_v3.py")

    if target_files:
        ok = (exitstatus == 0)
        file_label = " / ".join(target_files)
        status_text = "✅ 자동화 시나리오 완료" if ok else "❌ 자동화 시나리오 실패"
        case_lines = []
        case_map = {}
        fail_cases = []
        for item in getattr(session, "items", []):
            nodeid = item.nodeid
            if not any(f in nodeid for f in target_files):
                continue
            c = case_results.get(nodeid)
            if not c:
                continue
            case_map[c["name"]] = c["status"]
            icon = "✅" if c["status"] == "PASS" else ("⏭️" if c["status"] == "SKIP" else "❌")
            case_lines.append(f"{icon} {c['name']} ({c['duration']:.2f}s)")
            if c["status"] in ("FAIL", "ERROR"):
                fail_cases.append(c["name"])

        case_block = "\n".join(case_lines) if case_lines else "- (케이스 결과 없음)"

        flow_lines = []
        if case_map.get("test_full_e2e_from_start_v2") == "PASS":
            flow_lines.extend([
                "- 고객 3명 생성 + 중복 연락처 모달 검증 완료",
                "- 정액권/티켓/예약 흐름 완료",
            ])
        if case_map.get("test_sales_registrations_1_to_4_v2") == "PASS":
            flow_lines.append("- 매출등록 1~4 완료 (매출 등록 4 완료)")
        # v3 flow
        if case_map.get("test_login_and_add_customers") == "PASS":
            flow_lines.append("- 고객 3명 등록 완료")
        if case_map.get("test_membership_charge_from_customer_detail") == "PASS":
            flow_lines.append("- 정액권 충전 완료")
        if case_map.get("test_family_share") == "PASS":
            flow_lines.append("- 패밀리 추가 완료")
        if case_map.get("test_ticket_charge_from_customer_detail") == "PASS":
            flow_lines.append("- 티켓 충전 완료")
        if case_map.get("test_make_reservations") == "PASS":
            flow_lines.append("- 예약 등록 완료")
        if case_map.get("test_sales_registrations_1_to_4") == "PASS":
            flow_lines.append("- 매출등록 1~4 완료")
        flow_block = "\n".join(flow_lines)

        pass_count = sum(1 for s in case_map.values() if s == "PASS")
        fail_count = sum(1 for s in case_map.values() if s in ("FAIL", "ERROR"))
        skip_count = sum(1 for s in case_map.values() if s == "SKIP")
        msg = (
            f"{status_text}\n"
            f"실행 파일: {file_label}\n"
            f"결과 요약: PASS {pass_count} / FAIL {fail_count} / SKIP {skip_count}\n"
            f"소요시간: {duration:.2f}s | 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            + (f"\n진행 완료 항목:\n{flow_block}\n" if flow_block else "\n")
            + f"\n케이스 상세:\n{case_block}"
        )

        # 메인 메시지 전송
        main_ts = _post_to_slack(msg)

        # 실패 케이스가 있으면 스크린샷을 쓰레드에 첨부
        if fail_cases and main_ts:
            _upload_fail_screenshots(fail_cases, main_ts)
    else:
        print("[SLACK] skip send: v2/v3 미포함")
