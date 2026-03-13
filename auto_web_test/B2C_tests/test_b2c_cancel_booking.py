"""
B2C 예약 → B2B 취소 → 취소 사유 검증 → 공비서 예약 OFF → B2C 미노출
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
    _make_reservation, _is_toggle_on, _set_toggle,
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
        reservation_date = await _make_reservation(zero_page, shop_name, shop_id)
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

        # 내일 날짜로 이동 (오른쪽 화살표 클릭)
        d = reservation_date
        target = f"3. {d.day}"
        body = await crm_page.locator("body").inner_text()
        if target not in body:
            # 오른쪽 화살표 (날짜 헤더 옆, x~1860 위치)
            arrows = await crm_page.evaluate('''() => {
                return Array.from(document.querySelectorAll('button'))
                    .filter(b => b.offsetParent !== null && b.querySelector('svg') && b.textContent.trim() === '')
                    .map((b, i) => ({
                        i, x: b.getBoundingClientRect().x, y: b.getBoundingClientRect().y,
                        w: b.getBoundingClientRect().width
                    }))
                    .filter(a => a.y < 50 && a.w < 40);
            }''')
            # 가장 오른쪽에 있는 화살표 = 다음 날
            if arrows:
                right_arrow = max(arrows, key=lambda a: a["x"])
                all_btns = crm_page.locator("button")
                arrow_btn = all_btns.nth(right_arrow["i"])
                # 찾은 인덱스가 아닌 좌표로 직접 클릭
                await crm_page.mouse.click(right_arrow["x"] + 10, right_arrow["y"] + 10)
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

        # 예약 블록 클릭 → 상세 페이지로 이동
        block = crm_page.locator("div.booking-normal").filter(has_text="헤렌테스트").first
        if await block.count() == 0:
            block = crm_page.locator("div.booking-normal").first
        if await block.count() == 0:
            block = crm_page.get_by_text("헤렌테스트").first
        await expect(block).to_be_visible(timeout=15000)
        await block.click(force=True)
        await crm_page.wait_for_timeout(3000)
        await crm_page.wait_for_load_state("networkidle")
        print(f"  ✓ 상세 페이지: {crm_page.url}")

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

        # 취소 후 캘린더로 돌아왔으므로, 내일로 이동 → 취소된 예약 클릭 → 상세
        # 내일 날짜로 이동 (오른쪽 화살표)
        body = await crm_page.locator("body").inner_text()
        target = f"3. {d.day}"
        if target not in body:
            arrows = await crm_page.evaluate("""() => {
                return Array.from(document.querySelectorAll('button'))
                    .filter(b => b.offsetParent !== null && b.querySelector('svg') && b.textContent.trim() === '')
                    .map((b, i) => ({
                        i, x: b.getBoundingClientRect().x, y: b.getBoundingClientRect().y,
                        w: b.getBoundingClientRect().width
                    }))
                    .filter(a => a.y < 50 && a.w < 40);
            }""")
            if arrows:
                ra = max(arrows, key=lambda a: a["x"])
                await crm_page.mouse.click(ra["x"] + 10, ra["y"] + 10)
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

        # 취소된 예약 블록 클릭 → 상세 페이지
        cc = crm_page.locator("div.booking-normal").filter(has_text="헤렌테스트").first
        if await cc.count() == 0:
            cc = crm_page.get_by_text("헤렌테스트").first
        await expect(cc).to_be_visible(timeout=15000)
        await cc.click(force=True)
        await crm_page.wait_for_timeout(3000)
        await crm_page.wait_for_load_state("networkidle")
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
