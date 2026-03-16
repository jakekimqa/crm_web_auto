"""직원 입사 신청 → 원장 승인 테스트
1. 직원 계정(autoqatest2)으로 로그인 → 마이페이지 → 샵 추가 → 입사 신청
2. 원장 계정(autoqatest1)으로 로그인 → 직원관리 → 승인
"""
import os
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from pathlib import Path
from playwright.async_api import async_playwright, expect

load_dotenv(Path(__file__).parent.parent / ".env.dev", override=True)
os.environ["B2B_BASE_URL"] = "https://crm-dev5.gongbiz.kr/signin"
os.environ["B2B_HEADLESS"] = "1"

STAFF_ID = "autoqatest2"
STAFF_PW = "gong2023@@"
OWNER_ID = "autoqatest1"
OWNER_PW = "gong2023@@"
TARGET_SHOP = "0315_1202_배포_테스트"
BASE_URL = "https://crm-dev5.gongbiz.kr"

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module")
async def pw():
    p = await async_playwright().start()
    yield p
    await p.stop()


async def _login(pw_instance, user_id, password):
    """로그인 후 page 반환"""
    browser = await pw_instance.chromium.launch(headless=True)
    context = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await context.new_page()
    await page.goto(f"{BASE_URL}/signin")
    await page.wait_for_load_state("networkidle")

    id_input = page.locator("input[type='text'], input[name*='id'], input[placeholder*='아이디']").first
    await id_input.fill(user_id)
    pw_input = page.locator("input[type='password']").first
    await pw_input.fill(password)
    login_btn = page.locator("button:has-text('로그인'), button[type='submit']").first
    await login_btn.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)
    print(f"✓ {user_id} 로그인 완료 → {page.url}")
    return browser, context, page


async def test_staff_join_request(pw):
    """직원 계정으로 샵 입사 신청"""
    browser, context, page = await _login(pw, STAFF_ID, STAFF_PW)
    try:
        # 마이페이지 확인
        await expect(page.locator("div.title-xxl:has-text('마이페이지'), h1:has-text('마이페이지')").first).to_be_visible(timeout=5000)
        print("✓ 마이페이지 진입")

        # 이미 신청된 상태인지 확인
        existing = page.locator(f"tr:has-text('{TARGET_SHOP}')")
        if await existing.count() > 0:
            status = await existing.locator("td.status").text_content()
            print(f"ℹ 이미 등록됨: {TARGET_SHOP} → 상태: {status.strip()}")
            if "승인 전" in status:
                print("✓ 이미 입사 신청 완료 상태 (가입 승인 전)")
                return
            elif "승인" in status:
                print("✓ 이미 승인 완료 상태")
                return

        # [+ 샵 추가] 클릭
        add_shop_btn = page.locator("button:has-text('샵 추가'), a:has-text('샵 추가')").first
        await expect(add_shop_btn).to_be_visible(timeout=5000)
        await add_shop_btn.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)
        print("✓ 샵 추가 클릭")
        await page.screenshot(path="qa_artifacts/screenshots/staff_join_04_search.png")

        # 샵 이름 검색
        search_input = page.locator("input[type='text'], input[placeholder*='검색'], input[placeholder*='샵']").first
        await expect(search_input).to_be_visible(timeout=5000)
        await search_input.click()
        await search_input.type(TARGET_SHOP, delay=50)
        await page.wait_for_timeout(1500)
        await page.screenshot(path="qa_artifacts/screenshots/staff_join_05_search_result.png")

        # 검색 결과에서 샵 클릭
        shop_item = page.locator(f"text={TARGET_SHOP}").first
        await expect(shop_item).to_be_visible(timeout=5000)
        await shop_item.click()
        await page.wait_for_timeout(1000)
        print(f"✓ {TARGET_SHOP} 선택")
        await page.screenshot(path="qa_artifacts/screenshots/staff_join_06_modal.png")

        # "근무지 등록" 모달 → [다음] 클릭
        modal_next = page.locator("button:has-text('다음'), a:has-text('다음')").last
        await expect(modal_next).to_be_visible(timeout=5000)
        await modal_next.click()
        await page.wait_for_timeout(1000)
        print("✓ 근무지 등록 모달 [다음] 클릭")
        await page.screenshot(path="qa_artifacts/screenshots/staff_join_07_after_modal.png")

        # 하단 파란색 [다음] 버튼 클릭
        page_next = page.locator("button:has-text('다음'), a:has-text('다음')").first
        await expect(page_next).to_be_visible(timeout=5000)
        await page_next.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1500)
        print("✓ 화면 [다음] 클릭")

        # 마이페이지로 이동 → "가입 승인 전" 확인
        shop_row = page.locator(f"tr:has-text('{TARGET_SHOP}')")
        await expect(shop_row).to_be_visible(timeout=5000)
        status = await shop_row.locator("td.status").text_content()
        assert "승인 전" in status, f"상태 확인 실패: {status}"
        print(f"✓ 입사 신청 완료 → 상태: {status.strip()}")
        await page.screenshot(path="qa_artifacts/screenshots/staff_join_08_pending.png", full_page=True)

    finally:
        await browser.close()


async def test_owner_approve_staff(pw):
    """원장 계정으로 직원 승인"""
    browser, context, page = await _login(pw, OWNER_ID, OWNER_PW)
    try:
        # 원장 마이페이지에서 해당 샵으로 이동
        shop_link = page.locator(f"tr:has-text('{TARGET_SHOP}')").locator("a:has-text('샵으로 이동')").first
        if await shop_link.count() > 0:
            await shop_link.click()
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1000)
            print(f"✓ {TARGET_SHOP} 샵 진입: {page.url}")
        else:
            # 직접 샵 클릭
            shop_item = page.locator(f"text={TARGET_SHOP}").first
            if await shop_item.count() > 0:
                await shop_item.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1000)
            print(f"✓ 샵 진입 시도: {page.url}")

        await page.screenshot(path="qa_artifacts/screenshots/staff_join_09_owner_after_shop.png")

        # 우리샵 관리 > 직원관리
        await page.locator("text=우리샵 관리").first.click()
        await page.wait_for_timeout(500)
        await page.locator("text=직원관리").first.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)
        print(f"✓ 직원관리 페이지 진입: {page.url}")
        await page.screenshot(path="qa_artifacts/screenshots/staff_join_09_owner_staff.png", full_page=True)

        # 테스트_직원계정1 이름 확인
        staff_name = page.locator("tr:has-text('테스트_직원계정1')")
        await expect(staff_name).to_be_visible(timeout=5000)
        print("✓ 테스트_직원계정1 직원 확인")

        # [승인 대기] 버튼 클릭
        approve_btn = staff_name.locator("button:has-text('승인 대기')")
        await expect(approve_btn).to_be_visible(timeout=5000)
        await approve_btn.click()
        await page.wait_for_timeout(1000)
        await page.screenshot(path="qa_artifacts/screenshots/staff_join_10_approve_modal.png")
        print("✓ 승인 대기 버튼 클릭 → 모달 노출")

        # 입사 승인 모달 → [승인] 버튼 클릭
        modal_approve = page.locator("button:has-text('승인')").last
        await expect(modal_approve).to_be_visible(timeout=5000)
        await modal_approve.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)
        await page.screenshot(path="qa_artifacts/screenshots/staff_join_11_approved.png", full_page=True)
        print("✓ 직원 승인 완료")

        # 입사일이 오늘 날짜인지 확인
        from datetime import datetime
        today = datetime.now().strftime("%y. %-m. %-d")
        staff_row = page.locator("tr:has-text('테스트_직원계정1')")
        row_text = await staff_row.text_content()
        assert today in row_text, f"입사일 확인 실패: '{today}' not in '{row_text}'"
        print(f"✓ 입사일 확인: {today}")

    finally:
        await browser.close()
