"""
B2B 통합 테스트 v4
- v3 (CRM 기능 검증) + test_statistics (통계 검증) 병합
- 고객 추가 → 충전 → 예약 → 매출등록 → CRM 기능 → 통계 검증 → 고객 차트 필터
"""

import asyncio
import os
import re
from datetime import datetime

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
    await runner._dismiss_popup()
    yield


# ══════════════════════════════════════════════
# Phase 1: 셋업 (고객/충전/예약/매출)
# ══════════════════════════════════════════════

async def test_setup_customers(runner):
    """고객 3명 추가 (소개자 포함)"""
    await runner.add_customers()


async def test_setup_customer_detail_name(runner):
    """고객 상세 이름 확인 (리스트 → 상세)"""
    target_name = f"자동화_{runner.mmdd}_1"
    detail_page = await runner.open_customer_detail_from_list(target_name)
    await runner.assert_customer_name_visible_top_left(detail_page, target_name)


async def test_setup_membership_charge(runner):
    """자동화_1 정액권 200,000원 충전"""
    target_name = f"자동화_{runner.mmdd}_1"
    await runner.membership_charge_and_verify(target_name)
    runner._membership_hour = datetime.now().hour


async def test_setup_family_share(runner):
    """자동화_1 ↔ 자동화_3 패밀리 공유"""
    target_owner = f"자동화_{runner.mmdd}_1"
    target_member = f"자동화_{runner.mmdd}_3"
    await runner.family_add_and_verify(target_owner, target_member)


async def test_setup_ticket_charge(runner):
    """자동화_2 티켓 10만원권 충전"""
    target_name = f"자동화_{runner.mmdd}_2"
    await runner.ticket_charge_and_verify(target_name)
    runner._ticket_hour = datetime.now().hour


async def test_setup_reservations(runner):
    """예약 3건 등록"""
    await runner.make_reservations()


async def test_setup_verify_calendar(runner):
    """캘린더 예약 확인"""
    await runner.verify_calendar_reservations()


async def test_setup_sales_registrations(runner):
    """매출등록 5건 (사진 포함)"""
    await runner.sales_registrations_1()
    await runner.sales_registrations_2()
    await runner.sales_registrations_3()
    await runner.sales_registrations_4()
    runner._unreg_sales_hour = datetime.now().hour
    await runner.sales_registrations_5()
    runner._family_sales_hour = datetime.now().hour


# ══════════════════════════════════════════════
# Phase 1.5: 사진 확인/삭제 검증
# ══════════════════════════════════════════════

async def test_verify_photos_sales_1(runner):
    """자동화_1 매출 사진 10장 확인"""
    customer = f"자동화_{runner.mmdd}_1"
    await runner.verify_sales_photos(customer, expected_count=10)


async def test_verify_photos_sales_3(runner):
    """자동화_3 매출 사진 20장 확인 (매출3: 10장 + 매출5: 10장)"""
    customer = f"자동화_{runner.mmdd}_3"
    await runner.verify_sales_photos(customer, expected_count=20)


async def test_delete_photos_sales_3(runner):
    """자동화_3 사진 5장 삭제 → 15장 확인"""
    customer = f"자동화_{runner.mmdd}_3"
    await runner.delete_sales_photos(customer, delete_count=5)
    await runner.verify_sales_photos(customer, expected_count=15)


# ══════════════════════════════════════════════
# Phase 2: CRM 기능 검증 (배치 대기 전에 실행)
# ══════════════════════════════════════════════

async def test_verify_send_history(runner):
    """발송 이력 확인"""
    await runner.verify_send_history()


async def test_verify_shop_status(runner):
    """샵 현황 오늘 요약"""
    await runner.verify_shop_status_today_summary()


async def test_verify_statistics_details(runner):
    """통계 상세 검증"""
    await runner.verify_shop_status_and_statistics()


async def test_custom_payment_method(runner):
    """결제 수단 설정"""
    await runner.custom_payment_method()


async def test_customer_detail_verification(runner):
    """고객 상세 검증"""
    await runner.customer_detail_verification()


async def test_block_reservation(runner):
    """예약 차단 등록/반복/검증/삭제"""
    await runner.block_reservation()
    await runner.block_reservation_repeat()
    await runner.verify_block_reservation()
    await runner.verify_block_reservation_repeat()
    await runner.delete_block_reservation()
    await runner.delete_block_reservation_repeat()


# ══════════════════════════════════════════════
# 헬퍼 함수 (통계 검증용)
# ══════════════════════════════════════════════

async def _open_staff_statistics(runner):
    """통계 > 직원 통계 자세히 보기 → 오늘 필터 적용"""
    await runner._open_statistics_page()
    await runner._open_stat_detail("직원 통계")
    await runner._apply_today_filter()


async def _get_staff_row(table, staff_name):
    rows = table.locator("tbody tr:visible")
    row_count = await rows.count()
    for i in range(row_count):
        r = rows.nth(i)
        text = await r.inner_text()
        if staff_name in text:
            return r
    return None


async def _get_value_by_col_header(table, header_text, row):
    header = table.locator(f"thead th:has-text('{header_text}')").first
    await expect(header).to_be_visible(timeout=3000)
    col_idx = await header.evaluate(
        "th => Array.from(th.parentElement.children).indexOf(th) + 1"
    )
    cell = row.locator(f"td:nth-child({col_idx})").first
    await expect(cell).to_be_visible(timeout=3000)
    text = re.sub(r"\s+", " ", (await cell.inner_text()).strip())
    m = re.search(r"([0-9][0-9,]*)\s*원", text)
    if m:
        return int(m.group(1).replace(",", ""))
    m = re.search(r"([0-9]+)\s*(건|명)", text)
    if m:
        return int(m.group(1))
    m = re.search(r"([0-9][0-9,]*)\s*P", text)
    if m:
        return int(m.group(1).replace(",", ""))
    m = re.search(r"([0-9.]+)\s*%", text)
    if m:
        return float(m.group(1))
    raise AssertionError(f"값 파싱 실패 ({header_text}): {text}")


async def _get_customer_type_values(table, row):
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


async def _wait_for_batch(runner, staff_name, expected_sales_count, max_retries=20, interval=30):
    for attempt in range(max_retries):
        try:
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
        except Exception as e:
            print(f"  [배치 대기 {attempt + 1}/{max_retries}] 페이지 진입 실패: {e}")

        if attempt < max_retries - 1:
            print(f"  → {interval}초 대기 후 재시도...")
            await runner.page.wait_for_timeout(interval * 1000)
            base = runner.base_url.replace("/signin", "")
            await runner.page.goto(f"{base}/book/calendar", wait_until="networkidle")

    raise AssertionError(
        f"배치 반영 타임아웃: {staff_name} 매출 건수가 {expected_sales_count}건에 도달하지 못함 "
        f"({max_retries * interval}초 대기)"
    )


async def _get_first_data_row_values(table):
    return await table.evaluate(
        """(el) => {
            const row = el.querySelector('tbody tr');
            if (!row) return [];
            return [...row.querySelectorAll('td')].map(
                td => (td.innerText || '').replace(/\\s+/g, ' ').trim()
            );
        }"""
    )


async def _get_all_data_rows(table):
    return await table.evaluate(
        """(el) => {
            const rows = [...el.querySelectorAll('tbody tr')];
            return rows.map(row =>
                [...row.querySelectorAll('td')].map(
                    td => (td.innerText || '').replace(/\\s+/g, ' ').trim()
                )
            );
        }"""
    )


def _build_hourly_expected(runner=None, non_reservation_hour=None):
    hourly = {}

    def add(hour, count, sales, deduct):
        if hour not in hourly:
            hourly[hour] = {"매출 건수": 0, "실매출": 0, "차감": 0}
        hourly[hour]["매출 건수"] += count
        hourly[hour]["실매출"] += sales
        hourly[hour]["차감"] += deduct

    add(16, 1, 0, 20000)
    add(17, 1, 0, 20000)
    add(18, 1, 10000, 0)

    membership_h = getattr(runner, "_membership_hour", non_reservation_hour)
    ticket_h = getattr(runner, "_ticket_hour", non_reservation_hour)
    unreg_h = getattr(runner, "_unreg_sales_hour", non_reservation_hour)
    family_h = getattr(runner, "_family_sales_hour", non_reservation_hour)

    if membership_h is not None:
        add(membership_h, 1, 200000, 0)
    if ticket_h is not None:
        add(ticket_h, 1, 100000, 0)
    if unreg_h is not None:
        add(unreg_h, 1, 10000, 0)
    if family_h is not None:
        add(family_h, 1, 0, 10000)

    for h in hourly:
        hourly[h]["총합계"] = hourly[h]["실매출"] + hourly[h]["차감"]

    return hourly


# ══════════════════════════════════════════════
# Phase 3: 통계 검증 (배치 대기 후)
# ══════════════════════════════════════════════

async def test_staff_statistics_product_type(runner):
    """직원 통계 — 상품 유형별 검증"""
    staff_name = runner.owner_name
    await _wait_for_batch(runner, staff_name, expected_sales_count=7)

    table = runner.page.locator("table:visible").first
    await expect(table).to_be_visible(timeout=5000)
    row = await _get_staff_row(table, staff_name)
    assert row is not None, f"직원 '{staff_name}' 행을 찾을 수 없습니다."

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


async def test_channel_statistics(runner):
    """채널별 매출 통계 — 공비서 원장님 채널 검증"""
    await runner._open_statistics_page()
    await runner._open_stat_detail("채널별 매출 통계")
    await runner._apply_today_filter()

    table = runner.page.locator("table:visible").first
    await expect(table).to_be_visible(timeout=5000)

    row_values = await _get_first_data_row_values(table)
    assert len(row_values) >= 4, f"채널별 매출 통계 컬럼 부족: {row_values}"

    def parse_int(text):
        m = re.search(r"([0-9][0-9,]*)", text.replace(",", ""))
        return int(m.group(1)) if m else 0

    actual_count = parse_int(row_values[1])
    actual_sales = parse_int(row_values[2])
    actual_deduct = parse_int(row_values[3])

    assert actual_count == 7, f"채널별 매출 건수 불일치: 기대 7, 실제 {actual_count}"
    assert actual_sales == 320000, f"채널별 실매출 합계 불일치: 기대 320,000, 실제 {actual_sales:,}"
    assert actual_deduct == 50000, f"채널별 차감 합계 불일치: 기대 50,000, 실제 {actual_deduct:,}"

    print("✓ 채널별 매출 통계 검증 완료")


async def test_customer_statistics(runner):
    """고객 통계 — 고객 유형별 매출 건수/실매출/객단가/차감금액 검증"""
    await runner._open_statistics_page()
    await runner._open_stat_detail("고객 통계")
    await runner._apply_today_filter()

    table = runner.page.locator("table:visible").first
    await expect(table).to_be_visible(timeout=5000)

    row_values = await _get_first_data_row_values(table)

    def parse_int(text):
        m = re.search(r"([0-9][0-9,]*)", text.replace(",", ""))
        return int(m.group(1)) if m else 0

    expected_map = {
        "재방문 고객": {
            "매출 건수": (1, 1), "실매출": (2, 0), "객단가": (3, 0), "차감 금액": (4, 10000),
        },
        "신규 고객": {
            "매출 건수": (6, 5), "실매출": (7, 310000), "객단가": (8, 62000), "차감 금액": (9, 40000),
        },
        "미등록 고객": {
            "매출 건수": (11, 1), "실매출": (12, 10000), "객단가": (13, 10000),
        },
    }

    for group_name, fields in expected_map.items():
        for field_name, (col_idx, expected_val) in fields.items():
            assert col_idx < len(row_values), (
                f"고객 통계 [{group_name}] 컬럼 인덱스 {col_idx} 초과 (총 {len(row_values)}컬럼)"
            )
            actual = parse_int(row_values[col_idx])
            assert actual == expected_val, (
                f"고객 통계 [{group_name}] {field_name} 불일치: 기대 {expected_val:,}, 실제 {actual:,}"
            )

    print("✓ 고객 통계 검증 완료")


async def test_time_statistics(runner):
    """시간별 분석 — 시간대별 매출 건수/실매출/차감/총합계 검증"""
    await runner._open_statistics_page()
    await runner._open_stat_detail("시간별 분석")
    await runner._apply_today_filter()

    table = runner.page.locator("table:visible").first
    await expect(table).to_be_visible(timeout=5000)

    all_rows = await _get_all_data_rows(table)

    def parse_int(text):
        m = re.search(r"([0-9][0-9,]*)", text.replace(",", ""))
        return int(m.group(1)) if m else 0

    def parse_hour_from_range(text):
        m = re.search(r"(오전|오후)\s*(\d{1,2}):(\d{2})", text)
        if not m:
            return None
        ampm, h = m.group(1), int(m.group(2))
        if ampm == "오후" and h != 12:
            h += 12
        elif ampm == "오전" and h == 12:
            h = 0
        return h

    time_rows = {}
    for row_vals in all_rows:
        if not row_vals:
            continue
        hour = parse_hour_from_range(row_vals[0])
        if hour is not None:
            time_rows[hour] = row_vals

    hourly_expected = _build_hourly_expected(runner)

    has_recorded_hours = hasattr(runner, "_membership_hour")
    if not has_recorded_hours:
        non_res_hour = None
        for hour in sorted(time_rows.keys()):
            if hour in (16, 17, 18):
                continue
            count = parse_int(time_rows[hour][1]) if len(time_rows[hour]) > 1 else 0
            if count > 0:
                non_res_hour = hour
                break
        if non_res_hour is None:
            non_res_hour = 18
        hourly_expected = _build_hourly_expected(non_reservation_hour=non_res_hour)

    for hour, exp in hourly_expected.items():
        assert hour in time_rows, f"시간별 분석: {hour}시 행이 없습니다."
        row_vals = time_rows[hour]
        actual_count = parse_int(row_vals[1]) if len(row_vals) > 1 else 0
        actual_sales = parse_int(row_vals[2]) if len(row_vals) > 2 else 0
        actual_deduct = parse_int(row_vals[3]) if len(row_vals) > 3 else 0
        actual_total = parse_int(row_vals[4]) if len(row_vals) > 4 else 0

        assert actual_count == exp["매출 건수"], (
            f"시간별 [{hour}시] 매출 건수 불일치: 기대 {exp['매출 건수']}, 실제 {actual_count}"
        )
        assert actual_sales == exp["실매출"], (
            f"시간별 [{hour}시] 실매출 불일치: 기대 {exp['실매출']:,}, 실제 {actual_sales:,}"
        )
        assert actual_deduct == exp["차감"], (
            f"시간별 [{hour}시] 차감 불일치: 기대 {exp['차감']:,}, 실제 {actual_deduct:,}"
        )
        assert actual_total == exp["총합계"], (
            f"시간별 [{hour}시] 총합계 불일치: 기대 {exp['총합계']:,}, 실제 {actual_total:,}"
        )

    print("✓ 시간별 분석 검증 완료")


async def test_day_statistics(runner):
    """요일별 분석 — 오늘 요일 기준 매출 건수/실매출/차감/총합계 검증"""
    await runner._open_statistics_page()
    await runner._open_stat_detail("요일별 분석")
    await runner._apply_today_filter()

    table = runner.page.locator("table:visible").first
    await expect(table).to_be_visible(timeout=5000)

    day_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    today_day = day_names[datetime.now().weekday()]

    all_rows = await _get_all_data_rows(table)

    def parse_int(text):
        m = re.search(r"([0-9][0-9,]*)", text.replace(",", ""))
        return int(m.group(1)) if m else 0

    target_row = None
    for row_vals in all_rows:
        if row_vals and today_day in row_vals[0]:
            target_row = row_vals
            break

    assert target_row is not None, f"요일별 분석: '{today_day}' 행을 찾을 수 없습니다."

    actual_count = parse_int(target_row[1]) if len(target_row) > 1 else 0
    actual_sales = parse_int(target_row[2]) if len(target_row) > 2 else 0
    actual_deduct = parse_int(target_row[3]) if len(target_row) > 3 else 0
    actual_total = parse_int(target_row[4]) if len(target_row) > 4 else 0

    assert actual_count == 7, f"요일별 [{today_day}] 매출 건수 불일치: 기대 7, 실제 {actual_count}"
    assert actual_sales == 320000, f"요일별 [{today_day}] 실매출 합계 불일치: 기대 320,000, 실제 {actual_sales:,}"
    assert actual_deduct == 50000, f"요일별 [{today_day}] 차감 합계 불일치: 기대 50,000, 실제 {actual_deduct:,}"
    assert actual_total == 370000, f"요일별 [{today_day}] 총합계 불일치: 기대 370,000, 실제 {actual_total:,}"

    print(f"✓ 요일별 분석 검증 완료 ({today_day})")


# ══════════════════════════════════════════════
# Phase 4: 고객 차트 필터 검증
# ══════════════════════════════════════════════

async def _get_chart_customer_names(runner):
    await runner.page.wait_for_timeout(1500)
    names = await runner.page.evaluate(
        """() => {
            const cells = [...document.querySelectorAll('tbody tr p[class*="sc-4d212aff-2"]')];
            return cells
                .filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
                .map(el => (el.innerText || '').trim());
        }"""
    )
    return names


async def test_customer_chart_filter_procedure(runner):
    """고객 차트 — 받은 시술 필터 (손 > 젤 기본 → 자동화_1, 손 > 케어 → 자동화_3)"""
    await runner.focus_main_page()
    await runner._open_customer_chart()

    # 조건 추가 → 받은 시술
    add_btn = runner.page.locator("button:has(h5:has-text('조건 추가'))").first
    await expect(add_btn).to_be_visible(timeout=5000)
    await add_btn.click()
    await runner.page.wait_for_timeout(700)
    condition_btn = runner.page.locator("button:has-text('받은 시술')").first
    await expect(condition_btn).to_be_visible(timeout=5000)
    await condition_btn.click()
    await runner.page.wait_for_timeout(700)

    # 그룹: 손
    group_select = runner.page.locator("#cosmeticGroup button[data-testid='select-toggle-button']").first
    await expect(group_select).to_be_visible(timeout=5000)
    await group_select.click()
    await runner.page.wait_for_timeout(500)
    await runner.page.locator("#cosmeticGroup li:has-text('손')").first.click()
    await runner.page.wait_for_timeout(500)

    # 시술: 젤 기본
    item_select = runner.page.locator("#cosmeticItem button[data-testid='select-toggle-button']").first
    await expect(item_select).to_be_visible(timeout=5000)
    await item_select.click()
    await runner.page.wait_for_timeout(500)
    await runner.page.locator("#cosmeticItem li:has-text('젤 기본')").first.click()
    await runner.page.wait_for_timeout(1000)

    customer_1 = f"자동화_{runner.mmdd}_1"
    names = await _get_chart_customer_names(runner)
    assert customer_1 in names, f"받은 시술(젤 기본) 필터 결과에 '{customer_1}' 미노출 (목록: {names})"
    print(f"✓ 받은 시술 필터 (손 > 젤 기본) → {customer_1} 노출 확인")

    # 케어 검증
    item_select2 = runner.page.locator("#cosmeticItem button[data-testid='select-toggle-button']").first
    await expect(item_select2).to_be_visible(timeout=5000)
    await item_select2.click()
    await runner.page.wait_for_timeout(500)
    await runner.page.locator("#cosmeticItem li:has-text('케어')").first.click()
    await runner.page.wait_for_timeout(1000)

    customer_3 = f"자동화_{runner.mmdd}_3"
    names = await _get_chart_customer_names(runner)
    assert customer_3 in names, f"받은 시술(케어) 필터 결과에 '{customer_3}' 미노출 (목록: {names})"
    print(f"✓ 받은 시술 필터 (손 > 케어) → {customer_3} 노출 확인")


async def test_customer_chart_filter_staff(runner):
    """고객 차트 — 담당자 필터 (샵주테스트 → 자동화_1,2,3 노출)"""
    await runner.focus_main_page()
    await runner._open_customer_chart()

    # 조건 추가 → 담당자
    add_btn = runner.page.locator("button:has(h5:has-text('조건 추가'))").first
    await expect(add_btn).to_be_visible(timeout=5000)
    await add_btn.click()
    await runner.page.wait_for_timeout(700)
    condition_btn = runner.page.locator("button:has-text('담당자')").first
    await expect(condition_btn).to_be_visible(timeout=5000)
    await condition_btn.click()
    await runner.page.wait_for_timeout(700)

    staff_select = runner.page.locator("#optionValues button[data-testid='select-toggle-button']").first
    await expect(staff_select).to_be_visible(timeout=5000)
    await staff_select.click()
    await runner.page.wait_for_timeout(500)

    staff_name = runner.owner_name
    await runner.page.locator(f"button:has-text('{staff_name}'):visible, li:has-text('{staff_name}'):visible, [role='option']:has-text('{staff_name}'):visible").first.click()
    await runner.page.wait_for_timeout(1000)

    names = await _get_chart_customer_names(runner)
    for i in [1, 2, 3]:
        customer = f"자동화_{runner.mmdd}_{i}"
        assert customer in names, f"담당자({staff_name}) 필터 결과에 '{customer}' 미노출 (목록: {names})"

    print(f"✓ 담당자 필터 ({staff_name}) → 자동화_1,2,3 전체 노출 확인")


# ══════════════════════════════════════════════
# Phase 5: 슬랙 결과 전송
# ══════════════════════════════════════════════

async def test_send_slack_results(runner, request):
    """슬랙 결과 전송"""
    import json
    import urllib.request

    session = request.session
    case_results = getattr(session, "_case_results", {})

    name_map = {
        "test_setup_customers": "셋업 — 고객 추가",
        "test_setup_customer_detail_name": "셋업 — 고객 상세 이름",
        "test_setup_membership_charge": "셋업 — 정액권 충전",
        "test_setup_family_share": "셋업 — 패밀리 공유",
        "test_setup_ticket_charge": "셋업 — 티켓 충전",
        "test_setup_reservations": "셋업 — 예약 등록",
        "test_setup_verify_calendar": "셋업 — 캘린더 확인",
        "test_setup_sales_registrations": "셋업 — 매출등록 (사진 포함)",
        "test_verify_photos_sales_1": "사진 확인 — 자동화_1 (10장)",
        "test_verify_photos_sales_3": "사진 확인 — 자동화_3 (20장)",
        "test_delete_photos_sales_3": "사진 삭제 — 자동화_3 (5장→15장)",
        "test_verify_send_history": "발송 이력 확인",
        "test_verify_shop_status": "샵 현황 오늘 요약",
        "test_verify_statistics_details": "통계 상세 검증",
        "test_custom_payment_method": "결제 수단 설정",
        "test_customer_detail_verification": "고객 상세 검증",
        "test_block_reservation": "예약 차단",
        "test_staff_statistics_product_type": "상품 유형별 통계",
        "test_staff_statistics_customer_type_real": "고객 유형별 (실 매출 기준)",
        "test_staff_statistics_customer_type_total": "고객 유형별 (총 합계 기준)",
        "test_channel_statistics": "채널별 매출 통계",
        "test_customer_statistics": "고객 통계",
        "test_time_statistics": "시간별 분석",
        "test_day_statistics": "요일별 분석",
        "test_customer_chart_filter_procedure": "고객 차트 — 받은 시술 필터",
        "test_customer_chart_filter_staff": "고객 차트 — 담당자 필터",
    }

    results = {}
    for nodeid, info in case_results.items():
        test_name = nodeid.split("::")[-1]
        display_name = name_map.get(test_name)
        if display_name:
            results[display_name] = info.get("status", "UNKNOWN")

    if not SLACK_WEBHOOK_URL:
        print("[SLACK] webhook URL 없음 — 전송 스킵")
        return

    lines = ["*[B2B 통합 테스트 v4]*\n"]
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
