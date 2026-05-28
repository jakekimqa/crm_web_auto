"""
Phase 4.6 단독 테스트: 확인 후 확정 예약 (알림 벨 플로우)
- CRM 예약 방식 → 담당자 확인 후 확정으로 변경
- B2C 예약 진행
- CRM 알림 벨 → 예약 탭 → 해당 예약 클릭 → 확인 후 확정 검증
- 예약 확정 → 매출 등록
- 예약 방식 복원
"""
import asyncio, os, re, sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

sys.path.append(str(Path(__file__).resolve().parents[2]))
from auto_web_test.B2C_tests.test_b2b_b2c_shop_activation_flow import (
    _crm_login, _switch_shop, _kakao_login,
    CRM_BASE_URL as _DEFAULT_CRM_URL,
    ZERO_BASE_URL as _DEFAULT_ZERO_URL,
    SHOT_DIR,
)

CRM_BASE_URL = os.getenv("CRM_BASE_URL", _DEFAULT_CRM_URL)
ZERO_BASE_URL = os.getenv("ZERO_BASE_URL", _DEFAULT_ZERO_URL)
SHOP_NAME = os.getenv("B2C_SHOP_NAME", "0526_1215_배포_테스트")
SHOP_ID = os.getenv("B2C_SHOP_ID", "S000005288")


@pytest.mark.asyncio
async def test_phase46_notification_booking():
    """Phase 4.6: 확인 후 확정 예약 — 알림 벨 플로우"""
    async with async_playwright() as pw:
        headless = os.getenv("B2B_HEADLESS", "1") == "1"
        browser = await pw.chromium.launch(headless=headless)
        crm_context = await browser.new_context(viewport={"width": 1440, "height": 900})
        crm_page = await crm_context.new_page()
        crm_page.set_default_timeout(60000)

        zero_context = await browser.new_context(viewport={"width": 430, "height": 932})
        zero_page = await zero_context.new_page()
        zero_page.set_default_timeout(60000)

        try:
            # === 로그인 + 샵 전환 ===
            await _crm_login(crm_page)
            await _switch_shop(crm_page, SHOP_NAME)
            print(f"  [OK] CRM 로그인 + 샵 전환: {SHOP_NAME}")

            # === Step 1: 예약 방식 → 담당자 확인 후 확정 ===
            await crm_page.goto(f"{CRM_BASE_URL}/b2c/setting", wait_until="domcontentloaded")
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)

            online_info = crm_page.locator("h3:has-text('온라인 예약 정보')").first
            await expect(online_info).to_be_visible(timeout=15000)
            edit_btn = online_info.locator("..").locator("button:has-text('수정하기')").first
            await expect(edit_btn).to_be_visible(timeout=15000)
            await edit_btn.click()
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)

            confirm_option = crm_page.locator("label[for='MANUAL_CONFIRMED']").first
            await expect(confirm_option).to_be_visible(timeout=15000)
            await confirm_option.click()
            await crm_page.wait_for_timeout(500)

            save_btn = crm_page.locator("button[data-track-id='b2c_info_save']").first
            await expect(save_btn).to_be_visible(timeout=15000)
            await save_btn.click()
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)
            print("  [OK] 예약 방식 변경: 담당자 확인 후 예약 확정")

            # === Step 2: B2C 카카오 로그인 + 예약 진행 ===
            print("  --- B2C 카카오 로그인 ---")
            await _kakao_login(zero_page)
            print("  [OK] 카카오 로그인 완료")

            print("  --- B2C 확인 후 확정 예약 진행 ---")
            await zero_page.goto(f"{ZERO_BASE_URL}/shop/{SHOP_ID}", wait_until="domcontentloaded")
            try:
                await zero_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await zero_page.wait_for_timeout(1000)

            service_cb = zero_page.get_by_role("checkbox").first
            await expect(service_cb).to_be_visible(timeout=15000)
            await service_cb.click()
            await zero_page.wait_for_timeout(500)

            booking_btn = zero_page.locator("button:has-text('예약하기')").last
            await expect(booking_btn).to_be_visible(timeout=15000)
            await booking_btn.click()
            try:
                await zero_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await zero_page.wait_for_timeout(1000)

            # 담당자 선택
            designer_row = zero_page.locator("text=샵주테스트").first
            if await designer_row.count() > 0 and await designer_row.is_visible():
                select_btn = zero_page.locator("button:has-text('선택')").first
                await expect(select_btn).to_be_visible(timeout=15000)
                await select_btn.click()
                try:
                    await zero_page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                await zero_page.wait_for_timeout(1000)
                print("  [OK] 담당자 선택: 샵주테스트")

            # 날짜 선택 (내일)
            tomorrow = datetime.now() + timedelta(days=1)
            day_str = str(tomorrow.day)
            date_btn = zero_page.get_by_role("button", name=day_str, exact=True).first
            await expect(date_btn).to_be_visible(timeout=15000)
            await date_btn.click()
            await zero_page.wait_for_timeout(1000)

            # 시간 선택
            time_btn = zero_page.locator("button:has-text(':00'), button:has-text(':30')").first
            await expect(time_btn).to_be_visible(timeout=15000)
            confirm_time_text = await time_btn.inner_text()
            await time_btn.click()
            await zero_page.wait_for_timeout(500)
            print(f"  [OK] 시간 선택: {confirm_time_text}")

            # 예약하기
            booking_confirm = zero_page.locator("button:has-text('예약하기')").last
            await expect(booking_confirm).to_be_visible(timeout=15000)
            await booking_confirm.click()
            try:
                await zero_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await zero_page.wait_for_timeout(1000)

            # 앱 다운로드 팝업 제거
            await zero_page.evaluate("""() => {
                document.querySelectorAll('article, [role="alert"]').forEach(el => {
                    if (el.textContent.includes('앱 다운로드') || el.textContent.includes('App 다운로드') || el.getAttribute('role') === 'alert') {
                        el.style.display = 'none';
                        el.style.pointerEvents = 'none';
                    }
                });
            }""")
            await zero_page.wait_for_timeout(500)

            page_text = await zero_page.locator("body").inner_text()
            if "예약 완료" not in page_text and "예약 신청" not in page_text:
                # 동의 체크박스
                agree = zero_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
                if await agree.count() > 0:
                    await agree.click()
                    await zero_page.wait_for_timeout(1000)

                final_booking = zero_page.locator("button:has-text('예약하기')").last
                await expect(final_booking).to_be_visible(timeout=15000)
                await final_booking.click(force=True)
                try:
                    await zero_page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                await zero_page.wait_for_timeout(2000)

            # Step 3: B2C 예약 완료/신청 텍스트 검증
            complete_text = await zero_page.locator("body").inner_text()
            has_completion = any(t in complete_text for t in ["예약 신청", "예약 완료", "예약이 접수"])
            assert has_completion, f"확인 후 확정 예약 완료 텍스트 미노출: {complete_text[:300]}"
            print("  [OK] B2C 예약 완료/신청 텍스트 확인")
            await zero_page.screenshot(path=str(SHOT_DIR / "noti46_01_b2c_pending.png"))

            # === Step 4: CRM 알림 벨 → 예약 탭 → 예약 클릭 ===
            await crm_page.bring_to_front()

            # 캘린더 페이지로 이동 (알림 벨이 헤더에 있으므로)
            await crm_page.goto(f"{CRM_BASE_URL}/book/calendar", wait_until="domcontentloaded")
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(2000)

            # 팝업 dimmer 제거
            for _ in range(5):
                dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
                if await dim.count() > 0:
                    await dim.click(force=True)
                    await crm_page.wait_for_timeout(500)
                else:
                    break

            # 예약현황 패널이 열려있으면 닫기 (말풍선을 가리므로 먼저 닫아야 함)
            panel_close_btn = crm_page.locator("button:has(img[alt='예약 비활성화'])").first
            try:
                await panel_close_btn.wait_for(state="visible", timeout=3000)
                await panel_close_btn.click()
                await crm_page.wait_for_timeout(500)
                print("  [OK] 예약현황 패널 닫기")
            except Exception:
                print("  [SKIP] 예약현황 패널 없음")

            # 알림 말풍선 확인
            noti_bubble = crm_page.locator("h5:has-text('대기 중인 예약')").first
            await expect(noti_bubble).to_be_visible(timeout=15000)
            bubble_text = await noti_bubble.inner_text()
            print(f"  [OK] 알림 말풍선 확인: {bubble_text}")
            await crm_page.screenshot(path=str(SHOT_DIR / "noti46_02_bubble.png"))

            # 알림 벨 버튼 클릭
            bell_btn = crm_page.locator("button[data-track-id='notification_panel_open']").first
            await expect(bell_btn).to_be_visible(timeout=15000)
            await bell_btn.click()
            await crm_page.wait_for_timeout(3000)
            print("  [OK] 알림 벨 클릭 → 알림 패널 열림")
            await crm_page.screenshot(path=str(SHOT_DIR / "noti46_03_panel_open.png"))

            # "예약" 탭 클릭
            reservation_tab = crm_page.locator("button[data-track-id='notification_tab'][data-track-type='예약']").first
            await expect(reservation_tab).to_be_visible(timeout=15000)
            await reservation_tab.click()
            await crm_page.wait_for_timeout(3000)
            print("  [OK] 예약 탭 선택")
            await crm_page.screenshot(path=str(SHOT_DIR / "noti46_04_reservation_tab.png"))

            # 알림 목록에서 해당 예약 클릭 → 캘린더로 이동
            noti_item = crm_page.locator("div[data-notification-key^='ZERO_BOOKING_READY'][role='button']").first
            await expect(noti_item).to_be_visible(timeout=15000)
            await noti_item.click()
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(2000)
            print(f"  [OK] 알림 클릭 → 캘린더 이동: {crm_page.url}")

            # 캘린더에서 대기 중인 예약 카드 클릭 → 예약 상세 진입
            pending_block = crm_page.locator("div.READY.booking-normal").first
            await expect(pending_block).to_be_visible(timeout=15000)
            await pending_block.click(force=True)
            await crm_page.wait_for_timeout(2000)
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            confirm_detail_url = crm_page.url
            print(f"  [OK] 예약 상세 진입: {confirm_detail_url}")

            # === Step 5: 확인 후 확정 안내 텍스트 검증 ===
            detail_text = await crm_page.locator("body").inner_text()
            assert "확인 후 확정" in detail_text or "예약 대기" in detail_text, \
                f"확인 후 확정 안내 미노출: {detail_text[:300]}"
            print("  [OK] '확인 후 확정 예약입니다' 안내 확인")
            await crm_page.screenshot(path=str(SHOT_DIR / "noti46_05_pending_detail.png"))

            # === Step 6: 예약 확정 ===
            confirm_btn = crm_page.locator("button:has-text('예약 확정')").first
            await expect(confirm_btn).to_be_visible(timeout=15000)
            await confirm_btn.click()
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)
            print("  [OK] 예약 확정 완료")
            await crm_page.screenshot(path=str(SHOT_DIR / "noti46_06_confirmed.png"))

            # === Step 7: 매출 등록 ===
            if "detail" not in crm_page.url:
                await crm_page.goto(confirm_detail_url, wait_until="domcontentloaded")
                try:
                    await crm_page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                await crm_page.wait_for_timeout(1000)

            sales_btn = crm_page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
            await expect(sales_btn).to_be_visible(timeout=15000)
            await sales_btn.click()
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)

            card_btn = crm_page.get_by_text("카드", exact=True).first
            if await card_btn.count() == 0:
                card_btn = crm_page.locator("button:has-text('카드'), label:has-text('카드')").first
            await expect(card_btn).to_be_visible(timeout=15000)
            await card_btn.click()
            await crm_page.wait_for_timeout(500)
            print("  [OK] 결제 수단: 카드 선택")

            save_sales_btn = crm_page.locator("button:has-text('매출 저장'), button:has-text('매출 등록')").first
            await expect(save_sales_btn).to_be_visible(timeout=15000)
            await save_sales_btn.click()
            await crm_page.wait_for_timeout(3000)
            print("  [OK] 매출 등록 완료")

            await crm_page.goto(confirm_detail_url, wait_until="domcontentloaded")
            await crm_page.wait_for_load_state("domcontentloaded")
            await crm_page.wait_for_timeout(2000)
            detail_body = await crm_page.locator("body").inner_text()
            assert "매출" in detail_body, "매출 등록 확인 실패"
            print("  [OK] 매출 등록 완료 상태 확인")
            await crm_page.screenshot(path=str(SHOT_DIR / "noti46_07_sales_done.png"))

            # === Step 8: 예약 방식 복원 (즉시 확정) ===
            await crm_page.goto(f"{CRM_BASE_URL}/b2c/setting", wait_until="domcontentloaded")
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)

            online_info2 = crm_page.locator("h3:has-text('온라인 예약 정보')").first
            edit_btn2 = online_info2.locator("..").locator("button:has-text('수정하기')").first
            await expect(edit_btn2).to_be_visible(timeout=15000)
            await edit_btn2.click()
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)

            instant_option = crm_page.locator("label[for='AUTO_CONFIRMED']").first
            await expect(instant_option).to_be_visible(timeout=15000)
            await instant_option.click()
            await crm_page.wait_for_timeout(500)

            restore_save = crm_page.locator("button[data-track-id='b2c_info_save']").first
            await expect(restore_save).to_be_visible(timeout=15000)
            await restore_save.click()
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)
            print("  [OK] 예약 방식 복원: 즉시 예약 확정")

            print("\n=== Phase 4.6 알림 벨 플로우 완료 ===")

        finally:
            await crm_context.close()
            await zero_context.close()
            await browser.close()
