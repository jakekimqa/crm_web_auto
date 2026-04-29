"""매출등록 사진 저장 확인 — 매출 1,3에 각 10장씩 등록되었는지 검증
캘린더 → 예약 클릭 → 예약 상세 → 최근 매출 메모 → 썸네일 이미지 개수 확인
"""
import pytest
import pytest_asyncio
from playwright.async_api import expect

from auto_web_test.B2B_tests.test_b2b_v2 import B2BAutomationV2

pytestmark = pytest.mark.asyncio(loop_scope="module")

EXPECTED_PHOTO_COUNT = 10


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
    await runner.page.goto(f"{base}/book/calendar", wait_until="networkidle")
    await runner.page.wait_for_load_state("networkidle")
    yield


async def _open_reservation_detail(runner, customer_name):
    """캘린더에서 예약 카드 클릭 → 예약 상세 페이지 진입"""
    await runner._move_calendar_to_today()
    await runner.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()
    await runner.page.wait_for_timeout(500)

    reserve_card = None
    for _ in range(8):
        reserve_card = runner.page.locator("div.BOOKING.booking-normal").filter(has_text=customer_name).first
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
    """예약 상세에서 최근 매출 메모 클릭 → 썸네일 이미지 개수 반환"""
    memo_btn = runner.page.locator("p:has-text('최근 매출 메모')").first
    await expect(memo_btn).to_be_visible(timeout=5000)
    await memo_btn.click()
    await runner.page.wait_for_timeout(1000)

    # 최근 매출 메모 패널에서 썸네일 이미지 개수 확인
    panel = runner.page.locator("#booking-item-total-history")
    await expect(panel).to_be_visible(timeout=5000)

    photo_count = await panel.locator("img[alt^='최근 매출 메모 썸네일 이미지']").count()
    return photo_count


async def test_verify_photos_sales_1(runner):
    """매출 1 (자동화_1) — 캘린더 예약 상세 → 최근 매출 메모 → 사진 10장 확인"""
    customer = f"자동화_{runner.mmdd}_1"
    await _open_reservation_detail(runner, customer)

    photo_count = await _get_photo_count_from_memo(runner)
    print(f"✓ {customer} 사진 개수: {photo_count}장")
    assert photo_count == EXPECTED_PHOTO_COUNT, (
        f"{customer} 사진 개수 불일치: 기대 {EXPECTED_PHOTO_COUNT}장, 실제 {photo_count}장"
    )


async def test_verify_photos_sales_3(runner):
    """매출 3 (자동화_3) — 캘린더 예약 상세 → 최근 매출 메모 → 사진 10장 확인"""
    customer = f"자동화_{runner.mmdd}_3"
    await _open_reservation_detail(runner, customer)

    photo_count = await _get_photo_count_from_memo(runner)
    print(f"✓ {customer} 사진 개수: {photo_count}장")
    assert photo_count == EXPECTED_PHOTO_COUNT, (
        f"{customer} 사진 개수 불일치: 기대 {EXPECTED_PHOTO_COUNT}장, 실제 {photo_count}장"
    )
