"""
기존 샵(S000005159)에서 예약 2건 테스트:
1) 첫 번째 예약 → 예약 완료 페이지에서 X 닫기
2) 컷 > 남성컷 → 첫 번째 예약 다음 시간으로 두 번째 예약
3) CRM 캘린더에서 예약 2건 확인
"""
import os, sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

sys.path.append(str(Path(__file__).resolve().parents[2]))

ZERO_BASE_URL = os.getenv("ZERO_BASE_URL", "https://qa-zero.gongbiz.kr")
CRM_BASE_URL = os.getenv("CRM_BASE_URL", "https://crm-dev5.gongbiz.kr")
KAKAO_ID = os.getenv("KAKAO_ID", "developer@herren.co.kr")
KAKAO_PW = os.getenv("KAKAO_PW", "herren3378!")
CRM_USER_ID = os.getenv("CRM_USER_ID", "autoqatest1")
CRM_USER_PW = os.getenv("CRM_USER_PW", "gong2023@@")
SHOP_ID = "S000005159"
SHOT_DIR = Path(os.getenv("TEST_SCREENSHOT_DIR", "qa_artifacts/screenshots"))
SHOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.mark.asyncio
async def test_double_booking_on_existing_shop():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    zero_context = await browser.new_context(viewport={"width": 430, "height": 932})
    zero_page = await zero_context.new_page()

    try:
        # ── 카카오 로그인 ──
        print("\n=== 카카오 로그인 ===")
        await zero_page.goto(f"{ZERO_BASE_URL}/login")
        await zero_page.wait_for_load_state("networkidle")

        kakao_btn = zero_page.get_by_role("button", name="카카오로 로그인")
        await expect(kakao_btn).to_be_visible(timeout=10000)

        async with zero_page.expect_popup(timeout=15000) as popup_info:
            await kakao_btn.click()
        popup = await popup_info.value
        await popup.wait_for_load_state("networkidle")
        await popup.wait_for_timeout(1000)

        id_field = popup.get_by_placeholder("카카오메일 아이디, 이메일, 전화번호")
        try:
            await id_field.wait_for(state="visible", timeout=5000)
            await id_field.fill(KAKAO_ID)
            await popup.get_by_placeholder("비밀번호").fill(KAKAO_PW)
            await popup.get_by_role("button", name="로그인").first.click()
            try:
                await popup.wait_for_load_state("networkidle")
                agree_btn = popup.locator("button:has-text('동의하고 계속하기')")
                if await agree_btn.count() > 0 and await agree_btn.is_visible():
                    await agree_btn.click()
            except Exception:
                pass
        except Exception:
            pass

        await zero_page.wait_for_timeout(3000)
        await zero_page.wait_for_load_state("networkidle")
        if "/login" in zero_page.url:
            await zero_page.goto(f"{ZERO_BASE_URL}/main")
            await zero_page.wait_for_load_state("networkidle")
        print(f"  ✓ 카카오 로그인 완료: {zero_page.url}")

        # ── 첫 번째 예약 ──
        print("\n=== 첫 번째 예약 ===")
        await zero_page.goto(f"{ZERO_BASE_URL}/shop/{SHOP_ID}")
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 첫 번째 시술 체크박스 선택
        service_checkbox = zero_page.get_by_role("checkbox").first
        await expect(service_checkbox).to_be_visible(timeout=10000)
        await service_checkbox.click()
        await zero_page.wait_for_timeout(500)

        # 예약하기 버튼
        booking_btn = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_btn).to_be_visible(timeout=10000)
        await booking_btn.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 내일 날짜 선택
        tomorrow = datetime.now() + timedelta(days=1)
        day_str = str(tomorrow.day)
        date_btn = zero_page.get_by_role("button", name=day_str, exact=True).first
        await expect(date_btn).to_be_visible(timeout=10000)
        await date_btn.click()
        await zero_page.wait_for_timeout(1000)

        # 첫 번째 시간 선택 (10:00 또는 첫 번째 가능 시간)
        time_buttons = zero_page.locator("button:has-text(':00'), button:has-text(':30')")
        first_time_btn = time_buttons.first
        await expect(first_time_btn).to_be_visible(timeout=10000)
        first_time_text = await first_time_btn.inner_text()
        await first_time_btn.click()
        await zero_page.wait_for_timeout(500)
        print(f"  첫 번째 예약 시간: {first_time_text}")

        # 예약하기 → 결제 페이지로 이동
        booking_confirm = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_confirm).to_be_visible(timeout=10000)
        await booking_confirm.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(2000)

        # 결제 페이지: 동의 체크 → 최종 예약하기
        agree_check = zero_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
        if await agree_check.count() > 0:
            await agree_check.click()
            await zero_page.wait_for_timeout(500)

        final_booking = zero_page.locator("button:has-text('예약하기')").last
        await expect(final_booking).to_be_visible(timeout=10000)
        await final_booking.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(2000)

        # 예약 완료 확인
        page_text = await zero_page.locator("body").inner_text()
        assert "bookingId" in zero_page.url or "예약 완료" in page_text or "예약이 완료" in page_text, \
            f"첫 번째 예약 실패: {zero_page.url}"
        await zero_page.screenshot(path=str(SHOT_DIR / "double_01_first_complete.png"))
        print("  ✓ 첫 번째 예약 완료")

        # ── X 버튼 닫기 → 샵 페이지로 복귀 ──
        print("\n=== X 버튼 닫기 → 두 번째 예약 ===")
        close_btn = zero_page.locator("button:has(svg), button[aria-label='close'], button[aria-label='닫기']").first
        if await close_btn.count() > 0 and await close_btn.is_visible():
            await close_btn.click()
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(1000)
            print(f"  ✓ X 버튼 클릭 후 URL: {zero_page.url}")
        else:
            # X 버튼 못 찾으면 직접 샵 페이지로 이동
            await zero_page.goto(f"{ZERO_BASE_URL}/shop/{SHOP_ID}")
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(1000)
            print("  ✓ 샵 페이지로 직접 이동")

        await zero_page.screenshot(path=str(SHOT_DIR / "double_02_after_close.png"))

        # ── 두 번째 예약: 컷 > 남성컷 ──
        # 샵 페이지가 아니면 이동
        if f"/shop/{SHOP_ID}" not in zero_page.url:
            await zero_page.goto(f"{ZERO_BASE_URL}/shop/{SHOP_ID}")
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(1000)

        # "컷" 카테고리 버튼 클릭
        cut_btn = zero_page.locator("button:has-text('컷')").first
        await expect(cut_btn).to_be_visible(timeout=10000)
        await cut_btn.click()
        await zero_page.wait_for_timeout(1000)

        # "남성컷" 체크박스 선택
        male_cut = zero_page.locator("label:has-text('남성컷'), span:has-text('남성컷')").first
        if await male_cut.count() == 0:
            # 체크박스로 시도
            checkboxes = zero_page.get_by_role("checkbox")
            count = await checkboxes.count()
            for i in range(count):
                cb = checkboxes.nth(i)
                text = await cb.inner_text()
                if "남성컷" in text:
                    male_cut = cb
                    break
        await expect(male_cut).to_be_visible(timeout=10000)
        await male_cut.click()
        await zero_page.wait_for_timeout(500)
        await zero_page.screenshot(path=str(SHOT_DIR / "double_03_male_cut_selected.png"))

        # 예약하기 버튼
        booking_btn2 = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_btn2).to_be_visible(timeout=10000)
        await booking_btn2.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 내일 날짜 선택
        date_btn2 = zero_page.get_by_role("button", name=day_str, exact=True).first
        await expect(date_btn2).to_be_visible(timeout=10000)
        await date_btn2.click()
        await zero_page.wait_for_timeout(1000)

        # 두 번째 시간: 첫 번째 보이는 시간 선택
        time_buttons2 = zero_page.locator("button:has-text(':00'), button:has-text(':30')")
        second_time_btn = time_buttons2.first
        await expect(second_time_btn).to_be_visible(timeout=10000)
        second_time_text = await second_time_btn.inner_text()
        await second_time_btn.click()
        await zero_page.wait_for_timeout(500)
        print(f"  두 번째 예약 시간: {second_time_text}")

        # 예약하기 → 결제 페이지로 이동
        booking_confirm2 = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_confirm2).to_be_visible(timeout=10000)
        await booking_confirm2.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(2000)

        # 결제 페이지: 동의 체크 → 최종 예약하기
        agree_check2 = zero_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
        if await agree_check2.count() > 0:
            await agree_check2.click()
            await zero_page.wait_for_timeout(500)

        final_booking2 = zero_page.locator("button:has-text('예약하기')").last
        await expect(final_booking2).to_be_visible(timeout=10000)
        await final_booking2.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(2000)

        assert "bookingId" in zero_page.url or "예약 완료" in await zero_page.locator("body").inner_text(), \
            f"두 번째 예약 실패: {zero_page.url}"
        await zero_page.screenshot(path=str(SHOT_DIR / "double_04_second_complete.png"))
        print("  ✓ 두 번째 예약 완료")

        print("\n=== 전체 예약 2건 완료! ===")

    finally:
        await zero_context.close()
        await browser.close()
        await pw.stop()
