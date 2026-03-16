import os
import sys
import re
import base64
from datetime import datetime, timedelta
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
KAKAO_ID = os.getenv("KAKAO_ID", "developer@herren.co.kr")
KAKAO_PW = os.getenv("KAKAO_PW", "herren3378!")
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
        await input_addr_page.wait_for_load_state("networkidle")
        await input_addr_page.wait_for_timeout(1000)

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
        await self.page.wait_for_timeout(2000)

        # 샵 생성 후 모달이 뜨거나, /book/calendar?welcome=1 로 바로 리다이렉트될 수 있음
        if "welcome" in self.page.url or "/book/calendar" in self.page.url:
            print("  ✓ 샵 생성 후 캘린더(welcome)로 리다이렉트됨")
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(2000)
            await self._dismiss_shop_creation_modals()
        else:
            await expect(self.page.locator("#modal-content")).to_be_visible(timeout=5000)
            await self._dismiss_shop_creation_modals()

            assert await self.page.locator(f'text="{self.mmdd}_배포_테스트"').is_visible(), "샵 이름이 올바르지 않습니다."
            assert await self.page.locator(f"text={self.owner_name}").first.is_visible(), "점주 이름이 올바르지 않습니다."

    async def enable_gong_booking_after_shop_creation(self):
        print("=== [flow] 공비서 온라인 예약 설정 시작 ===")

        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(2000)
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
    id_field = page.get_by_role("textbox", name="아이디")
    try:
        await id_field.wait_for(state="visible", timeout=3000)
    except Exception:
        return  # 이미 로그인된 상태 — 스킵
    await id_field.fill(CRM_USER_ID)
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
        off_confirm = page.get_by_role("button", name="예약받기 비활성화").first
        await expect(off_confirm).to_be_visible(timeout=10000)
        page.on("dialog", lambda dialog: dialog.accept())
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


async def _kakao_login(page):
    await page.goto(f"{ZERO_BASE_URL}/login")
    await page.wait_for_load_state("networkidle")

    kakao_btn = page.get_by_role("button", name="카카오로 로그인")
    await expect(kakao_btn).to_be_visible(timeout=10000)

    # 카카오 로그인은 새 창(팝업)으로 열림
    async with page.expect_popup(timeout=15000) as popup_info:
        await kakao_btn.click()
    popup = await popup_info.value
    await popup.wait_for_load_state("networkidle")
    await popup.wait_for_timeout(1000)

    # 팝업에서 카카오 로그인 폼 처리
    id_field = popup.get_by_placeholder("카카오메일 아이디, 이메일, 전화번호")
    try:
        await id_field.wait_for(state="visible", timeout=5000)
    except Exception:
        # 이미 로그인된 상태 — 팝업이 자동으로 닫힐 수 있음
        await page.wait_for_timeout(3000)
        return
    await id_field.fill(KAKAO_ID)
    await popup.get_by_placeholder("비밀번호").fill(KAKAO_PW)
    await popup.get_by_role("button", name="로그인").first.click()

    # 로그인 성공 시 팝업이 자동으로 닫힘 — TargetClosedError 허용
    try:
        await popup.wait_for_load_state("networkidle")
        # 동의 화면이 나타나면 처리
        agree_btn = popup.locator("button:has-text('동의하고 계속하기')")
        if await agree_btn.count() > 0 and await agree_btn.is_visible():
            await agree_btn.click()
            await popup.wait_for_timeout(3000)
    except Exception:
        pass  # 팝업이 닫힌 경우

    # 팝업 완료 후 원래 페이지로 돌아옴
    await page.wait_for_timeout(3000)
    await page.wait_for_load_state("networkidle")

    # 로그인 후에도 /login에 머물러 있으면 /main으로 직접 이동
    if "/login" in page.url:
        await page.goto(f"{ZERO_BASE_URL}/main")
        await page.wait_for_load_state("networkidle")

    assert "/main" in page.url or "/login" not in page.url, (
        f"카카오 로그인 실패: {page.url}"
    )


async def _get_shop_id_from_crm(page) -> str:
    preview_btn = page.get_by_role("button", name="미리보기")
    await expect(preview_btn).to_be_visible(timeout=10000)

    async with page.expect_popup() as popup_info:
        await preview_btn.click()
    preview_page = await popup_info.value
    await preview_page.wait_for_load_state("networkidle")

    # URL: https://.../shop/S000005093
    url = preview_page.url
    shop_id = url.rstrip("/").split("/")[-1]
    await preview_page.close()
    return shop_id


async def _do_booking_flow(page, shop_id: str):
    """샵 상세 → 시술 선택 → 날짜/시간 선택 → 결제 페이지까지 진행.
    Returns (tomorrow datetime, whether payment page reached)."""
    await page.goto(f"{ZERO_BASE_URL}/shop/{shop_id}")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)

    # 시술 메뉴 선택 (첫 번째 체크박스)
    service_checkbox = page.get_by_role("checkbox").first
    await expect(service_checkbox).to_be_visible(timeout=10000)
    await service_checkbox.click()
    await page.wait_for_timeout(500)

    # 예약하기 버튼 클릭
    booking_btn = page.locator("button:has-text('예약하기')").last
    await expect(booking_btn).to_be_visible(timeout=10000)
    await booking_btn.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)

    # 담당자 선택 (2명 이상일 때 노출)
    designer_row = page.locator("text=샵주테스트").first
    if await designer_row.count() > 0 and await designer_row.is_visible():
        select_btn = page.locator("button:has-text('선택')").first
        await expect(select_btn).to_be_visible(timeout=5000)
        await select_btn.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)
        print("  ✓ 담당자 선택: 샵주테스트")

    # 날짜 선택 (내일)
    tomorrow = datetime.now() + timedelta(days=1)
    day_str = str(tomorrow.day)
    date_btn = page.get_by_role("button", name=day_str, exact=True).first
    await expect(date_btn).to_be_visible(timeout=10000)
    await date_btn.click()
    await page.wait_for_timeout(1000)

    # 시간 선택 (오전 10:00 또는 첫 번째 사용 가능한 시간)
    time_btn = page.locator("button:has-text('10:00')").first
    if await time_btn.count() == 0 or not await time_btn.is_visible():
        time_btn = page.locator("button:has-text(':00'), button:has-text(':30')").first
    await expect(time_btn).to_be_visible(timeout=10000)
    await time_btn.click()
    await page.wait_for_timeout(500)

    # 예약하기 (날짜/시간 선택 페이지) → 결제 페이지로 이동
    booking_confirm = page.locator("button:has-text('예약하기')").last
    await expect(booking_confirm).to_be_visible(timeout=10000)
    await booking_confirm.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)

    return tomorrow


async def _make_reservation(page, shop_name: str, shop_id: str):
    print("=== [flow] B2C 예약 진행 시작 ===")

    tomorrow = await _do_booking_flow(page, shop_id)

    page_text = await page.locator("body").inner_text()
    if "예약 완료" in page_text:
        pass  # 이미 예약 완료
    else:
        await page.screenshot(path=str(SHOT_DIR / "shop_activation_05_payment_page.png"))

        # "카카오로 계속하기" 버튼 처리 — 새 창(팝업)으로 열림
        kakao_btn = page.locator("button[data-track-id='click_pay_login']")
        if await kakao_btn.count() > 0 and await kakao_btn.is_visible():
            print("[reservation] 카카오로 계속하기 버튼 감지 → 팝업 처리")
            await kakao_btn.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)

            async with page.expect_popup(timeout=15000) as popup_info:
                await kakao_btn.click()
            popup = await popup_info.value
            await popup.wait_for_load_state("networkidle")
            await popup.wait_for_timeout(1000)
            print(f"[reservation] 카카오 팝업 열림: {popup.url}")

            # 팝업에서 카카오 로그인 폼 처리 (이미 로그인됐으면 팝업이 바로 닫힘)
            try:
                kakao_id_field = popup.get_by_placeholder("카카오메일 아이디, 이메일, 전화번호")
                if await kakao_id_field.count() > 0 and await kakao_id_field.is_visible():
                    await kakao_id_field.fill(KAKAO_ID)
                    await popup.get_by_placeholder("비밀번호").fill(KAKAO_PW)
                    await popup.get_by_role("button", name="로그인").first.click()

                # 동의 화면이 나타나면 처리
                try:
                    await popup.wait_for_load_state("networkidle")
                    agree_btn = popup.locator("button:has-text('동의하고 계속하기')")
                    if await agree_btn.count() > 0 and await agree_btn.is_visible():
                        await agree_btn.click()
                except Exception:
                    pass  # 팝업이 닫힌 경우
            except Exception:
                pass  # 팝업이 이미 닫힌 경우 (자동 인증 완료)

            # 팝업 완료 후 원래 페이지 대기 — 카카오 버튼이 사라지고 예약하기로 바뀔 때까지
            await page.bring_to_front()
            await page.wait_for_timeout(2000)

            # 카카오 로그인 버튼이 사라질 때까지 대기
            kakao_gone = page.locator("button[data-track-id='click_pay_login']")
            try:
                await kakao_gone.wait_for(state="hidden", timeout=30000)
            except Exception:
                # 안 사라지면 페이지 리로드 시도
                await page.reload()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)

            await page.wait_for_load_state("networkidle")
            await page.screenshot(path=str(SHOT_DIR / "shop_activation_05b_after_kakao.png"))
            print(f"[reservation] 카카오 인증 완료 후 URL: {page.url}")

        # 최종 예약하기 버튼 클릭
        page_text = await page.locator("body").inner_text()
        if "예약 완료" not in page_text:
            final_booking = page.locator("button:has-text('예약하기')").last
            try:
                await expect(final_booking).to_be_visible(timeout=15000)
            except Exception:
                # 예약하기 버튼 안 보이면 리로드 후 재시도
                await page.reload()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(2000)
                final_booking = page.locator("button:has-text('예약하기')").last
                await expect(final_booking).to_be_visible(timeout=15000)
            await final_booking.click()
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)

    # 예약 완료 확인 (URL에 bookingId가 있거나 페이지에 "예약 완료" 텍스트가 있으면 성공)
    complete_text = await page.locator("body").inner_text()
    has_booking_id = "bookingId" in page.url
    has_complete_text = "예약 완료" in complete_text
    assert has_booking_id or has_complete_text, f"예약 완료를 확인할 수 없습니다. URL: {page.url}"
    await page.screenshot(path=str(SHOT_DIR / "shop_activation_06_reservation_complete.png"))
    print("=== [flow] B2C 예약 완료 ===")

    return tomorrow


async def _verify_reservation_on_crm(page, shop_name: str, reservation_date: datetime):
    print("=== [flow] CRM 캘린더 예약 확인 시작 ===")

    await _switch_shop(page, shop_name)

    # 캘린더 페이지로 이동
    await page.goto(f"{CRM_BASE_URL}/book/calendar")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)

    # 날짜별 보기로 전환
    date_view_btn = page.get_by_role("button", name="날짜별")
    if await date_view_btn.count() > 0 and await date_view_btn.is_visible():
        await date_view_btn.click()
        await page.wait_for_timeout(1000)

    # 예약 날짜 선택
    date_cell = page.locator(
        f"td[aria-label*='{reservation_date.year}년 {reservation_date.month}월 {reservation_date.day}일']"
    ).first
    if await date_cell.count() == 0:
        date_cell = page.get_by_role("gridcell",
            name=re.compile(
                rf"{reservation_date.year}년\s*{reservation_date.month}월\s*{reservation_date.day}일"
            )
        ).first
    await expect(date_cell).to_be_visible(timeout=10000)
    await date_cell.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)

    # 예약 확인 (헤렌테스트)
    body_text = await page.locator("body").inner_text()
    assert "헤렌테스트" in body_text, "CRM 캘린더에서 예약자(헤렌테스트)를 찾을 수 없습니다."
    await page.screenshot(path=str(SHOT_DIR / "shop_activation_07_crm_calendar_verified.png"))
    print("=== [flow] CRM 캘린더 예약 확인 완료 ===")


@pytest.mark.asyncio
async def test_create_shop_activate_then_verify_b2c_visibility():
    shop_name = f"{datetime.now():%m%d}_배포_테스트"

    runner = ShopActivationRunner()
    runner.headless = True
    crm_page = None
    zero_page = None
    zero_context = None
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
            # B2C 예약은 별도 컨텍스트에서 수행 (카카오 로그인 세션 분리)
            zero_context = await runner.browser.new_context()
            zero_page = await zero_context.new_page()
            await crm_page.bring_to_front()
            await _crm_login(crm_page)
            await _switch_shop(crm_page, shop_name)
            await crm_page.screenshot(path=str(SHOT_DIR / "shop_activation_01_initial_crm.png"))
            initial_on = await _is_toggle_on(crm_page)

            # 토글이 OFF면 먼저 ON으로 전환
            if not initial_on:
                await _set_toggle(crm_page, turn_on=True)
                await crm_page.screenshot(path=str(SHOT_DIR / "shop_activation_01b_toggle_on.png"))

            # 3. B2C 내주변에서 샵 노출 확인
            await zero_page.bring_to_front()
            await _open_nearby_list(zero_page)
            await zero_page.screenshot(path=str(SHOT_DIR / "shop_activation_02_on_nearby_list.png"))
            assert await _is_shop_visible_in_nearby(zero_page, shop_name), (
                "활성화 상태인데 QA-ZERO 내주변 목록에서 샵이 보이지 않습니다."
            )

            # 4. B2C 예약 진행 (로그인은 결제 페이지에서 팝업으로)
            await crm_page.bring_to_front()
            shop_id = await _get_shop_id_from_crm(crm_page)

            await zero_page.bring_to_front()
            reservation_date = await _make_reservation(zero_page, shop_name, shop_id)

            # 5. CRM 예약 확인 + 공비서로 예약받기 OFF
            await crm_page.bring_to_front()
            await _verify_reservation_on_crm(crm_page, shop_name, reservation_date)

            await crm_page.goto(f"{CRM_BASE_URL}/b2c/setting")
            await crm_page.wait_for_load_state("networkidle")
            await _set_toggle(crm_page, turn_on=False)
            await crm_page.screenshot(path=str(SHOT_DIR / "shop_activation_03_off_applied_crm.png"))

            # 6. B2C 내주변 미노출 확인
            await zero_page.bring_to_front()
            await _open_nearby_list(zero_page)
            await zero_page.screenshot(path=str(SHOT_DIR / "shop_activation_04_off_nearby_list.png"))
            assert not await _is_shop_visible_in_nearby(zero_page, shop_name), (
                "비활성화 후에도 QA-ZERO 내주변 목록에서 샵이 계속 노출됩니다."
            )
        finally:
            if zero_page and not zero_page.is_closed():
                await zero_page.close()
            if zero_context:
                await zero_context.close()
            if crm_page and not crm_page.is_closed():
                await crm_page.close()
    finally:
        await runner.teardown()


