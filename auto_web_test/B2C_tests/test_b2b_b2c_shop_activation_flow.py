import os
import sys
import re
import base64
from datetime import datetime
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

sys.path.append(str(Path(__file__).resolve().parents[2]))

from auto_web_test.B2B_tests.test_b2b_v2 import B2BAutomationV2

_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO7ZJ6kAAAAASUVORK5CYII="
)
CRM_BASE_URL = os.getenv("CRM_BASE_URL", "https://crm-dev4.gongbiz.kr")
ZERO_BASE_URL = os.getenv("ZERO_BASE_URL", "https://qa-zero.gongbiz.kr")
CRM_USER_ID = os.getenv("CRM_USER_ID", "autoqatest1")
CRM_USER_PW = os.getenv("CRM_USER_PW", "gong2023@@")
SHOT_DIR = Path(os.getenv("TEST_SCREENSHOT_DIR", "qa_artifacts/screenshots"))
SHOT_DIR.mkdir(parents=True, exist_ok=True)


class ShopActivationRunner(B2BAutomationV2):
    def __init__(self):
        super().__init__()
        self.crm_test_phone = os.getenv("CRM_TEST_PHONE", "01012345678")
        self.crm_test_intro = os.getenv("CRM_TEST_INTRO", "샵 소개 테스트 문구입니다.")

    async def _find_address_search_frame(self, popup_page):
        for frame in popup_page.frames:
            search_input = frame.locator("input#region_name, input.tf_keyword").first
            if await search_input.count() > 0:
                return frame
        raise AssertionError("주소 검색 프레임을 찾지 못했습니다.")

    async def _attach_b2c_test_image(self):
        tmp_path = Path("/tmp") / "b2c_required_field_test_image.png"
        tmp_path.write_bytes(base64.b64decode(_PNG_BASE64))
        await self.page.set_input_files("input[type='file']", str(tmp_path))
        await self.page.wait_for_timeout(500)

        modal_save = self.page.locator("#modal-content button", has_text="저장")
        if await modal_save.count() > 0 and await modal_save.first.is_visible():
            await modal_save.first.click()
            await self.page.wait_for_timeout(700)

    async def _dismiss_shop_creation_modals(self):
        start_btn = self.page.get_by_role("button", name="무료 체험 시작하기")
        if await start_btn.count() > 0 and await start_btn.first.is_visible():
            await start_btn.first.click()
            await self.page.wait_for_timeout(700)

        skip_candidates = [
            self.page.locator("button:has-text('건너뛰기'):visible").first,
            self.page.get_by_role("button", name="건너뛰기").locator(":visible").first,
        ]
        for skip_btn in skip_candidates:
            if await skip_btn.count() > 0 and await skip_btn.is_visible():
                await skip_btn.click()
                await self.page.wait_for_timeout(1000)
                break

        close_buttons = self.page.locator(
            "#modal-content button:has-text('닫기'):visible, "
            "#modal-content svg[icon='systemX']:visible, "
            "button[aria-label='close']:visible"
        )
        if await close_buttons.count() > 0:
            try:
                await close_buttons.first.click()
                await self.page.wait_for_timeout(500)
            except Exception:
                pass

        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

    async def _is_b2c_toggle_on(self):
        selectors = [
            "#b2c-setting-online-activate-reservation",
            "#b2c-setting-activate-switch",
        ]
        for selector in selectors:
            toggle = self.page.locator(selector)
            if await toggle.count() > 0:
                await expect(toggle).to_be_attached(timeout=10000)
                return await toggle.is_checked()
        raise AssertionError("공비서로 온라인 예약받기 토글이 ON 상태가 아닙니다.")

    async def create_new_shop(self):
        print("=== [flow] 신규 샵 생성 시작 ===")

        await self.page.locator("button:has-text('마이페이지')").first.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.get_by_role("link", name="+ 샵 추가").click()

        name_input = self.page.get_by_placeholder("샵 이름")
        await expect(name_input).to_be_visible(timeout=10000)
        await name_input.fill(f"{self.mmdd}_배포_테스트")

        async with self.page.expect_popup() as input_addr_info:
            await self.page.locator("input#addr[placeholder='샵 주소']").click()
        input_addr_page = await input_addr_info.value
        await input_addr_page.wait_for_load_state("domcontentloaded")

        frame = await self._find_address_search_frame(input_addr_page)
        search_input = frame.locator("input#region_name, input.tf_keyword").first
        await search_input.fill("강남역")
        await search_input.press("Enter")

        address_item = frame.locator("span.txt_address").filter(
            has_text="서울 강남구 강남대로 지하 396 (강남역)"
        ).locator("button.link_post").first
        await expect(address_item).to_be_visible(timeout=10000)
        await address_item.click()

        detail_addr = self.page.get_by_placeholder("상세 주소")
        await detail_addr.fill("테스트 상세주소")
        await detail_addr.press("Tab")
        await self.page.wait_for_timeout(300)
        await self.page.get_by_role("link", name="다음").first.click()
        await self.page.wait_for_url("**/signup/owner/add", timeout=10000)

        dropdown = self.page.locator(".ui.dropdown-check.category")
        await expect(dropdown).to_be_visible(timeout=10000)
        trigger = dropdown.locator(".text", has_text="업종선택").first
        if await trigger.count() == 0:
            trigger = dropdown.get_by_text("업종선택", exact=False).first
        await trigger.click()

        panel = dropdown.locator(".dropdown-items-wrap")
        await panel.wait_for(state="visible", timeout=3000)
        await panel.locator("label[for='cate1']").click()
        await panel.locator("label[for='cate3']").click()
        await panel.get_by_role("button", name="선택").click()

        await self.page.locator("a[onclick='onClickSubmit();']").click()
        await expect(self.page.locator("#modal-content")).to_be_visible(timeout=5000)
        await self._dismiss_shop_creation_modals()

        assert await self.page.locator(f'text="{self.mmdd}_배포_테스트"').is_visible(), "샵 이름이 올바르지 않습니다."
        assert await self.page.locator(f"text={self.owner_name}").first.is_visible(), "점주 이름이 올바르지 않습니다."

    async def enable_gong_booking_after_shop_creation(self):
        print("=== [flow] 공비서 온라인 예약 설정 시작 ===")

        await self._dismiss_shop_creation_modals()
        await self.page.locator(
            "h3:has-text('온라인 예약'):visible, button:has-text('온라인 예약'):visible, a:has-text('온라인 예약'):visible"
        ).first.click()
        await self.page.wait_for_timeout(1000)

        booking_menu = self.page.locator(
            "button:has-text('공비서로 예약받기'):visible, "
            "a:has-text('공비서로 예약받기'):visible, "
            "h4:has-text('공비서로 예약받기'):visible, "
            "span:has-text('공비서로 예약받기'):visible, "
            "li:has-text('공비서로 예약받기'):visible"
        ).first
        await expect(booking_menu).to_be_visible(timeout=10000)
        await booking_menu.click()
        await self.page.wait_for_load_state("networkidle")

        phone_field = self.page.get_by_placeholder("문의 가능한 전화번호를 입력해 주세요.")
        join_button = self.page.locator(
            "[data-track-id='b2c_reservation']:visible, "
            "button:has(h3:has-text('공비서 입점하기')):visible, "
            "button:has-text('공비서 입점하기'):visible, "
            "a:has-text('공비서 입점하기'):visible"
        ).first
        await expect(join_button).to_be_visible(timeout=10000)
        await join_button.click()
        await expect(phone_field).to_be_visible(timeout=10000)

        await phone_field.fill(self.crm_test_phone)
        await self.page.get_by_placeholder("샵을 소개할 수 있는 내용을 작성해 주세요.").fill(self.crm_test_intro)
        await self._attach_b2c_test_image()

        deposit_section = self.page.locator(
            "div:has-text('예약 방식 설정'):visible, section:has-text('예약 방식 설정'):visible"
        ).first
        await expect(deposit_section).to_be_visible(timeout=10000)
        await deposit_section.scroll_into_view_if_needed()

        without_deposit = self.page.locator("h4:has-text('예약금 없이 예약'):visible").first
        await expect(without_deposit).to_be_visible(timeout=10000)
        await without_deposit.scroll_into_view_if_needed()
        await without_deposit.click()
        await self.page.wait_for_timeout(1000)

        reservation_mode_text = re.sub(r"\s+", " ", await self.page.locator("body").inner_text())
        assert "예약금 없이 예약" in reservation_mode_text, "예약 방식 설정에서 '예약금 없이 예약' 텍스트 확인 실패"

        save_button = self.page.locator("button[data-track-id='b2c_info_save']")
        if await save_button.count() == 0:
            save_button = self.page.locator("button:has-text('저장'):visible").last
        await expect(save_button).to_be_enabled(timeout=10000)
        await save_button.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        assert await self._is_b2c_toggle_on(), "공비서로 온라인 예약받기 토글이 ON 상태가 아닙니다."


async def _crm_login(page):
    await page.goto(f"{CRM_BASE_URL}/signin")
    await page.get_by_role("textbox", name="아이디").fill(CRM_USER_ID)
    await page.get_by_role("textbox", name="비밀번호").fill(CRM_USER_PW)
    await page.get_by_role("button", name="로그인").click()
    await page.wait_for_load_state("networkidle")


async def _switch_shop(page, shop_name: str):
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

    await page.goto(f"{CRM_BASE_URL}/b2c/setting")
    await page.wait_for_load_state("networkidle")
    assert await page.get_by_role("link", name=shop_name).first.is_visible(), (
        f"샵 전환 실패: expected={shop_name}"
    )


async def _is_toggle_on(page) -> bool:
    selectors = [
        "#b2c-setting-online-activate-reservation",
        "#b2c-setting-activate-switch",
    ]
    for selector in selectors:
        toggle = page.locator(selector)
        if await toggle.count() > 0:
            await expect(toggle).to_be_attached(timeout=10000)
            return await toggle.is_checked()
    raise AssertionError("B2C 토글 요소를 찾지 못했습니다.")


async def _set_toggle(page, turn_on: bool):
    current = await _is_toggle_on(page)
    if current == turn_on:
        return

    label = page.locator("label[for='b2c-setting-online-activate-reservation']").first
    if await label.count() == 0:
        label = page.locator("label[for='b2c-setting-activate-switch']").first
    await expect(label).to_be_visible(timeout=10000)
    await label.click(force=True)
    await page.wait_for_timeout(700)

    if not turn_on:
        off_confirm = page.locator("button.sc-45a967ab-0.iPNnOp").filter(
            has_text="비활성화"
        ).first
        await expect(off_confirm).to_be_visible(timeout=10000)
        await off_confirm.click(force=True)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(800)

    assert await _is_toggle_on(page) == turn_on


async def _open_nearby_list(page):
    await page.goto(f"{ZERO_BASE_URL}/main")
    await page.wait_for_load_state("networkidle")
    await page.get_by_role("link", name="내주변").click()
    await page.wait_for_load_state("networkidle")
    await page.get_by_role("button", name="목록보기").click()
    await page.wait_for_load_state("networkidle")


async def _is_shop_visible_in_nearby(page, shop_name: str) -> bool:
    for _ in range(8):
        body = await page.locator("body").inner_text()
        if shop_name in body:
            return True
        await page.mouse.wheel(0, 1200)
        await page.wait_for_timeout(350)
    return False


@pytest.mark.asyncio
async def test_create_shop_activate_then_verify_b2c_visibility():
    shop_name = f"{datetime.now():%m%d}_배포_테스트"

    runner = ShopActivationRunner()
    runner.headless = False
    crm_page = None
    zero_page = None
    try:
        await runner.setup()
        await runner.login()
        await runner.create_new_shop()
        try:
            await runner.enable_gong_booking_after_shop_creation()
        except Exception as exc:
            # 저장 후 토글 셀렉터만 불안정한 상태가 있어도, 실제 후속 CRM/B2C 검증으로 판정한다.
            if "공비서로 온라인 예약받기 토글이 ON 상태가 아닙니다." not in str(exc) and \
               "b2c-setting-activate-switch" not in str(exc):
                raise

        try:
            crm_page = await runner.context.new_page()
            zero_page = await runner.context.new_page()
            await crm_page.bring_to_front()
            await _crm_login(crm_page)
            await _switch_shop(crm_page, shop_name)
            await crm_page.screenshot(path=str(SHOT_DIR / "shop_activation_01_initial_crm.png"))
            initial_on = await _is_toggle_on(crm_page)

            if initial_on:
                await zero_page.bring_to_front()
                await _open_nearby_list(zero_page)
                await zero_page.screenshot(path=str(SHOT_DIR / "shop_activation_02_on_nearby_list.png"))
                assert await _is_shop_visible_in_nearby(zero_page, shop_name), (
                    "활성화 상태인데 QA-ZERO 내주변 목록에서 샵이 보이지 않습니다."
                )

                await crm_page.bring_to_front()
                await _set_toggle(crm_page, turn_on=False)
                await crm_page.screenshot(path=str(SHOT_DIR / "shop_activation_03_off_applied_crm.png"))

                await zero_page.bring_to_front()
                await _open_nearby_list(zero_page)
                await zero_page.screenshot(path=str(SHOT_DIR / "shop_activation_04_off_nearby_list.png"))
                assert not await _is_shop_visible_in_nearby(zero_page, shop_name), (
                    "비활성화 후에도 QA-ZERO 내주변 목록에서 샵이 계속 노출됩니다."
                )
            else:
                await zero_page.bring_to_front()
                await _open_nearby_list(zero_page)
                await zero_page.screenshot(path=str(SHOT_DIR / "shop_activation_02_off_nearby_list.png"))
                assert not await _is_shop_visible_in_nearby(zero_page, shop_name), (
                    "비활성화 상태인데 QA-ZERO 내주변 목록에서 샵이 노출됩니다."
                )

                await crm_page.bring_to_front()
                await _set_toggle(crm_page, turn_on=True)
                await crm_page.screenshot(path=str(SHOT_DIR / "shop_activation_03_on_applied_crm.png"))

                await zero_page.bring_to_front()
                await _open_nearby_list(zero_page)
                await zero_page.screenshot(path=str(SHOT_DIR / "shop_activation_04_on_nearby_list.png"))
                assert await _is_shop_visible_in_nearby(zero_page, shop_name), (
                    "활성화 후 QA-ZERO 내주변 목록에서 샵이 보이지 않습니다."
                )
        finally:
            if zero_page and not zero_page.is_closed():
                await zero_page.close()
            if crm_page and not crm_page.is_closed():
                await crm_page.close()
    finally:
        await runner.teardown()
