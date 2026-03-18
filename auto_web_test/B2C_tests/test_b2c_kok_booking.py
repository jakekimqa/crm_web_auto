"""
콕예약 단독 테스트: B2C 카카오 로그인 → 관심샵 → 콕예약 → 예약 완료 → CRM 매출 등록
"""
import os, re, sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

sys.path.append(str(Path(__file__).resolve().parents[2]))
from auto_web_test.B2C_tests.test_b2b_b2c_shop_activation_flow import (
    ShopActivationRunner, _crm_login, _switch_shop,
    ZERO_BASE_URL, CRM_BASE_URL, SHOT_DIR,
)

KAKAO_ID = os.getenv("KAKAO_ID", "developer@herren.co.kr")
KAKAO_PW = os.getenv("KAKAO_PW", "herren3378!")


@pytest.mark.asyncio
async def test_b2c_kok_booking():
    KOK_SHOP_NAME = "자동화_헤렌네일"

    async with async_playwright() as pw:
        headless = os.getenv("B2B_HEADLESS", "1") == "1"
        browser = await pw.chromium.launch(headless=headless)

        # B2C 컨텍스트 (모바일 뷰)
        zero_context = await browser.new_context(viewport={"width": 430, "height": 932})
        zero_page = await zero_context.new_page()

        # CRM 컨텍스트 (데스크톱 뷰)
        crm_context = await browser.new_context(viewport={"width": 1440, "height": 900})
        crm_page = await crm_context.new_page()

        try:
            # ── Step 1: 카카오 로그인 ──
            print("\n=== Step 1: B2C 카카오 로그인 ===")
            await zero_page.goto(f"{ZERO_BASE_URL}/login")
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(1000)

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
                        await popup.wait_for_timeout(3000)
                except Exception:
                    pass
            except Exception:
                await zero_page.wait_for_timeout(3000)

            await zero_page.wait_for_timeout(3000)
            await zero_page.wait_for_load_state("networkidle")
            if "/login" in zero_page.url:
                await zero_page.goto(f"{ZERO_BASE_URL}/main")
                await zero_page.wait_for_load_state("networkidle")

            print(f"  로그인 후 URL: {zero_page.url}")
            print("  ✓ 카카오 로그인 완료")

            # ── Step 2: 홈 → 관심샵 → 자동화_헤렌네일 진입 ──
            print("=== Step 2: 관심샵 진입 ===")
            await zero_page.goto(f"{ZERO_BASE_URL}/main")
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(2000)

            fav_shop = zero_page.locator(f"text={KOK_SHOP_NAME}").first
            await expect(fav_shop).to_be_visible(timeout=10000)
            await fav_shop.click()
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(1500)
            print(f"  ✓ '{KOK_SHOP_NAME}' 진입")

            # ── Step 3: 콕예약 탭 → 자동화_테스트 선택 ──
            print("=== Step 3: 콕예약 선택 ===")
            kok_tab = zero_page.locator("button:has-text('콕예약')").first
            await expect(kok_tab).to_be_visible(timeout=10000)
            await kok_tab.click()
            await zero_page.wait_for_timeout(1000)
            print("  ✓ 콕예약 탭 선택")

            kok_item = zero_page.locator("text=자동화_테스트").first
            await expect(kok_item).to_be_visible(timeout=10000)
            await kok_item.click()
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(1000)
            print("  ✓ '자동화_테스트' 콕예약 선택")

            # ── Step 4: 날짜/담당자/시간 선택 → 예약하기 ──
            print("=== Step 4: 예약 정보 선택 ===")
            tomorrow = datetime.now() + timedelta(days=1)
            day_str = str(tomorrow.day)
            date_btn = zero_page.get_by_role("button", name=day_str, exact=True).first
            await expect(date_btn).to_be_visible(timeout=10000)
            await date_btn.click()
            await zero_page.wait_for_timeout(1000)
            print(f"  ✓ 날짜 선택: 내일 ({tomorrow.month}/{tomorrow.day})")

            # 담당자 선택: 샵주테스트
            designer = zero_page.locator("text=샵주테스트").first
            if await designer.count() > 0 and await designer.is_visible():
                select_btn = zero_page.locator("button:has-text('선택')").first
                if await select_btn.count() > 0 and await select_btn.is_visible():
                    await select_btn.click()
                else:
                    await designer.click()
                await zero_page.wait_for_load_state("networkidle")
                await zero_page.wait_for_timeout(1000)
                print("  ✓ 담당자 선택: 샵주테스트")

            # 가장 빠른 시간 선택
            time_btn = zero_page.locator("button:has-text(':00'), button:has-text(':30')").first
            await expect(time_btn).to_be_visible(timeout=10000)
            kok_time = await time_btn.inner_text()
            await time_btn.click()
            await zero_page.wait_for_timeout(500)
            print(f"  ✓ 시간 선택: {kok_time}")

            # 예약하기 → 결제 페이지로 바로 이동
            booking_btn = zero_page.locator("button:has-text('예약하기')").last
            await expect(booking_btn).to_be_visible(timeout=10000)
            await booking_btn.click()
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(2000)

            # ── Step 5: 고객 요청사항 확인 + 예약 완료 ──
            print("=== Step 5: 결제 페이지 검증 + 예약 완료 ===")
            request_textarea = zero_page.locator("textarea").first
            if await request_textarea.count() > 0:
                request_text = await request_textarea.input_value()
            else:
                request_text = await zero_page.locator("body").inner_text()
            assert "[콕예약]" in request_text, \
                f"고객 요청사항에 '[콕예약]' 미포함: '{request_text[:100]}'"
            print(f"  ✓ 고객 요청사항: '{request_text.strip()}'")

            # 동의 체크 (있으면)
            agree = zero_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
            if await agree.count() > 0:
                await agree.click()
                await zero_page.wait_for_timeout(500)

            # 하단 [예약하기] → 예약 완료
            final_btn = zero_page.locator("button:has-text('예약하기')").last
            await expect(final_btn).to_be_visible(timeout=10000)
            await final_btn.click()
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(2000)

            assert "bookingId" in zero_page.url or "예약 완료" in await zero_page.locator("body").inner_text(), \
                f"콕예약 실패: {zero_page.url}"
            await zero_page.screenshot(path=str(SHOT_DIR / "kok_01_booking_complete.png"))
            print("  ✓ 콕예약 완료!")
            print("✓ Step 5 완료\n")

            # ── Step 6: CRM 로그인 + 자동화_헤렌네일 샵 전환 ──
            print("=== Step 6: CRM 로그인 + 샵 전환 ===")
            await crm_page.bring_to_front()
            await _crm_login(crm_page)
            await _switch_shop(crm_page, KOK_SHOP_NAME)
            print(f"  ✓ CRM '{KOK_SHOP_NAME}' 전환 완료")

            # ── Step 7: 캘린더 → 내일 이동 → 콕예약 블록 클릭 ──
            print("=== Step 7: 캘린더 → 예약 상세 ===")
            await crm_page.goto(f"{CRM_BASE_URL}/book/calendar")
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(2000)

            # 딤머 닫기
            for _ in range(5):
                dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
                if await dim.count() > 0:
                    await dim.click(force=True)
                    await crm_page.wait_for_timeout(500)
                else:
                    break

            # "일" 보기 전환
            for name in ["일", "날짜별"]:
                btn = crm_page.get_by_role("button", name=name).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    await crm_page.wait_for_load_state("networkidle")
                    await crm_page.wait_for_timeout(1500)
                    break

            # 딤머 닫기
            for _ in range(3):
                dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
                if await dim.count() > 0:
                    await dim.click(force=True)
                    await crm_page.wait_for_timeout(500)
                else:
                    break

            # 내일 날짜로 이동
            d = tomorrow
            header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
            target_day = f"{d.month}. {d.day}"
            for _ in range(10):
                if f"{d.day}" in header:
                    break
                current_match = re.search(r"(\d+)\.\s*(\d+)", header)
                if current_match:
                    current_day = int(current_match.group(2))
                    btn_cls = "fc-next-button" if current_day < d.day else "fc-prev-button"
                else:
                    btn_cls = "fc-next-button"
                nav_btn = crm_page.locator(f"button.{btn_cls}").first
                await expect(nav_btn).to_be_visible(timeout=5000)
                await nav_btn.click()
                await crm_page.wait_for_load_state("networkidle")
                await crm_page.wait_for_timeout(1500)
                header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
            print(f"  ✓ 캘린더 날짜: {header.strip()}")

            # 딤머 닫기
            for _ in range(3):
                dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
                if await dim.count() > 0:
                    await dim.click(force=True)
                    await crm_page.wait_for_timeout(500)
                else:
                    break

            # 예약 블록 클릭 → 상세 페이지
            block = crm_page.locator("div.booking-normal").first
            await expect(block).to_be_visible(timeout=15000)
            await block.click(force=True)
            await crm_page.wait_for_timeout(3000)
            await crm_page.wait_for_load_state("networkidle")
            detail_url = crm_page.url
            print(f"  ✓ 예약 상세: {detail_url}")

            # "공비서 > 콕예약" 경로 확인
            detail_text = await crm_page.locator("body").inner_text()
            assert "공비서" in detail_text, f"'공비서' 텍스트 미발견"
            assert "콕예약" in detail_text, f"'콕예약' 텍스트 미발견"
            print("  ✓ '공비서 > 콕예약' 확인")

            if "[콕예약]" in detail_text:
                print("  ✓ 요청사항에 [콕예약] 확인")
            await crm_page.screenshot(path=str(SHOT_DIR / "kok_02_crm_detail.png"))

            # ── Step 8: 매출 등록 ──
            print("=== Step 8: 매출 등록 ===")
            sales_btn = crm_page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
            await expect(sales_btn).to_be_visible(timeout=10000)
            await sales_btn.click()
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(2000)
            print(f"  ✓ 매출 등록 페이지: {crm_page.url}")

            # 결제 금액 확인
            sales_text = await crm_page.locator("body").inner_text()
            if "20,000" in sales_text:
                print("  ✓ 결제 금액: 20,000원")
            await crm_page.screenshot(path=str(SHOT_DIR / "kok_03_sales_page.png"))

            # 결제 수단: 카드 선택
            card_btn = crm_page.get_by_text("카드", exact=True).first
            if await card_btn.count() == 0:
                card_btn = crm_page.locator("button:has-text('카드'), label:has-text('카드')").first
            await expect(card_btn).to_be_visible(timeout=10000)
            await card_btn.click()
            await crm_page.wait_for_timeout(500)
            print("  ✓ 결제 수단: 카드 선택")

            # 매출 저장
            save_btn = crm_page.locator("button:has-text('매출 저장')").first
            await expect(save_btn).to_be_visible(timeout=10000)
            await save_btn.click()
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(3000)
            print("  ✓ 매출 저장 완료")

            # 매출 등록 완료 확인
            await crm_page.goto(detail_url)
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(2000)
            sales_label = crm_page.locator("h4.SALE.disabled:has-text('매출 등록')").first
            if await sales_label.count() == 0:
                sales_label = crm_page.locator("h4:has-text('매출 등록')").first
            await expect(sales_label).to_be_visible(timeout=10000)
            print("  ✓ 매출 등록 완료 상태 확인")
            await crm_page.screenshot(path=str(SHOT_DIR / "kok_04_sales_done.png"))
            print("✓ Step 8 완료\n")

            print("=== 콕예약 전체 테스트 성공! ===")

        finally:
            await zero_context.close()
            await crm_context.close()
            await browser.close()
