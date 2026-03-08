import os
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect


CRM_BASE_URL = os.getenv("CRM_BASE_URL", "https://crm-dev6.gongbiz.kr")
ZERO_BASE_URL = os.getenv("ZERO_BASE_URL", "https://qa-zero.gongbiz.kr")
SHOP_NAME = os.getenv("CRM_SHOP_NAME", "미입점_샵생성")
CRM_USER_ID = os.getenv("CRM_USER_ID", "jaketest")
CRM_USER_PW = os.getenv("CRM_USER_PW", "gong2023@@")

SHOT_DIR = Path(os.getenv("TEST_SCREENSHOT_DIR", "qa_artifacts/screenshots"))
SHOT_DIR.mkdir(parents=True, exist_ok=True)


async def _crm_login(page):
    await page.goto(f"{CRM_BASE_URL}/signin")
    await page.get_by_role("textbox", name="아이디").fill(CRM_USER_ID)
    await page.get_by_role("textbox", name="비밀번호").fill(CRM_USER_PW)
    await page.get_by_role("button", name="로그인").click()
    await page.wait_for_load_state("networkidle")


async def _switch_shop(page, shop_name: str):
    # 로그인 직후 마이페이지(샵 리스트)로 이동해서
    # 대상 샵 카드의 [샵으로 이동] 버튼으로 진입한다.
    await page.goto(f"{CRM_BASE_URL}/mypage/owner")
    await page.wait_for_load_state("networkidle")

    moved = False
    for _ in range(3):
        shop_move_btn = page.locator(
            f"xpath=//*[contains(normalize-space(),'{shop_name}')]/following::a[contains(normalize-space(),'샵으로 이동')][1]"
        )
        if await shop_move_btn.count() > 0 and await shop_move_btn.first.is_visible():
            await shop_move_btn.first.click()
            await page.wait_for_load_state("networkidle")
            moved = True
            break
        await page.reload()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(700)

    assert moved, f"샵 리스트에서 [샵으로 이동] 버튼 탐색 실패: {shop_name}"

    # 대상 메뉴로 이동 후 상단 샵명으로 재확인
    await page.goto(f"{CRM_BASE_URL}/b2c/setting")
    await page.wait_for_load_state("networkidle")
    assert await page.get_by_role("link", name=shop_name).first.is_visible(), (
        f"샵 전환 실패: expected={shop_name}"
    )


async def _is_toggle_on(page) -> bool:
    toggle = page.locator("#b2c-setting-activate-switch")
    await expect(toggle).to_be_attached(timeout=10000)
    return await toggle.is_checked()


async def _set_toggle(page, turn_on: bool):
    current = await _is_toggle_on(page)
    if current == turn_on:
        return

    # hidden input 대신 연결 label 클릭
    await page.click("label[for='b2c-setting-activate-switch']")
    await page.wait_for_timeout(700)

    # OFF 전환 시 뜨는 모달 처리
    off_confirm = page.get_by_role("button", name="예약받기 비활성화")
    if await off_confirm.count() > 0 and await off_confirm.first.is_visible():
        await off_confirm.first.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(800)

    # 상태 검증
    assert await _is_toggle_on(page) == turn_on


async def _open_nearby_list(page):
    await page.goto(f"{ZERO_BASE_URL}/main")
    await page.wait_for_load_state("networkidle")
    await page.get_by_role("link", name="내주변").click()
    await page.wait_for_load_state("networkidle")
    await page.get_by_role("button", name="목록보기").click()
    await page.wait_for_load_state("networkidle")


async def _is_shop_visible_in_nearby(page, shop_name: str) -> bool:
    # 목록이 지연 렌더링/가상 스크롤일 수 있어 여러 번 스캔한다.
    for _ in range(8):
        body = await page.locator("body").inner_text()
        if shop_name in body:
            return True
        await page.mouse.wheel(0, 1200)
        await page.wait_for_timeout(350)
    return False


@pytest.mark.asyncio
async def test_dev6_toggle_and_qa_zero_visibility_sync():
    """
    분기형 시나리오:
    1.1 토글 ON이면: QA-ZERO 노출 확인 -> OFF -> QA-ZERO 미노출 확인
    1.2 토글 OFF면: QA-ZERO 미노출 확인 -> ON -> QA-ZERO 노출 확인
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=200)
        context = await browser.new_context(
            viewport={"width": 1600, "height": 1000},
            geolocation={"latitude": 37.4981, "longitude": 127.0276},
            permissions=["geolocation"],
        )
        crm_page = await context.new_page()
        zero_page = await context.new_page()

        try:
            await _crm_login(crm_page)
            await _switch_shop(crm_page, SHOP_NAME)

            await crm_page.screenshot(path=str(SHOT_DIR / "toggle_branch_01_initial_crm.png"))
            initial_on = await _is_toggle_on(crm_page)

            if initial_on:
                # 1.1 ON 분기
                await _open_nearby_list(zero_page)
                await zero_page.screenshot(path=str(SHOT_DIR / "toggle_branch_02_on_nearby_list.png"))
                assert await _is_shop_visible_in_nearby(zero_page, SHOP_NAME), (
                    "토글 ON 상태인데 QA-ZERO 내주변 목록에서 샵이 보이지 않습니다."
                )

                await _set_toggle(crm_page, turn_on=False)
                await crm_page.screenshot(path=str(SHOT_DIR / "toggle_branch_03_off_applied_crm.png"))

                await _open_nearby_list(zero_page)
                await zero_page.screenshot(path=str(SHOT_DIR / "toggle_branch_04_off_nearby_list.png"))
                assert not await _is_shop_visible_in_nearby(zero_page, SHOP_NAME), (
                    "토글 OFF 상태인데 QA-ZERO 내주변 목록에서 샵이 계속 노출됩니다."
                )

            else:
                # 1.2 OFF 분기
                await _open_nearby_list(zero_page)
                await zero_page.screenshot(path=str(SHOT_DIR / "toggle_branch_02_off_nearby_list.png"))
                assert not await _is_shop_visible_in_nearby(zero_page, SHOP_NAME), (
                    "토글 OFF 상태인데 QA-ZERO 내주변 목록에 샵이 노출됩니다."
                )

                await _set_toggle(crm_page, turn_on=True)
                await crm_page.screenshot(path=str(SHOT_DIR / "toggle_branch_03_on_applied_crm.png"))

                await _open_nearby_list(zero_page)
                await zero_page.screenshot(path=str(SHOT_DIR / "toggle_branch_04_on_nearby_list.png"))
                assert await _is_shop_visible_in_nearby(zero_page, SHOP_NAME), (
                    "토글 ON 상태인데 QA-ZERO 내주변 목록에서 샵이 보이지 않습니다."
                )

        finally:
            await context.close()
            await browser.close()
