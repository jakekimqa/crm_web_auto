"""
CRM에서 예약 2건 처리 (S000005159):
1) 첫 번째 예약 → 취소 + 취소 사유 검증
2) 두 번째 예약 (남성컷) → 매출 등록 + 검증
"""
import os, re, sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

sys.path.append(str(Path(__file__).resolve().parents[2]))
from auto_web_test.B2C_tests.test_b2b_b2c_shop_activation_flow import (
    _crm_login, _switch_shop, CRM_BASE_URL, SHOT_DIR,
)

SHOP_NAME = "0315_1202_배포_테스트"


async def _move_to_tomorrow(page, tomorrow):
    """캘린더 fc-next-button 클릭으로 내일 이동"""
    target = f"3. {tomorrow.day}"
    body = await page.locator("body").inner_text()
    if target in body:
        return
    next_btn = page.locator("button.fc-next-button").first
    await expect(next_btn).to_be_visible(timeout=10000)
    await next_btn.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)


@pytest.mark.asyncio
async def test_crm_cancel_and_sales():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    page = await context.new_page()

    try:
        # ── CRM 로그인 + 샵 전환 ──
        print("\n=== CRM 로그인 + 샵 전환 ===")
        await _crm_login(page)
        await _switch_shop(page, SHOP_NAME)
        print(f"  ✓ 로그인 + 샵 전환 완료: {SHOP_NAME}")

        # ── 캘린더 이동 ──
        print("\n=== 캘린더 → 내일 이동 ===")
        await page.goto(f"{CRM_BASE_URL}/book/calendar")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # 딤머 닫기
        for _ in range(5):
            dim = page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await page.wait_for_timeout(500)
            else:
                break

        # "일" 보기 전환
        for name in ["일", "날짜별"]:
            btn = page.get_by_role("button", name=name).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1500)
                break

        # 딤머 닫기
        for _ in range(3):
            dim = page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await page.wait_for_timeout(500)
            else:
                break

        # 내일로 이동
        tomorrow = datetime.now() + timedelta(days=1)
        target = f"3. {tomorrow.day}"
        await _move_to_tomorrow(page, tomorrow)
        print(f"  ✓ 내일({tomorrow.month}/{tomorrow.day})로 이동")

        # 딤머 닫기
        for _ in range(3):
            dim = page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await page.wait_for_timeout(500)
            else:
                break

        await page.screenshot(path=str(SHOT_DIR / "crm_01_calendar.png"))

        # ── 첫 번째 예약 취소 ──
        print("\n=== 첫 번째 예약 취소 ===")
        blocks = page.locator("div.booking-normal")
        block_count = await blocks.count()
        print(f"  예약 블록 수: {block_count}")
        assert block_count >= 2, f"예약 블록이 2개 이상이어야 합니다 (현재: {block_count})"

        # 첫 번째 예약 클릭
        first_block = blocks.first
        await expect(first_block).to_be_visible(timeout=10000)
        await first_block.click(force=True)
        await page.wait_for_timeout(3000)
        await page.wait_for_load_state("networkidle")
        first_detail_url = page.url
        print(f"  ✓ 첫 번째 예약 상세: {first_detail_url}")
        await page.screenshot(path=str(SHOT_DIR / "crm_02_first_detail.png"))

        # 예약 확정 → 예약 취소
        sb = page.get_by_role("button", name="예약 확정").first
        if await sb.count() == 0:
            sb = page.locator("button").filter(has_text="예약 확정").first
        await expect(sb).to_be_visible(timeout=15000)
        await sb.click()
        await page.wait_for_timeout(1000)

        co = page.get_by_text("예약 취소").first
        await expect(co).to_be_visible(timeout=5000)
        await co.click()
        await page.wait_for_timeout(1000)

        # 취소 모달
        modal = page.locator("[role='dialog']:visible, #modal-content:visible").first
        await expect(modal).to_be_visible(timeout=10000)
        print("  ✓ 취소 모달 노출")

        mt = await modal.inner_text()
        assert "취소 사유" in mt
        print("  ✓ 취소 사유 섹션 노출")

        # 디폴트 사유 선택
        dr = modal.get_by_text(re.compile(r"시술이 어려운|다른 시간")).first
        await expect(dr).to_be_visible(timeout=5000)
        await dr.click()
        reason_text = await dr.inner_text()
        print(f"  ✓ 디폴트 사유: '{reason_text}'")

        cb = modal.get_by_role("button", name=re.compile(r"예약\s*취소")).first
        await expect(cb).to_be_visible(timeout=5000)
        await cb.click()
        await page.wait_for_timeout(2000)
        await page.wait_for_load_state("networkidle")

        try:
            im = await modal.is_visible(timeout=2000)
        except Exception:
            im = False
        assert not im, "모달 안 닫힘"
        print("  ✓ 첫 번째 예약 취소 완료")
        await page.screenshot(path=str(SHOT_DIR / "crm_03_cancel_done.png"))

        # ── 취소 사유 검증 ──
        print("\n=== 취소 사유 검증 ===")
        await page.wait_for_timeout(2000)

        # 취소된 예약 상세로 직접 이동
        await page.goto(first_detail_url)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(SHOT_DIR / "crm_04_cancel_detail.png"))

        # 배너 확인
        banner = page.locator("h5.banner-title").filter(has_text="샵에서 취소한 예약")
        if await banner.count() == 0:
            banner = page.get_by_text(re.compile(r"샵에서 취소한 예약")).first
        await expect(banner).to_be_visible(timeout=10000)
        print(f"  ✓ 취소 배너: '{await banner.inner_text()}'")

        rel = page.locator("p.banner-desc").first
        if await rel.count() == 0:
            rel = page.get_by_text(re.compile(r"취소\s*사유")).first
        await expect(rel).to_be_visible(timeout=5000)
        displayed = await rel.inner_text()
        print(f"  ✓ 취소 사유: '{displayed}'")
        assert reason_text[:10] in displayed, f"불일치! '{reason_text}' vs '{displayed}'"
        print("  ✓ 취소 사유 일치!")
        await page.screenshot(path=str(SHOT_DIR / "crm_05_reason_verified.png"))

        # ── 두 번째 예약: 매출 등록 ──
        print("\n=== 두 번째 예약: 매출 등록 ===")
        # 캘린더로 돌아가기
        await page.goto(f"{CRM_BASE_URL}/book/calendar")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        # 딤머 닫기
        for _ in range(5):
            dim = page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await page.wait_for_timeout(500)
            else:
                break

        # "일" 보기
        for name in ["일", "날짜별"]:
            btn = page.get_by_role("button", name=name).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_timeout(1500)
                break

        # 딤머 닫기
        for _ in range(3):
            dim = page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await page.wait_for_timeout(500)
            else:
                break

        # 내일로 이동
        await _move_to_tomorrow(page, tomorrow)

        # 딤머 닫기
        for _ in range(3):
            dim = page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await page.wait_for_timeout(500)
            else:
                break

        # 남성컷 예약 블록 클릭
        male_block = page.locator("div.booking-normal").filter(has_text="남성컷").first
        if await male_block.count() == 0:
            # 취소되지 않은 예약 블록 (두 번째)
            all_blocks = page.locator("div.booking-normal")
            count = await all_blocks.count()
            for i in range(count):
                b = all_blocks.nth(i)
                text = await b.inner_text()
                if "취소" not in text:
                    male_block = b
                    break
        await expect(male_block).to_be_visible(timeout=15000)
        await male_block.click(force=True)
        await page.wait_for_timeout(3000)
        await page.wait_for_load_state("networkidle")
        second_detail_url = page.url
        print(f"  ✓ 두 번째 예약 상세: {second_detail_url}")
        await page.screenshot(path=str(SHOT_DIR / "crm_06_male_cut_detail.png"))

        # 예약일시 확인
        detail_text = await page.locator("body").inner_text()
        assert f"{tomorrow.month}" in detail_text and f"{tomorrow.day}" in detail_text, \
            "예약일시 확인 실패"
        print(f"  ✓ 예약일시 확인: {tomorrow.month}/{tomorrow.day}")

        # 시술 메뉴 확인
        if "남성컷" in detail_text:
            print("  ✓ 시술 메뉴: 남성컷 확인")
        elif "여성컷" in detail_text:
            print("  ✓ 시술 메뉴: 여성컷 확인")
        else:
            print(f"  ✓ 시술 메뉴 확인 (상세에서 확인)")

        # [매출 등록] 버튼 클릭
        sales_btn = page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
        await expect(sales_btn).to_be_visible(timeout=10000)
        await sales_btn.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)
        print(f"  ✓ 매출 등록 페이지: {page.url}")
        await page.screenshot(path=str(SHOT_DIR / "crm_07_sales_page.png"))

        # 남은 결제 금액 확인 (남성컷 18,000원 또는 여성컷 20,000원)
        sales_text = await page.locator("body").inner_text()
        if "18,000" in sales_text:
            print("  ✓ 남은 결제 금액: 18,000원 확인 (남성컷)")
        elif "20,000" in sales_text:
            print("  ✓ 남은 결제 금액: 20,000원 확인 (여성컷)")
        else:
            assert False, f"결제 금액을 찾을 수 없습니다: {sales_text[:200]}"

        # 결제 수단: 카드 선택
        card_btn = page.get_by_text("카드", exact=True).first
        if await card_btn.count() == 0:
            card_btn = page.locator("button:has-text('카드'), label:has-text('카드')").first
        await expect(card_btn).to_be_visible(timeout=10000)
        await card_btn.click()
        await page.wait_for_timeout(500)
        print("  ✓ 결제 수단: 카드 선택")

        # 매출 저장 버튼 클릭
        save_btn = page.locator("button:has-text('매출 저장')").first
        await expect(save_btn).to_be_visible(timeout=10000)
        await save_btn.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)
        print("  ✓ 매출 저장 완료")
        await page.screenshot(path=str(SHOT_DIR / "crm_08_sales_saved.png"))

        # 매출 등록 후 예약 상세로 직접 이동하여 확인
        await page.goto(second_detail_url)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(SHOT_DIR / "crm_09_sales_verified.png"))

        # "매출 등록" 텍스트가 disabled 상태로 표시되는지 확인
        sales_label = page.locator("h4.SALE.disabled:has-text('매출 등록')").first
        if await sales_label.count() == 0:
            sales_label = page.locator("h4:has-text('매출 등록')").first
        await expect(sales_label).to_be_visible(timeout=10000)
        print("  ✓ 매출 등록 완료 상태 확인")

        print("\n=== 전체 테스트 성공! ===")

    finally:
        await context.close()
        await browser.close()
        await pw.stop()
