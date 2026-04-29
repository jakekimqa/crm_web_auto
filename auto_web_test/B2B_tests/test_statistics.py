"""
직원 통계 검증 테스트
- 고객 추가 (소개자 포함) → 정액권/티켓 충전 → 가족공유 → 예약 → 매출등록 5건
- 직원 통계: 상품 유형별 + 고객 유형별 (실 매출 / 총 합계) 검증
- 통계 배치는 5분마다 → polling 방식으로 대기
"""

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
    await runner.page.wait_for_load_state("networkidle")
    await runner.page.wait_for_timeout(1000)
    base = runner.base_url.replace("/signin", "")
    for _ in range(3):
        try:
            await runner.page.goto(f"{base}/book/calendar", wait_until="networkidle")
            break
        except Exception:
            await runner.page.wait_for_timeout(1000)
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
    """매출등록 5건"""
    await runner.sales_registrations_1()
    await runner.sales_registrations_2()
    await runner.sales_registrations_3()
    await runner.sales_registrations_4()
    runner._unreg_sales_hour = datetime.now().hour
    await runner.sales_registrations_5()
    runner._family_sales_hour = datetime.now().hour


async def test_setup_verify_photos_sales_1(runner):
    """매출 1 (자동화_1) — 캘린더 예약 상세 → 최근 매출 메모 → 사진 10장 확인"""
    customer = f"자동화_{runner.mmdd}_1"
    await _open_reservation_detail(runner, customer)
    photo_count, broken_count = await _get_photo_count_from_memo(runner)
    print(f"✓ {customer} 사진 개수: {photo_count}장 (깨진 이미지: {broken_count}장)")
    assert photo_count == 10, (
        f"{customer} 사진 개수 불일치: 기대 10장, 실제 {photo_count}장"
    )
    assert broken_count == 0, (
        f"{customer} 깨진 이미지 {broken_count}장 발견"
    )


async def test_setup_verify_photos_sales_3(runner):
    """매출 3+5 (자동화_3) — 캘린더 예약 상세 → 최근 매출 메모 → 사진 20장 확인"""
    customer = f"자동화_{runner.mmdd}_3"
    await _open_reservation_detail(runner, customer)
    photo_count, broken_count = await _get_photo_count_from_memo(runner)
    print(f"✓ {customer} 사진 개수: {photo_count}장 (깨진 이미지: {broken_count}장)")
    assert photo_count == 20, (
        f"{customer} 사진 개수 불일치: 기대 20장, 실제 {photo_count}장"
    )
    assert broken_count == 0, (
        f"{customer} 깨진 이미지 {broken_count}장 발견"
    )


async def test_setup_delete_photos_sales_3(runner):
    """매출 3 (자동화_3) — 매출 수정에서 사진 5장 삭제 후 15장 확인"""
    customer = f"자동화_{runner.mmdd}_3"

    # 1. 캘린더에서 예약 카드 클릭
    await _open_reservation_detail(runner, customer)

    # 2. 매출 수정 버튼 클릭
    edit_btn = runner.page.locator("button:has-text('매출 수정')").first
    await expect(edit_btn).to_be_visible(timeout=5000)
    await edit_btn.click()
    await runner.page.wait_for_load_state("networkidle")
    await runner.page.wait_for_timeout(1500)

    # 3. 사진 탭 클릭
    photo_tab = runner.page.locator("div.sc-f17959d8-1:has(h4:has-text('사진'))").first
    await photo_tab.click()
    await runner.page.wait_for_timeout(500)

    # 4. 사진 아이콘(10/10) 클릭 → 사진 모달 열기
    photo_icon = runner.page.locator("div.sc-b56506f1-3:has(svg[icon='systemImage'])").first
    await photo_icon.click()
    await runner.page.wait_for_timeout(1500)

    # 5. 사진 5장 삭제 (1번~5번 이미지 삭제 버튼 클릭)
    for i in range(5):
        delete_btn = runner.page.locator("button[aria-label*='이미지 삭제']").first
        await expect(delete_btn).to_be_visible(timeout=3000)
        await delete_btn.click()
        await runner.page.wait_for_timeout(500)
    print("  ✓ 사진 5장 삭제 완료")

    # 6. 모달 내 저장 버튼 클릭
    modal_save_btn = runner.page.locator("#modal-content button:has-text('저장'):visible, [role='dialog'] button:has-text('저장'):visible").first
    await expect(modal_save_btn).to_be_enabled(timeout=5000)
    await modal_save_btn.click()
    await runner.page.wait_for_timeout(2000)
    # dimmer 남아있으면 닫기
    dimmer = runner.page.locator("#modal-dimmer.isActiveDimmed").first
    if await dimmer.count() > 0 and await dimmer.is_visible():
        await runner.page.keyboard.press("Escape")
        await runner.page.wait_for_timeout(500)
    print("  ✓ 사진 모달 저장 완료")

    # 7. 매출 저장 버튼 클릭 + alert 확인
    async def _handle_alert(dialog):
        assert "매출이 수정되었습니다" in dialog.message, (
            f"alert 메시지 불일치: {dialog.message}"
        )
        print(f"  ✓ alert 확인: {dialog.message}")
        await dialog.accept()

    runner.page.on("dialog", _handle_alert)
    try:
        sales_save_btn = runner.page.locator("button:has-text('매출 저장'):visible").first
        if await sales_save_btn.count() == 0:
            sales_save_btn = runner.page.locator("button:has-text('매출 등록'):visible").last
        await sales_save_btn.click()
        await runner.page.wait_for_timeout(2000)
    finally:
        runner.page.remove_listener("dialog", _handle_alert)

    # 8. 캘린더로 돌아가서 카드 클릭 → 최근 매출 메모 → 15장 확인
    await _open_reservation_detail(runner, customer)
    photo_count, broken_count = await _get_photo_count_from_memo(runner)
    print(f"✓ {customer} 삭제 후 사진 개수: {photo_count}장 (깨진 이미지: {broken_count}장)")
    assert photo_count == 15, (
        f"{customer} 삭제 후 사진 개수 불일치: 기대 15장, 실제 {photo_count}장"
    )
    assert broken_count == 0, (
        f"{customer} 깨진 이미지 {broken_count}장 발견"
    )


# ── 사진 확인 헬퍼 ──

async def _open_reservation_detail(runner, customer_name):
    """캘린더 일간 뷰 → 예약 카드 찾기 + 클릭 (매출등록 코드와 동일)"""
    await runner.ensure_calendar_page()
    if "/book/calendar" not in runner.page.url:
        base = runner.base_url.replace("/signin", "")
        await runner.page.goto(f"{base}/book/calendar", wait_until="networkidle")
    await runner._move_calendar_to_today()
    await runner.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()
    await runner.page.wait_for_timeout(500)
    reserve_card = None
    for _ in range(8):
        reserve_card = runner.page.locator("div.BOOKING, div.SALE").filter(has_text=customer_name).first
        if await reserve_card.count() == 0:
            reserve_card = runner.page.get_by_text(customer_name, exact=True).first
        if await reserve_card.count() > 0 and await reserve_card.is_visible():
            break
        await runner.page.mouse.wheel(0, 400)
        await runner.page.wait_for_timeout(250)
    await expect(reserve_card).to_be_visible(timeout=5000)
    await reserve_card.click()
    await runner.page.wait_for_timeout(1000)


async def _get_photo_count_from_memo(runner):
    """예약 상세에서 최근 매출 메모 클릭 → (썸네일 개수, 깨진 이미지 수) 반환"""
    memo_btn = runner.page.locator("button:has-text('최근 매출 메모')").first
    await expect(memo_btn).to_be_visible(timeout=5000)
    await memo_btn.click()
    await runner.page.wait_for_timeout(2000)

    panel = runner.page.locator("#booking-item-total-history")
    await expect(panel).to_be_visible(timeout=5000)

    photos = panel.locator("img[alt^='최근 매출 메모 썸네일 이미지']")
    photo_count = await photos.count()

    # 이미지 로딩 대기: 모든 이미지가 complete될 때까지 polling
    for attempt in range(10):
        all_loaded = await runner.page.evaluate(
            """() => {
                const imgs = [...document.querySelectorAll('#booking-item-total-history img[alt^="최근 매출 메모 썸네일 이미지"]')];
                return imgs.every(img => img.complete && img.naturalWidth > 0);
            }"""
        )
        if all_loaded:
            break
        await runner.page.wait_for_timeout(1000)

    # 깨진 이미지 확인
    broken_count = 0
    for i in range(photo_count):
        is_broken = await photos.nth(i).evaluate(
            "img => !img.complete || img.naturalWidth === 0"
        )
        if is_broken:
            broken_count += 1

    return photo_count, broken_count


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


async def _wait_for_batch(runner, staff_name, expected_sales_count, max_retries=20, interval=30):
    """배치 반영 대기: 직원 통계에서 매출 건수가 기대값에 도달할 때까지 polling
    max_retries=20, interval=30초 → 최대 10분 대기 (배치 5분 주기 + 여유)
    """
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
            # 캘린더 페이지로 돌아간 뒤 다시 진입
            base = runner.base_url.replace("/signin", "")
            await runner.page.goto(f"{base}/book/calendar", wait_until="networkidle")

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


# ── 고객 통계 검증 테스트 ──

async def _open_customer_statistics(runner):
    """통계 > 고객 통계 자세히 보기 → 오늘 필터 적용"""
    await runner._open_statistics_page()
    await runner._open_stat_detail("고객 통계")
    await runner._apply_today_filter()


async def _get_customer_stat_row(table, customer_type):
    """고객 통계 테이블에서 고객 유형(재방문 고객/신규 고객/미등록 고객) 행 찾기"""
    rows = table.locator("tbody tr:visible")
    row_count = await rows.count()
    for i in range(row_count):
        r = rows.nth(i)
        text = await r.inner_text()
        if customer_type in text:
            return r
    return None


async def _open_channel_statistics(runner):
    """통계 > 채널별 매출 통계 자세히 보기 → 오늘 필터 적용"""
    await runner._open_statistics_page()
    await runner._open_stat_detail("채널별 매출 통계")
    await runner._apply_today_filter()


async def _get_grouped_table_values(table, group_name):
    """컬럼 그룹 헤더(공비서 원장님, 재방문 고객 등)의 시작 인덱스를 찾아
    해당 그룹의 td 값들을 순서대로 반환 (첫 번째 tbody 행 기준)"""
    # thead에서 그룹 헤더의 colspan 위치 계산
    values = await table.evaluate(
        """(args) => {
            const [groupName] = args;
            const headerRows = [...table.querySelectorAll('thead tr')];
            // 그룹 헤더가 있는 행 찾기
            let groupStartCol = -1;
            let groupColSpan = 0;
            for (const tr of headerRows) {
                let colIdx = 0;
                for (const th of tr.children) {
                    const text = (th.innerText || '').replace(/\\s+/g, ' ').trim();
                    const span = parseInt(th.getAttribute('colspan') || '1', 10);
                    if (text.includes(groupName)) {
                        groupStartCol = colIdx;
                        groupColSpan = span;
                        break;
                    }
                    colIdx += span;
                }
                if (groupStartCol >= 0) break;
            }
            if (groupStartCol < 0) return null;

            // 첫 번째 tbody 행에서 해당 범위의 td 추출
            // 날짜 컬럼(첫 번째 td)은 rowspan으로 그룹 헤더 행에 포함되지 않으므로
            // tbody td 인덱스에서 날짜 컬럼(1개)을 빼야 함
            const row = table.querySelector('tbody tr');
            if (!row) return null;
            const tds = [...row.querySelectorAll('td')];
            // 첫 번째 td는 날짜, 그 이후부터 그룹 순서대로
            // groupStartCol은 날짜 컬럼 이후 기준이므로 -1 보정 불필요 (thead에서 날짜 th도 포함)
            const result = [];
            for (let i = groupStartCol; i < groupStartCol + groupColSpan && i < tds.length; i++) {
                result.push((tds[i].innerText || '').replace(/\\s+/g, ' ').trim());
            }
            return result;
        }""",
        [group_name],
    )
    return values


async def _get_first_data_row_values(table):
    """조회 기간 합계 테이블의 첫 번째 tbody 행에서 모든 td 텍스트를 반환"""
    values = await table.evaluate(
        """(el) => {
            const row = el.querySelector('tbody tr');
            if (!row) return [];
            return [...row.querySelectorAll('td')].map(
                td => (td.innerText || '').replace(/\\s+/g, ' ').trim()
            );
        }"""
    )
    return values


async def test_channel_statistics(runner):
    """채널별 매출 통계 — 공비서 원장님 채널 매출 건수/실매출/차감 검증
    테이블 구조: 날짜 | 공비서 원장님(매출건수,실매출합계,차감합계) | 공비서(...) | 네이버예약(...)
    """
    await _open_channel_statistics(runner)

    # "조회 기간 합계" 테이블 (첫 번째 table)
    table = runner.page.locator("table:visible").first
    await expect(table).to_be_visible(timeout=5000)

    # 첫 번째 행의 모든 td 값 가져오기
    # 컬럼 순서: 날짜 | 공비서원장님(매출건수, 실매출합계, 차감합계) | 공비서(...) | 네이버예약(...)
    row_values = await _get_first_data_row_values(table)
    assert len(row_values) >= 4, f"채널별 매출 통계 컬럼 부족: {row_values}"

    def parse_int(text):
        m = re.search(r"([0-9][0-9,]*)", text.replace(",", ""))
        return int(m.group(1)) if m else 0

    # 공비서 원장님: index 1=매출건수, 2=실매출합계, 3=차감합계
    actual_count = parse_int(row_values[1])
    actual_sales = parse_int(row_values[2])
    actual_deduct = parse_int(row_values[3])

    assert actual_count == 7, f"채널별 매출 건수 불일치: 기대 7, 실제 {actual_count}"
    assert actual_sales == 320000, f"채널별 실매출 합계 불일치: 기대 320,000, 실제 {actual_sales:,}"
    assert actual_deduct == 50000, f"채널별 차감 합계 불일치: 기대 50,000, 실제 {actual_deduct:,}"

    print("✓ 채널별 매출 통계 검증 완료")
    print(f"  공비서 원장님: {actual_count}건 / 실매출 {actual_sales:,}원 / 차감 {actual_deduct:,}원")


async def test_customer_statistics(runner):
    """고객 통계 — 고객 유형별 매출 건수/실매출/객단가/차감금액 검증
    테이블 구조: 날짜 | 재방문고객(매출건수,실매출,객단가,차감금액,재방문율) | 신규고객(매출건수,실매출,객단가,차감금액,신규방문율) | 미등록고객(매출건수,실매출,객단가)
    """
    await _open_customer_statistics(runner)

    # "조회 기간 합계" 테이블
    table = runner.page.locator("table:visible").first
    await expect(table).to_be_visible(timeout=5000)

    row_values = await _get_first_data_row_values(table)

    def parse_int(text):
        m = re.search(r"([0-9][0-9,]*)", text.replace(",", ""))
        return int(m.group(1)) if m else 0

    # 스크린샷 기준 컬럼 순서 (조회 기간 합계):
    # 0=날짜 | 재방문고객: 1=매출건수, 2=실매출, 3=객단가, 4=차감금액, 5=재방문율
    #        | 신규고객: 6=매출건수, 7=실매출, 8=객단가, 9=차감금액, 10=신규방문율
    #        | 미등록고객: 11=매출건수, 12=실매출, 13=객단가

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
    print("  재방문: 1건/0원/0원/10,000원")
    print("  신규: 5건/310,000원/62,000원/40,000원")
    print("  미등록: 1건/10,000원/10,000원")


# ── 시간별 분석 검증 테스트 ──

def _build_hourly_expected(runner=None, non_reservation_hour=None):
    """시간별 기대값 생성

    예약 기반 매출 (예약 시간 고정):
      16시: sales_reg_1 → 실매출 0, 차감 20,000 (정액권차감), 총합계 20,000
      17시: sales_reg_2 → 실매출 0, 차감 20,000 (티켓차감), 총합계 20,000
      18시: sales_reg_3 → 실매출 10,000 (현금+카드), 차감 0, 총합계 10,000

    비예약 매출 (등록 시간 기준):
      정액권 충전 → 실매출 200,000, 차감 0
      티켓 충전   → 실매출 100,000, 차감 0
      미등록 제품 → 실매출 10,000, 차감 0
      패밀리 정액권 → 실매출 0, 차감 10,000
    """
    hourly = {}

    def add(hour, count, sales, deduct):
        if hour not in hourly:
            hourly[hour] = {"매출 건수": 0, "실매출": 0, "차감": 0}
        hourly[hour]["매출 건수"] += count
        hourly[hour]["실매출"] += sales
        hourly[hour]["차감"] += deduct

    # 예약 기반 (고정)
    add(16, 1, 0, 20000)
    add(17, 1, 0, 20000)
    add(18, 1, 10000, 0)

    # 비예약 시간 결정: runner에 기록된 시간 > 명시적 인자 > fallback
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

    # 총합계 계산
    for h in hourly:
        hourly[h]["총합계"] = hourly[h]["실매출"] + hourly[h]["차감"]

    return hourly


async def _get_all_data_rows(table):
    """테이블의 모든 tbody 행에서 td 텍스트 배열을 반환"""
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

    # 시간대 행을 dict로 변환: {16: [td0, td1, ...], ...}
    # 시간 형식: "오후 4:00 ~ 오후 5:00" → 시작 시간(16)으로 매핑
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

    # 셋업 없이 실행 시 비예약 시간이 기록 안 됨 → 실제 데이터에서 역산
    has_recorded_hours = hasattr(runner, "_membership_hour")
    if not has_recorded_hours:
        # 예약 시간(16,17,18) 외에서 매출이 있는 시간대를 찾기
        non_res_hour = None
        for hour in sorted(time_rows.keys()):
            if hour in (16, 17, 18):
                continue
            count = parse_int(time_rows[hour][1]) if len(time_rows[hour]) > 1 else 0
            if count > 0:
                non_res_hour = hour
                break
        # 비예약 매출이 예약 시간(18시)에 합산된 경우
        if non_res_hour is None:
            non_res_hour = 18
        hourly_expected = _build_hourly_expected(non_reservation_hour=non_res_hour)

    for hour, exp in hourly_expected.items():
        assert hour in time_rows, f"시간별 분석: {hour}시 행이 없습니다. (존재하는 시간: {list(time_rows.keys())})"
        row_vals = time_rows[hour]
        # 컬럼 순서: 시간 | 매출건수 | 실매출합계 | 차감합계 | 총합계
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
    for h in sorted(hourly_expected):
        e = hourly_expected[h]
        print(f"  {h}시: {e['매출 건수']}건 / 실매출 {e['실매출']:,}원 / 차감 {e['차감']:,}원 / 총합계 {e['총합계']:,}원")


# ── 요일별 분석 검증 테스트 ──

async def test_day_statistics(runner):
    """요일별 분석 — 오늘 요일 기준 매출 건수/실매출/차감/총합계 검증"""
    await runner._open_statistics_page()
    await runner._open_stat_detail("요일별 분석")
    await runner._apply_today_filter()

    table = runner.page.locator("table:visible").first
    await expect(table).to_be_visible(timeout=5000)

    # 오늘 요일 구하기
    day_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    today_day = day_names[datetime.now().weekday()]

    all_rows = await _get_all_data_rows(table)

    def parse_int(text):
        m = re.search(r"([0-9][0-9,]*)", text.replace(",", ""))
        return int(m.group(1)) if m else 0

    # 오늘 요일 행 찾기
    target_row = None
    for row_vals in all_rows:
        if row_vals and today_day in row_vals[0]:
            target_row = row_vals
            break

    assert target_row is not None, f"요일별 분석: '{today_day}' 행을 찾을 수 없습니다."

    # 컬럼 순서: 요일 | 매출건수 | 실매출합계 | 차감합계 | 총합계
    actual_count = parse_int(target_row[1]) if len(target_row) > 1 else 0
    actual_sales = parse_int(target_row[2]) if len(target_row) > 2 else 0
    actual_deduct = parse_int(target_row[3]) if len(target_row) > 3 else 0
    actual_total = parse_int(target_row[4]) if len(target_row) > 4 else 0

    assert actual_count == 7, f"요일별 [{today_day}] 매출 건수 불일치: 기대 7, 실제 {actual_count}"
    assert actual_sales == 320000, f"요일별 [{today_day}] 실매출 합계 불일치: 기대 320,000, 실제 {actual_sales:,}"
    assert actual_deduct == 50000, f"요일별 [{today_day}] 차감 합계 불일치: 기대 50,000, 실제 {actual_deduct:,}"
    assert actual_total == 370000, f"요일별 [{today_day}] 총합계 불일치: 기대 370,000, 실제 {actual_total:,}"

    print(f"✓ 요일별 분석 검증 완료 ({today_day})")
    print(f"  매출 건수: 7건 / 실매출: 320,000원 / 차감: 50,000원 / 총합계: 370,000원")


# ── 고객 차트 필터 검증 테스트 ──

async def _open_customer_chart(runner):
    """고객 > 고객차트 페이지 이동 (B2BAutomationV2 메서드 활용)"""
    await runner.focus_main_page()
    await runner._open_customer_chart()


async def _open_filter_condition(runner, condition_name):
    """조건 추가 버튼 → 조건 선택 모달에서 특정 조건 클릭"""
    add_btn = runner.page.locator("button:has(h5:has-text('조건 추가'))").first
    await expect(add_btn).to_be_visible(timeout=5000)
    await add_btn.click()
    await runner.page.wait_for_timeout(700)

    condition_btn = runner.page.locator(f"button:has-text('{condition_name}')").first
    await expect(condition_btn).to_be_visible(timeout=5000)
    await condition_btn.click()
    await runner.page.wait_for_timeout(700)


async def _get_chart_customer_names(runner):
    """고객 차트 결과 테이블 tbody에서 고객 이름 추출"""
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


async def _reset_filter(runner):
    """전체 재설정 버튼 클릭 + dimmer 닫기"""
    reset_btn = runner.page.locator("button:has(h4:has-text('전체 재설정'))").first
    if await reset_btn.count() > 0:
        await reset_btn.click()
        await runner.page.wait_for_timeout(700)
    # dimmer가 남아있으면 ESC로 닫기
    dimmer = runner.page.locator("#modal-dimmer.isActiveDimmed").first
    for _ in range(3):
        if await dimmer.count() > 0 and await dimmer.is_visible():
            await runner.page.keyboard.press("Escape")
            await runner.page.wait_for_timeout(500)
        else:
            break


async def test_customer_chart_filter_procedure(runner):
    """고객 차트 — 받은 시술 필터 검증 (그룹: 손, 시술: 젤 기본 → 자동화_1 노출)"""
    await _open_customer_chart(runner)
    await _open_filter_condition(runner, "받은 시술")

    # 그룹 선택: 손
    group_select = runner.page.locator("#cosmeticGroup button[data-testid='select-toggle-button']").first
    await expect(group_select).to_be_visible(timeout=5000)
    await group_select.click()
    await runner.page.wait_for_timeout(500)
    await runner.page.locator("#cosmeticGroup li:has-text('손')").first.click()
    await runner.page.wait_for_timeout(500)

    # 시술 선택: 젤 기본
    item_select = runner.page.locator("#cosmeticItem button[data-testid='select-toggle-button']").first
    await expect(item_select).to_be_visible(timeout=5000)
    await item_select.click()
    await runner.page.wait_for_timeout(500)
    await runner.page.locator("#cosmeticItem li:has-text('젤 기본')").first.click()
    await runner.page.wait_for_timeout(1000)

    # 결과 확인 (tbody 테이블 기준)
    customer_1 = f"자동화_{runner.mmdd}_1"
    names = await _get_chart_customer_names(runner)
    assert customer_1 in names, f"받은 시술(젤 기본) 필터 결과 테이블에 '{customer_1}' 미노출 (목록: {names})"
    print(f"✓ 받은 시술 필터 (손 > 젤 기본) → {customer_1} 노출 확인")

    # 케어 검증 — 조건 패널이 열려있으므로 시술 드롭다운만 변경
    item_select2 = runner.page.locator("#cosmeticItem button[data-testid='select-toggle-button']").first
    await expect(item_select2).to_be_visible(timeout=5000)
    await item_select2.click()
    await runner.page.wait_for_timeout(500)
    await runner.page.locator("#cosmeticItem li:has-text('케어')").first.click()
    await runner.page.wait_for_timeout(1000)

    customer_3 = f"자동화_{runner.mmdd}_3"
    names = await _get_chart_customer_names(runner)
    assert customer_3 in names, f"받은 시술(케어) 필터 결과 테이블에 '{customer_3}' 미노출 (목록: {names})"
    print(f"✓ 받은 시술 필터 (손 > 케어) → {customer_3} 노출 확인")


async def test_customer_chart_filter_staff(runner):
    """고객 차트 — 담당자 필터 검증 (샵주테스트 → 자동화_1,2,3 노출)"""
    await _open_customer_chart(runner)
    await _open_filter_condition(runner, "담당자")

    # 담당자 선택
    staff_select = runner.page.locator("#optionValues button[data-testid='select-toggle-button']").first
    await expect(staff_select).to_be_visible(timeout=5000)
    await staff_select.click()
    await runner.page.wait_for_timeout(500)

    staff_name = runner.owner_name  # 샵주테스트
    await runner.page.locator(f"button:has-text('{staff_name}'):visible, li:has-text('{staff_name}'):visible, [role='option']:has-text('{staff_name}'):visible").first.click()
    await runner.page.wait_for_timeout(1000)

    # 결과 확인 (tbody 테이블 기준)
    names = await _get_chart_customer_names(runner)
    for i in [1, 2, 3]:
        customer = f"자동화_{runner.mmdd}_{i}"
        assert customer in names, f"담당자({staff_name}) 필터 결과 테이블에 '{customer}' 미노출 (목록: {names})"

    print(f"✓ 담당자 필터 ({staff_name}) → 자동화_1,2,3 전체 노출 확인")


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

    await _send_slack(results)
