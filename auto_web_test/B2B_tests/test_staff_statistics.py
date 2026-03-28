"""
직원 통계 검증 테스트
- 고객 추가 (소개자 포함) → 정액권/티켓 충전 → 가족공유 → 예약 → 매출등록 5건
- 직원 통계: 상품 유형별 + 고객 유형별 (실 매출 / 총 합계) 검증
- 통계 배치는 5분마다 → polling 방식으로 대기
"""

import os
import re

import pytest
import pytest_asyncio
from playwright.async_api import expect

from auto_web_test.B2B_tests.test_b2b_v2 import B2BAutomationV2

pytestmark = pytest.mark.asyncio(loop_scope="module")

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")


# ── module-scoped fixture: 브라우저 + 로그인 1회 ──

@pytest_asyncio.fixture(scope="module")
async def runner():
    r = B2BAutomationV2()
    await r.setup()
    await r.login()
    yield r
    await r.teardown()


@pytest_asyncio.fixture(autouse=True)
async def clean_state(runner):
    for p in runner.context.pages[1:]:
        if not p.is_closed():
            await p.close()
    await runner.focus_main_page()
    base = runner.base_url.replace("/signin", "")
    await runner.page.goto(f"{base}/book/calendar")
    await runner.page.wait_for_load_state("networkidle")
    yield


# ── 셋업 테스트 (고객/충전/예약/매출) ──

async def test_setup_customers(runner):
    """고객 3명 추가 (소개자 포함)"""
    await runner.add_customers()


async def test_setup_membership_charge(runner):
    """자동화_1 정액권 200,000원 충전"""
    target_name = f"자동화_{runner.mmdd}_1"
    await runner.membership_charge_and_verify(target_name)


async def test_setup_family_share(runner):
    """자동화_1 ↔ 자동화_3 패밀리 공유"""
    target_owner = f"자동화_{runner.mmdd}_1"
    target_member = f"자동화_{runner.mmdd}_3"
    await runner.family_add_and_verify(target_owner, target_member)


async def test_setup_ticket_charge(runner):
    """자동화_2 티켓 10만원권 충전"""
    target_name = f"자동화_{runner.mmdd}_2"
    await runner.ticket_charge_and_verify(target_name)


async def test_setup_reservations(runner):
    """예약 3건 등록"""
    await runner.make_reservations()


async def test_setup_verify_calendar(runner):
    """캘린더 예약 확인"""
    await runner.verify_calendar_reservations()


async def test_setup_sales_registrations(runner):
    """매출등록 5건"""
    await runner.sales_registrations_1()
    await runner.sales_registrations_2()
    await runner.sales_registrations_3()
    await runner.sales_registrations_4()
    await runner.sales_registrations_5()


# ── 헬퍼 함수 ──

async def _open_staff_statistics(runner):
    """통계 > 직원 통계 자세히 보기 → 오늘 필터 적용"""
    await runner._open_statistics_page()
    await runner._open_stat_detail("직원 통계")
    await runner._apply_today_filter()


async def _get_staff_row(table, staff_name):
    """테이블에서 특정 직원 행 찾기"""
    rows = table.locator("tbody tr:visible")
    row_count = await rows.count()
    for i in range(row_count):
        r = rows.nth(i)
        text = await r.inner_text()
        if staff_name in text:
            return r
    return None


async def _get_value_by_col_header(table, header_text, row):
    """헤더 텍스트로 컬럼 인덱스를 찾아 값 추출"""
    header = table.locator(f"thead th:has-text('{header_text}')").first
    await expect(header).to_be_visible(timeout=3000)
    col_idx = await header.evaluate(
        "th => Array.from(th.parentElement.children).indexOf(th) + 1"
    )
    cell = row.locator(f"td:nth-child({col_idx})").first
    await expect(cell).to_be_visible(timeout=3000)
    text = re.sub(r"\s+", " ", (await cell.inner_text()).strip())
    # 원 단위
    m = re.search(r"([0-9][0-9,]*)\s*원", text)
    if m:
        return int(m.group(1).replace(",", ""))
    # 건/명 단위
    m = re.search(r"([0-9]+)\s*(건|명)", text)
    if m:
        return int(m.group(1))
    # P(포인트)
    m = re.search(r"([0-9][0-9,]*)\s*P", text)
    if m:
        return int(m.group(1).replace(",", ""))
    # 퍼센트
    m = re.search(r"([0-9.]+)\s*%", text)
    if m:
        return float(m.group(1))
    raise AssertionError(f"값 파싱 실패 ({header_text}): {text}")


async def _get_customer_type_values(table, row):
    """고객 유형별 테이블에서 행의 모든 td 값을 추출 (컬럼 인덱스 기반)
    컬럼 순서: 이름 | 신규일반(고객수,매출건,매출금액) | 신규소개(...) | 재방지정(...) | 재방대체(...) | 미등록고객(...)
    """
    cells = row.locator("td")
    cell_count = await cells.count()
    values = []
    for i in range(cell_count):
        text = re.sub(r"\s+", " ", (await cells.nth(i).inner_text()).strip())
        values.append(text)

    def parse_count(text):
        m = re.search(r"([0-9]+)", text)
        return int(m.group(1)) if m else 0

    def parse_amount(text):
        m = re.search(r"([0-9][0-9,]*)\s*원", text)
        return int(m.group(1).replace(",", "")) if m else 0

    # index 0 = 이름, 1~3 = 신규일반, 4~6 = 신규소개, 7~9 = 재방지정, 10~12 = 재방대체, 13~15 = 미등록고객
    result = {}
    types = ["신규 일반", "신규 소개", "재방 지정", "재방 대체", "미등록 고객"]
    for idx, type_name in enumerate(types):
        base_idx = 1 + idx * 3
        if base_idx + 2 < cell_count:
            result[type_name] = {
                "고객 수": parse_count(values[base_idx]),
                "매출 건": parse_count(values[base_idx + 1]),
                "매출 금액": parse_amount(values[base_idx + 2]),
            }
    return result


async def _wait_for_batch(runner, staff_name, expected_sales_count, max_retries=12, interval=30):
    """배치 반영 대기: 직원 통계에서 매출 건수가 기대값에 도달할 때까지 polling
    max_retries=12, interval=30초 → 최대 6분 대기
    """
    for attempt in range(max_retries):
        await _open_staff_statistics(runner)

        table = runner.page.locator("table:visible").first
        if await table.count() > 0:
            row = await _get_staff_row(table, staff_name)
            if row is not None:
                try:
                    actual = await _get_value_by_col_header(table, "매출 건수", row)
                    print(f"  [배치 대기 {attempt + 1}/{max_retries}] 매출 건수: {actual}건 (기대: {expected_sales_count}건)")
                    if actual >= expected_sales_count:
                        print(f"✓ 배치 반영 완료 (시도 {attempt + 1}회)")
                        return
                except Exception:
                    print(f"  [배치 대기 {attempt + 1}/{max_retries}] 값 파싱 실패, 재시도...")

        if attempt < max_retries - 1:
            print(f"  → {interval}초 대기 후 재시도...")
            await runner.page.wait_for_timeout(interval * 1000)
            # 뒤로가기 → 다시 진입
            back_btn = runner.page.locator("button:has(h4:has-text('뒤로가기')):visible, button:has-text('뒤로가기'):visible").first
            if await back_btn.count() > 0:
                await back_btn.click()
                await runner.page.wait_for_timeout(700)

    raise AssertionError(
        f"배치 반영 타임아웃: {staff_name} 매출 건수가 {expected_sales_count}건에 도달하지 못함 "
        f"({max_retries * interval}초 대기)"
    )


async def _send_slack(results: dict):
    """슬랙 메시지 전송"""
    import json
    import urllib.request

    if not SLACK_WEBHOOK_URL:
        print("[SLACK] webhook URL 없음 — 전송 스킵")
        return

    lines = ["*[직원 통계 검증 결과]*\n"]
    all_pass = True

    for test_name, status in results.items():
        icon = "✅" if status == "PASS" else "❌"
        if status != "PASS":
            all_pass = False
        lines.append(f"{icon} {test_name}: {status}")

    lines.append(f"\n{'🎉 전체 통과!' if all_pass else '⚠️ 실패 항목 있음'}")

    payload = json.dumps({"text": "\n".join(lines)}).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL, data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        print(f"[SLACK] 전송 완료: {resp.status}")


# ── 직원 통계 검증 테스트 ──

async def test_staff_statistics_product_type(runner):
    """직원 통계 — 배치 대기 후 상품 유형별 검증 (샵주테스트)"""
    staff_name = runner.owner_name  # 샵주테스트

    # 배치 반영 대기 (매출 건수 7건)
    await _wait_for_batch(runner, staff_name, expected_sales_count=7)

    table = runner.page.locator("table:visible").first
    await expect(table).to_be_visible(timeout=5000)
    row = await _get_staff_row(table, staff_name)
    assert row is not None, f"직원 '{staff_name}' 행을 찾을 수 없습니다."

    # 기대값
    expected = {
        "매출 건수": 7,
        "실 매출 합계": 320000,
        "시술": 10000,
        "정액권 판매": 200000,
        "티켓 판매": 100000,
        "예약 위약금": 0,
        "제품": 10000,
        "차감 합계": 50000,
        "정액권 차감": 30000,
        "티켓 차감": 20000,
        "총 합계": 370000,
    }

    for header, expected_val in expected.items():
        actual = await _get_value_by_col_header(table, header, row)
        assert actual == expected_val, (
            f"상품 유형별 [{staff_name}] {header} 불일치: 기대 {expected_val:,}, 실제 {actual:,}"
        )

    print(f"✓ 직원 통계 상품 유형별 검증 완료 ({staff_name})")
    print(f"  매출 건수: 7건 / 실 매출: 320,000 / 총 합계: 370,000")


async def test_staff_statistics_customer_type_real(runner):
    """직원 통계 — 고객 유형별 (실 매출 기준) 검증"""
    await _open_staff_statistics(runner)

    customer_tab = runner.page.locator("button:has-text('고객 유형별 통계'):visible").first
    await customer_tab.click()
    await runner.page.wait_for_timeout(1000)

    real_label = runner.page.locator("label:has-text('실 매출 기준'):visible").first
    await expect(real_label).to_be_visible(timeout=3000)

    table = runner.page.locator("table:visible").first
    await expect(table).to_be_visible(timeout=5000)

    staff_name = runner.owner_name
    row = await _get_staff_row(table, staff_name)
    assert row is not None, f"직원 '{staff_name}' 행을 찾을 수 없습니다."
    values = await _get_customer_type_values(table, row)

    expected = {
        "신규 일반": {"고객 수": 1, "매출 건": 2, "매출 금액": 200000},
        "신규 소개": {"고객 수": 2, "매출 건": 3, "매출 금액": 110000},
        "재방 지정": {"고객 수": 1, "매출 건": 1, "매출 금액": 0},
        "재방 대체": {"고객 수": 0, "매출 건": 0, "매출 금액": 0},
        "미등록 고객": {"고객 수": 1, "매출 건": 1, "매출 금액": 10000},
    }

    for type_name, exp in expected.items():
        actual = values.get(type_name, {})
        for key, exp_val in exp.items():
            act_val = actual.get(key, -1)
            assert act_val == exp_val, (
                f"고객 유형별 실매출 [{staff_name}] {type_name}/{key} 불일치: "
                f"기대 {exp_val}, 실제 {act_val}"
            )

    print(f"✓ 직원 통계 고객 유형별 (실 매출 기준) 검증 완료 ({staff_name})")


async def test_staff_statistics_customer_type_total(runner):
    """직원 통계 — 고객 유형별 (총 합계 기준) 검증"""
    await _open_staff_statistics(runner)

    customer_tab = runner.page.locator("button:has-text('고객 유형별 통계'):visible").first
    await customer_tab.click()
    await runner.page.wait_for_timeout(1000)

    total_label = runner.page.locator("label:has-text('총 합계 기준'):visible").first
    await total_label.click()
    await runner.page.wait_for_timeout(1000)

    table = runner.page.locator("table:visible").first
    await expect(table).to_be_visible(timeout=5000)

    staff_name = runner.owner_name
    row = await _get_staff_row(table, staff_name)
    assert row is not None, f"직원 '{staff_name}' 행을 찾을 수 없습니다."
    values = await _get_customer_type_values(table, row)

    expected = {
        "신규 일반": {"고객 수": 1, "매출 건": 2, "매출 금액": 220000},
        "신규 소개": {"고객 수": 2, "매출 건": 3, "매출 금액": 130000},
        "재방 지정": {"고객 수": 1, "매출 건": 1, "매출 금액": 10000},
        "재방 대체": {"고객 수": 0, "매출 건": 0, "매출 금액": 0},
        "미등록 고객": {"고객 수": 1, "매출 건": 1, "매출 금액": 10000},
    }

    for type_name, exp in expected.items():
        actual = values.get(type_name, {})
        for key, exp_val in exp.items():
            act_val = actual.get(key, -1)
            assert act_val == exp_val, (
                f"고객 유형별 총합계 [{staff_name}] {type_name}/{key} 불일치: "
                f"기대 {exp_val}, 실제 {act_val}"
            )

    print(f"✓ 직원 통계 고객 유형별 (총 합계 기준) 검증 완료 ({staff_name})")


async def test_send_slack_results(runner, request):
    """슬랙 결과 전송 — 실제 pytest 결과 기반"""
    session = request.session
    case_results = getattr(session, "_case_results", {})

    # 테스트 이름 → 슬랙 표시명 매핑
    name_map = {
        "test_setup_customers": "셋업 — 고객 추가",
        "test_setup_membership_charge": "셋업 — 정액권 충전",
        "test_setup_family_share": "셋업 — 패밀리 공유",
        "test_setup_ticket_charge": "셋업 — 티켓 충전",
        "test_setup_reservations": "셋업 — 예약 등록",
        "test_setup_verify_calendar": "셋업 — 캘린더 확인",
        "test_setup_sales_registrations": "셋업 — 매출등록",
        "test_staff_statistics_product_type": "상품 유형별 통계",
        "test_staff_statistics_customer_type_real": "고객 유형별 (실 매출 기준)",
        "test_staff_statistics_customer_type_total": "고객 유형별 (총 합계 기준)",
    }

    results = {}
    for nodeid, info in case_results.items():
        test_name = nodeid.split("::")[-1]
        display_name = name_map.get(test_name)
        if display_name:
            results[display_name] = info.get("status", "UNKNOWN")

    await _send_slack(results)
