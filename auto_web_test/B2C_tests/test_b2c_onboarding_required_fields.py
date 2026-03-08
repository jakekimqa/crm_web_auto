import base64
import os
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect


# 1x1 PNG
_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7ZJ6kAAAAASUVORK5CYII="
)


async def _ensure_logged_in(page, base_url: str, user_id: str, user_pw: str) -> None:
    await page.goto(f"{base_url}/signin")
    await page.get_by_role("textbox", name="아이디").fill(user_id)
    await page.get_by_role("textbox", name="비밀번호").fill(user_pw)
    await page.get_by_role("button", name="로그인").click()
    await page.wait_for_load_state("networkidle")


async def _switch_shop(page, shop_name: str) -> None:
    await page.goto("https://crm-dev1.gongbiz.kr/book/calendar")
    await page.wait_for_load_state("networkidle")

    # 샵 선택 패널 열기
    await page.locator("header button").first.click()
    await page.wait_for_timeout(500)

    # 샵 전환
    await page.get_by_text(shop_name, exact=True).first.click()
    await page.wait_for_load_state("networkidle")


async def _open_b2c_form(page, base_url: str) -> None:
    await page.goto(f"{base_url}/b2c/setting")
    await page.wait_for_load_state("networkidle")

    phone_field = page.get_by_placeholder("문의 가능한 전화번호를 입력해 주세요.")
    if await phone_field.count() > 0 and await phone_field.first.is_visible():
        return

    join_button = page.get_by_role("button", name="공비서 입점하기")
    if await join_button.count() > 0 and await join_button.first.is_visible():
        await join_button.first.click()
        await expect(phone_field).to_be_visible(timeout=10000)
        return

    # 이미 입점 신청된 상태 등에서 '수정하기'로 진입
    edit_in_online_info = page.locator(
        "xpath=//*[contains(normalize-space(), '온라인 예약 정보')]/following::button[normalize-space()='수정하기'][1]"
    )
    await edit_in_online_info.first.click()
    await expect(phone_field).to_be_visible(timeout=10000)


async def _attach_test_image(page) -> None:
    tmp_path = Path("/tmp") / "b2c_required_field_test_image.png"
    tmp_path.write_bytes(base64.b64decode(_PNG_BASE64))

    await page.set_input_files("input[type='file']", str(tmp_path))
    await page.wait_for_timeout(500)

    modal_save = page.locator("#modal-content button", has_text="저장")
    if await modal_save.count() > 0 and await modal_save.first.is_visible():
        await modal_save.first.click()
        await page.wait_for_timeout(700)


@pytest.mark.asyncio
async def test_b2c_onboarding_required_fields_matrix():
    """
    필수 3개 항목 매트릭스 검증:
    - 예약 상담 가능 번호
    - 소개글
    - 샵 소개 이미지
    """

    base_url = os.getenv("CRM_BASE_URL", "https://crm-dev1.gongbiz.kr")
    user_id = os.getenv("CRM_USER_ID")
    user_pw = os.getenv("CRM_USER_PW")
    shop_name = os.getenv("CRM_SHOP_NAME", "샵 새성")

    phone_value = os.getenv("CRM_TEST_PHONE", "01012345678")
    intro_value = os.getenv("CRM_TEST_INTRO", "샵 소개 테스트 문구입니다.")

    if not user_id or not user_pw:
        pytest.skip("Set CRM_USER_ID and CRM_USER_PW to run this test.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=200)
        context = await browser.new_context(viewport={"width": 1600, "height": 1000})
        page = await context.new_page()

        try:
            await _ensure_logged_in(page, base_url, user_id, user_pw)
            await _switch_shop(page, shop_name)
            await _open_b2c_form(page, base_url)

            save_button = page.locator("button[data-track-id='b2c_info_save']")
            phone = page.get_by_placeholder("문의 가능한 전화번호를 입력해 주세요.")
            intro = page.get_by_placeholder("샵을 소개할 수 있는 내용을 작성해 주세요.")

            # RF-001: none
            await phone.fill("")
            await intro.fill("")
            await expect(save_button).to_be_disabled()

            # RF-002: phone + intro, no image
            await phone.fill(phone_value)
            await intro.fill(intro_value)
            await expect(save_button).to_be_disabled()

            # RF-003: phone + intro + image
            await _attach_test_image(page)
            await expect(save_button).to_be_enabled()

            # RF-004: remove phone
            await phone.fill("")
            await expect(save_button).to_be_disabled()

            # RF-005: restore phone, remove intro
            await phone.fill(phone_value)
            await intro.fill("")
            await expect(save_button).to_be_disabled()

        finally:
            await context.close()
            await browser.close()
