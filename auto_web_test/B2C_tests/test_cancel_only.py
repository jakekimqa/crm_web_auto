"""
Phase 3 취소 모달 headless 디버그용 최소 스크립트
Runner.create_new_shop() + 입점 → B2C 예약 1건 → CRM 캘린더에서 취소
"""
import asyncio, os, re, sys
from datetime import datetime
from pathlib import Path

import pytest
from playwright.async_api import expect

sys.path.append(str(Path(__file__).resolve().parents[2]))
from auto_web_test.B2C_tests.test_b2b_b2c_shop_activation_flow import (
    ShopActivationRunner, _switch_shop, _make_reservation, _kakao_login,
    _get_shop_id_from_crm, _crm_login,
    CRM_BASE_URL, ZERO_BASE_URL,
)


@pytest.mark.asyncio
async def test_cancel_modal_only():
    shop_name = f"{datetime.now():%m%d}_취소디버그"
    runner = ShopActivationRunner()
    runner.headless = os.getenv("B2B_HEADLESS", "1") == "1"

    try:
        # === 1. 샵 생성 + 입점 ===
        print(f"\n=== 1. 샵 생성 + 입점: {shop_name} ===")
        await runner.setup()
        await runner.login()
        await runner.create_new_shop()
        shop_name = f"{runner.mmdd}_배포_테스트"  # create_new_shop이 사용하는 이름
        try:
            await runner.enable_gong_booking_after_shop_creation()
        except Exception as exc:
            if "토글이 ON 상태가 아닙니다" not in str(exc):
                raise
        print(f"  ✓ 샵 생성 + 입점: {shop_name}")

        # === 2. B2C 예약 1건 ===
        print("\n=== 2. B2C 예약 ===")
        crm_page = await runner.context.new_page()
        zero_context = await runner.browser.new_context()
        zero_page = await zero_context.new_page()

        await crm_page.bring_to_front()
        await _crm_login(crm_page)
        await _switch_shop(crm_page, shop_name)

        shop_id = await _get_shop_id_from_crm(crm_page)
        print(f"  shopId: {shop_id}")

        await zero_page.bring_to_front()
        await zero_page.goto(f"{ZERO_BASE_URL}/shop/{shop_id}")
        try:
            await zero_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # 카카오 로그인 (필요시)
        login_btn = zero_page.locator("a[href*='/login']").first
        if await login_btn.count() > 0 and await login_btn.is_visible():
            await login_btn.click()
            try:
                await zero_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
        await _kakao_login(zero_page)
        await zero_page.goto(f"{ZERO_BASE_URL}/shop/{shop_id}")
        try:
            await zero_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        reservation_date = await _make_reservation(zero_page, shop_name, shop_id)
        print(f"  ✓ 예약 완료 (날짜: {reservation_date})")

        # === 3. CRM 캘린더 → 취소 모달 ===
        print("\n=== 3. 취소 모달 테스트 ===")
        await crm_page.bring_to_front()
        await crm_page.goto(f"{CRM_BASE_URL}/book/calendar")
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)

        # 딤머 + 일 보기
        for attempt in range(3):
            for _ in range(5):
                dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
                if await dim.count() > 0:
                    await dim.click(force=True)
                    await crm_page.wait_for_timeout(500)
                else:
                    break
            for name in ["일", "날짜별"]:
                btn = crm_page.get_by_role("button", name=name).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(force=True)
                    try:
                        await crm_page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        pass
                    await crm_page.wait_for_timeout(1000)
                    break
            h = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
            if h.strip().count(".") >= 2:
                print(f"  ✓ 일 보기: {h.strip()}")
                break

        # 예약 날짜로 이동
        d = reservation_date
        target_day = f"{d.month}. {d.day}"
        header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        for _ in range(10):
            if target_day in header:
                break
            m = re.search(rf"{d.month}\.\s*(\d+)", header)
            btn_cls = "fc-next-button" if (not m or int(m.group(1)) < d.day) else "fc-prev-button"
            await crm_page.locator(f"button.{btn_cls}").first.click()
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)
            header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        print(f"  ✓ 캘린더: {header.strip()}")

        # 딤머/공지 닫기
        for _ in range(5):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break
        try:
            dismiss = crm_page.locator("text=하루 동안 보지 않기").first
            await dismiss.wait_for(state="visible", timeout=2000)
            await dismiss.click()
            await crm_page.wait_for_timeout(500)
            print("  ✓ 공지 팝업 닫기")
        except Exception:
            pass

        # 예약 블록 클릭
        block = crm_page.locator("div.booking-normal").first
        await expect(block).to_be_visible(timeout=15000)
        await block.click(force=True)
        await crm_page.wait_for_timeout(2000)
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        print(f"  ✓ 예약 상세: {crm_page.url}")

        # 공지 팝업 닫기 (상세 진입 후)
        try:
            dismiss = crm_page.locator("text=하루 동안 보지 않기").first
            await dismiss.wait_for(state="visible", timeout=2000)
            await dismiss.click()
            await crm_page.wait_for_timeout(500)
            print("  ✓ 공지 팝업 닫기")
        except Exception:
            pass

        # 예약 확정 드롭다운 → 예약 취소
        sb = crm_page.get_by_role("button", name="예약 확정").first
        if await sb.count() == 0:
            sb = crm_page.locator("button").filter(has_text="예약 확정").first
        await expect(sb).to_be_visible(timeout=15000)
        await crm_page.screenshot(path="/tmp/cancel_debug_01_before_dropdown.png")
        await sb.click()
        await crm_page.wait_for_timeout(1000)
        await crm_page.screenshot(path="/tmp/cancel_debug_02_dropdown_open.png")

        co = crm_page.get_by_text("예약 취소").first
        await expect(co).to_be_visible(timeout=5000)
        await co.click()
        await crm_page.wait_for_timeout(1500)
        await crm_page.screenshot(path="/tmp/cancel_debug_03_modal_open.png")

        # 취소 모달
        modal = crm_page.locator("[role='dialog']:visible, #modal-content:visible").first
        await expect(modal).to_be_visible(timeout=10000)
        print("  ✓ 취소 모달 노출")

        # 사유 선택
        dr = modal.get_by_text(re.compile(r"시술이 어려운|다른 시간")).first
        await expect(dr).to_be_visible(timeout=5000)
        await dr.click()
        reason_text = await dr.inner_text()
        print(f"  ✓ 사유: '{reason_text}'")
        await crm_page.screenshot(path="/tmp/cancel_debug_04_reason_selected.png")

        # 취소 버튼
        cb = modal.get_by_role("button", name=re.compile(r"예약\s*취소")).first
        await expect(cb).to_be_visible(timeout=5000)
        bbox = await cb.bounding_box()
        print(f"  버튼 bbox: {bbox}, enabled: {await cb.is_enabled()}")

        # --- 5가지 클릭 방법 순차 시도 ---
        methods = [
            ("click()", lambda: cb.click()),
            ("click(force=True)", lambda: cb.click(force=True)),
            ("JS el.click()", lambda: cb.evaluate("el => el.click()")),
            ("dispatch_event", lambda: cb.dispatch_event("click")),
        ]

        for i, (name, action) in enumerate(methods, 1):
            print(f"\n  [방법{i}] {name}")
            await action()
            await crm_page.wait_for_timeout(2000)
            await crm_page.screenshot(path=f"/tmp/cancel_debug_{4+i:02d}_method{i}.png")
            try:
                im = await modal.is_visible()
            except Exception:
                im = False
            if not im:
                print(f"  ✓ 방법{i} 성공!")
                return
            print(f"    모달 아직 열림")

        # 방법 5: focus + Enter
        print("\n  [방법5] focus + Enter")
        await cb.focus()
        await crm_page.keyboard.press("Enter")
        await crm_page.wait_for_timeout(2000)
        await crm_page.screenshot(path="/tmp/cancel_debug_09_method5.png")
        try:
            im = await modal.is_visible()
        except Exception:
            im = False
        if not im:
            print("  ✓ 방법5 성공!")
            return

        print("\n  ✗ 모든 방법 실패")
        assert False, "모달 안 닫힘"

    finally:
        await runner.teardown()
