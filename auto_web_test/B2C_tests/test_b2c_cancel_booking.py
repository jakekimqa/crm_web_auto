"""
B2C 예약 2건 → B2B 첫 번째 취소 + 사유 검증 → 두 번째 매출 등록 → 공비서 예약 OFF → B2C 미노출
"""
import os, re, sys, json, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

sys.path.append(str(Path(__file__).resolve().parents[2]))
from auto_web_test.B2C_tests.test_b2b_b2c_shop_activation_flow import (
    ShopActivationRunner, _crm_login, _switch_shop,
    _open_nearby_list, _is_shop_visible_in_nearby,
    _make_reservation, _kakao_login, _is_toggle_on, _set_toggle,
    CRM_BASE_URL, SHOT_DIR,
)


@pytest.mark.asyncio
async def test_b2c_booking_cancel_with_default_reason():
    shop_name = f"{datetime.now():%m%d_%H%M}_배포_테스트"

    runner = ShopActivationRunner()
    runner.base_url = f"{CRM_BASE_URL}/signin"
    runner.headless = os.getenv("B2B_HEADLESS", "1") == "1"
    runner.mmdd = datetime.now().strftime("%m%d_%H%M")
    crm_page = zero_page = zero_context = None

    try:
        # ── Phase 1: 샵 생성 + 입점 ──
        print("\n=== Phase 1: 샵 생성 + 공비서 입점 ===")
        await runner.setup()
        await runner.login()
        try:
            await runner.create_new_shop()
        except Exception as e:
            if "signup/owner/add" in str(e):
                await runner.page.wait_for_url("**/signup/shop*", timeout=10000)
            else:
                raise
        try:
            await runner.enable_gong_booking_after_shop_creation()
        except Exception as exc:
            if "토글이 ON 상태" not in str(exc) and "activate-switch" not in str(exc):
                raise
        print("✓ Phase 1 완료\n")

        # ── Phase 2: B2C 예약 ──
        print("=== Phase 2: B2C 예약 ===")
        crm_page = await runner.context.new_page()
        zero_context = await runner.browser.new_context(viewport={"width": 430, "height": 932})
        zero_page = await zero_context.new_page()

        await crm_page.bring_to_front()
        await _crm_login(crm_page)
        await _switch_shop(crm_page, shop_name)

        # shopId
        try:
            api = "https://qa-api-zero.gongbiz.kr/api/v1/search/shop/location?lat=37.4979&lng=127.0276&radius=5000"
            with urllib.request.urlopen(api, timeout=10) as r:
                data = json.loads(r.read())
            shop_id = next(s["id"] for s in data.get("shopList", []) if shop_name in s.get("name", ""))
        except Exception:
            from auto_web_test.B2C_tests.test_b2b_b2c_shop_activation_flow import _get_shop_id_from_crm
            shop_id = await _get_shop_id_from_crm(crm_page)
        print(f"  shopId: {shop_id}")

        await zero_page.bring_to_front()
        await _kakao_login(zero_page)
        reservation_date = await _make_reservation(zero_page, shop_name, shop_id)
        print("  ✓ 첫 번째 예약 완료")

        # ── 두 번째 예약: 컷 > 남성컷 ──
        print("  --- 두 번째 예약: 컷 > 남성컷 ---")
        ZERO_BASE_URL = os.getenv("ZERO_BASE_URL", "https://qa-zero.gongbiz.kr")
        await zero_page.goto(f"{ZERO_BASE_URL}/shop/{shop_id}")
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # "컷" 카테고리 선택
        cut_btn = zero_page.locator("button:has-text('컷')").first
        await expect(cut_btn).to_be_visible(timeout=10000)
        await cut_btn.click()
        await zero_page.wait_for_timeout(1000)

        # "남성컷" 체크박스 선택
        male_cut = zero_page.locator("label:has-text('남성컷'), span:has-text('남성컷')").first
        if await male_cut.count() == 0:
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

        # 예약하기 버튼
        booking_btn2 = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_btn2).to_be_visible(timeout=10000)
        await booking_btn2.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 내일 날짜 선택
        tomorrow = datetime.now() + timedelta(days=1)
        day_str = str(tomorrow.day)
        date_btn2 = zero_page.get_by_role("button", name=day_str, exact=True).first
        await expect(date_btn2).to_be_visible(timeout=10000)
        await date_btn2.click()
        await zero_page.wait_for_timeout(1000)

        # 첫 번째 보이는 시간 선택
        time_buttons2 = zero_page.locator("button:has-text(':00'), button:has-text(':30')")
        second_time_btn = time_buttons2.first
        await expect(second_time_btn).to_be_visible(timeout=10000)
        second_time_text = await second_time_btn.inner_text()
        await second_time_btn.click()
        await zero_page.wait_for_timeout(500)
        print(f"  두 번째 예약 시간: {second_time_text}")

        # 예약하기 → 결제 페이지
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
        await zero_page.screenshot(path=str(SHOT_DIR / "cancel_00_second_booking.png"))
        print("  ✓ 두 번째 예약 완료 (컷 > 남성컷)")
        print("✓ Phase 2 완료\n")

        # ── Phase 3: 캘린더 → 내일 이동 → 상세 → 취소 ──
        print("=== Phase 3: 캘린더 → 상세 → 취소 ===")
        await crm_page.bring_to_front()
        await _switch_shop(crm_page, shop_name)

        # 캘린더 이동
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

        # 딤머 다시 닫기
        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 내일 날짜로 이동 (fc-next-button)
        d = reservation_date
        target = f"3. {d.day}"
        body = await crm_page.locator("body").inner_text()
        if target not in body:
            next_btn = crm_page.locator("button.fc-next-button").first
            await expect(next_btn).to_be_visible(timeout=10000)
            await next_btn.click()
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(2000)
            print(f"  ✓ 내일({d.month}/{d.day})로 이동")
        else:
            print(f"  ✓ 이미 내일({d.month}/{d.day}) 표시 중")

        # 딤머 다시 닫기
        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 첫 번째 예약 블록 클릭 → 상세 페이지로 이동
        block = crm_page.locator("div.booking-normal").first
        await expect(block).to_be_visible(timeout=15000)
        await block.click(force=True)
        await crm_page.wait_for_timeout(3000)
        await crm_page.wait_for_load_state("networkidle")
        first_detail_url = crm_page.url
        print(f"  ✓ 상세 페이지: {first_detail_url}")

        # 공비서 마크 확인
        b2c = crm_page.locator("svg[icon='serviceB2c'], svg.ZERO_B2C").first
        try:
            await expect(b2c).to_be_visible(timeout=5000)
            print("  ✓ 공비서 마크 확인")
        except Exception:
            print("  ⚠ 공비서 마크 미매칭")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_01_detail.png"))

        # 상세 페이지에서 "예약 확정" 드롭다운 → 예약 취소
        sb = crm_page.get_by_role("button", name="예약 확정").first
        if await sb.count() == 0:
            sb = crm_page.locator("button").filter(has_text="예약 확정").first
        await expect(sb).to_be_visible(timeout=15000)
        await sb.click()
        await crm_page.wait_for_timeout(1000)

        co = crm_page.get_by_text("예약 취소").first
        await expect(co).to_be_visible(timeout=5000)
        await co.click()
        await crm_page.wait_for_timeout(1000)

        # 취소 모달
        modal = crm_page.locator("[role='dialog']:visible, #modal-content:visible").first
        await expect(modal).to_be_visible(timeout=10000)
        print("  ✓ 취소 모달 노출")

        mt = await modal.inner_text()
        if "환불 방식" not in mt:
            print("  ✓ 환불 방식 미노출 (예약금 없는 샵)")
        assert "취소 사유" in mt
        print("  ✓ 취소 사유 섹션 노출")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_02_modal.png"))

        # 디폴트 사유
        dr = modal.get_by_text(re.compile(r"시술이 어려운|다른 시간")).first
        await expect(dr).to_be_visible(timeout=5000)
        await dr.click()
        reason_text = await dr.inner_text()
        print(f"  ✓ 디폴트 사유: '{reason_text}'")

        cb = modal.get_by_role("button", name=re.compile(r"예약\s*취소")).first
        await expect(cb).to_be_visible(timeout=5000)
        await cb.click()
        await crm_page.wait_for_timeout(2000)
        await crm_page.wait_for_load_state("networkidle")

        try:
            im = await modal.is_visible(timeout=2000)
        except Exception:
            im = False
        assert not im, "모달 안 닫힘"
        print("  ✓ 예약 취소 완료")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_03_complete.png"))
        print("✓ Phase 3 완료\n")

        # ── Phase 4: 취소 사유 검증 ──
        print("=== Phase 4: 취소 사유 검증 ===")
        await crm_page.wait_for_timeout(2000)

        # 취소된 예약 상세로 직접 이동
        await crm_page.goto(first_detail_url)
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(2000)
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_04_detail.png"))

        # 상세 페이지에서 배너 확인
        banner = crm_page.locator("h5.banner-title").filter(has_text="샵에서 취소한 예약")
        if await banner.count() == 0:
            banner = crm_page.get_by_text(re.compile(r"샵에서 취소한 예약")).first

        await expect(banner).to_be_visible(timeout=10000)
        print(f"  ✓ 취소 배너: '{await banner.inner_text()}'")

        rel = crm_page.locator("p.banner-desc").first
        if await rel.count() == 0:
            rel = crm_page.get_by_text(re.compile(r"취소\s*사유")).first
        await expect(rel).to_be_visible(timeout=5000)
        displayed = await rel.inner_text()
        print(f"  ✓ 취소 사유: '{displayed}'")
        assert reason_text[:10] in displayed, f"불일치! '{reason_text}' vs '{displayed}'"
        print("  ✓ 취소 사유 일치!")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_05_verified.png"))
        print("✓ Phase 4 완료\n")

        # ── Phase 4.5: 두 번째 예약 매출 등록 ──
        print("=== Phase 4.5: 두 번째 예약 매출 등록 ===")
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

        # "일" 보기
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

        # 내일로 이동
        body = await crm_page.locator("body").inner_text()
        if f"3. {d.day}" not in body:
            next_btn = crm_page.locator("button.fc-next-button").first
            await expect(next_btn).to_be_visible(timeout=10000)
            await next_btn.click()
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(2000)

        # 딤머 닫기
        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 남은 활성 예약 블록 클릭
        male_block = crm_page.locator("div.booking-normal").first
        await expect(male_block).to_be_visible(timeout=15000)
        await male_block.click(force=True)
        await crm_page.wait_for_timeout(3000)
        await crm_page.wait_for_load_state("networkidle")
        second_detail_url = crm_page.url
        print(f"  ✓ 두 번째 예약 상세: {second_detail_url}")

        # 예약일시 확인
        detail_text = await crm_page.locator("body").inner_text()
        assert f"{d.day}" in detail_text, "예약일시 확인 실패"
        print(f"  ✓ 예약일시 확인: {d.month}/{d.day}")

        # 시술 메뉴 확인
        if "남성컷" in detail_text:
            print("  ✓ 시술 메뉴: 남성컷 확인")
        elif "여성컷" in detail_text:
            print("  ✓ 시술 메뉴: 여성컷 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_05a_male_detail.png"))

        # [매출 등록] 버튼 클릭
        sales_btn = crm_page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
        await expect(sales_btn).to_be_visible(timeout=10000)
        await sales_btn.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(2000)
        print(f"  ✓ 매출 등록 페이지: {crm_page.url}")

        # 남은 결제 금액 확인
        sales_text = await crm_page.locator("body").inner_text()
        if "18,000" in sales_text:
            print("  ✓ 남은 결제 금액: 18,000원 (남성컷)")
        elif "20,000" in sales_text:
            print("  ✓ 남은 결제 금액: 20,000원 (여성컷)")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_05b_sales_page.png"))

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
        await crm_page.goto(second_detail_url)
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(2000)
        sales_label = crm_page.locator("h4.SALE.disabled:has-text('매출 등록')").first
        if await sales_label.count() == 0:
            sales_label = crm_page.locator("h4:has-text('매출 등록')").first
        await expect(sales_label).to_be_visible(timeout=10000)
        print("  ✓ 매출 등록 완료 상태 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_05c_sales_done.png"))
        print("✓ Phase 4.5 완료\n")

        # ── Phase 5: 공비서 예약 OFF → B2C 미노출 ──
        print("=== Phase 5: 공비서 예약 OFF → B2C 미노출 ===")
        await crm_page.goto(f"{CRM_BASE_URL}/b2c/setting")
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        if await _is_toggle_on(crm_page):
            await _set_toggle(crm_page, turn_on=False)
            print("  ✓ 공비서 예약 OFF")
        else:
            print("  ✓ 이미 OFF")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_06_toggle_off.png"))

        await zero_page.bring_to_front()
        await _open_nearby_list(zero_page)
        await zero_page.screenshot(path=str(SHOT_DIR / "cancel_07_nearby_off.png"))
        assert not await _is_shop_visible_in_nearby(zero_page, shop_name), \
            f"비활성화 후 '{shop_name}' 아직 노출"
        print("  ✓ B2C 미노출 확인")
        print("✓ Phase 5 완료\n")

        print("=== 전체 테스트 성공! ===")

    finally:
        for p in [zero_page, crm_page]:
            if p and not p.is_closed():
                await p.close()
        if zero_context:
            await zero_context.close()
        await runner.teardown()
