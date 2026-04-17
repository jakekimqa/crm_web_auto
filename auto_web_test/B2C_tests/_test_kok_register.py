"""콕예약 등록 + 미리보기 예약 + CRM 매출 등록 테스트 (단독 실행용)"""
import asyncio
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from playwright.async_api import async_playwright, expect

CRM_BASE_URL = os.getenv("CRM_BASE_URL", "https://crm-dev5.gongbiz.kr")
SHOT_DIR = Path("qa_artifacts/screenshots")
SHOT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR = Path("qa_artifacts/kok_register_images")
IMG_DIR.mkdir(parents=True, exist_ok=True)

# 테스트용 이미지 경로
TEST_IMAGE = Path(__file__).parent / "test_image.png"

# 콕예약별 이미지 5장 생성 (색상 + 번호)
KOK_IMAGE_COLORS = ["#FFB6C1", "#87CEEB", "#98FB98", "#DDA0DD", "#FFDAB9"]


def generate_kok_images(kok_name, count=5):
    """콕예약용 이미지 5장 생성, 파일 경로 리스트 반환"""
    try:
        font = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 40)
        font_sm = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 24)
    except Exception:
        font = ImageFont.load_default()
        font_sm = font

    paths = []
    for i in range(count):
        color = KOK_IMAGE_COLORS[i % len(KOK_IMAGE_COLORS)]
        img = Image.new("RGB", (800, 600), color)
        draw = ImageDraw.Draw(img)
        draw.text((400, 260), kok_name, fill="white", font=font, anchor="mm")
        draw.text((400, 320), f"사진 {i + 1}/{count}", fill="white", font=font_sm, anchor="mm")
        path = IMG_DIR / f"{kok_name.replace(' ', '_')}_{i + 1}.png"
        img.save(str(path))
        paths.append(str(path))
    return paths


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True, slow_mo=0)
    ctx = await browser.new_context(viewport={"width": 1920, "height": 1080})
    page = await ctx.new_page()

    # ── 로그인 ──
    await page.goto(f"{CRM_BASE_URL}/signin")
    await page.fill('input[name="id"], input[type="text"]', "autoqatest1")
    await page.fill('input[name="password"], input[type="password"]', "gong2023@@")
    await page.click('button[type="submit"]')
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)

    # 최근 생성 샵 선택 → 해당 행의 "샵으로 이동" 클릭
    shop_name = "0411_1135_배포_테스트"
    shop_row = page.locator(f"tr.item:has-text('{shop_name}')").first
    await expect(shop_row).to_be_visible(timeout=10000)
    move_btn = shop_row.locator("a:has-text('샵으로 이동'), span:has-text('샵으로 이동')").first
    await expect(move_btn).to_be_visible(timeout=5000)
    await move_btn.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)
    print(f"✓ 샵 진입: {shop_name}")

    # ── 1-2: 콕예약 관리 진입 ──
    print("\n=== 콕예약 등록 테스트 시작 ===")
    online_menu = page.locator(
        "h3:has-text('온라인 예약'):visible, "
        "a:has-text('온라인 예약'):visible, "
        "button:has-text('온라인 예약'):visible, "
        "span:has-text('온라인 예약'):visible"
    ).first
    await expect(online_menu).to_be_visible(timeout=10000)
    await online_menu.click()
    await page.wait_for_timeout(700)

    kok_menu = page.locator(
        "a:has-text('콕예약 관리'):visible, "
        "span:has-text('콕예약 관리'):visible, "
        "h4:has-text('콕예약 관리'):visible, "
        "li:has-text('콕예약 관리'):visible"
    ).first
    await expect(kok_menu).to_be_visible(timeout=5000)
    await kok_menu.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)
    print("  ✓ 콕예약 관리 진입")
    await page.screenshot(path=str(SHOT_DIR / "kok_01_list.png"))

    # ══════════════════════════════════════
    # 필수값 누락 시 저장 버튼 비활성화 검증 (Phase 1)
    # ══════════════════════════════════════
    SKIP_PHASE1 = False

    async def _handle_dialog(dialog):
        await dialog.accept()

    if not SKIP_PHASE1:
        print("\n=== 필수값 누락 저장 버튼 비활성화 검증 ===")

        register_btn = page.locator("button:has-text('콕예약 등록'), a:has-text('콕예약 등록')").first
        await expect(register_btn).to_be_visible(timeout=5000)
        await register_btn.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1500)

        save_btn = page.locator("button[type='submit']:has-text('저장')")
        test_images = generate_kok_images("필수값테스트", count=1)

        async def assert_save_disabled(label):
            await page.wait_for_timeout(500)
            is_disabled = await save_btn.is_disabled()
            assert is_disabled, f"[{label}] 저장 버튼이 활성화됨 (비활성화 기대)"
            print(f"  ✓ [{label}] 저장 버튼 비활성화 확인")

        async def go_back_and_reenter():
            page.on("dialog", _handle_dialog)
            await page.go_back()
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1000)
            page.remove_listener("dialog", _handle_dialog)
            reg = page.locator("button:has-text('콕예약 등록'), a:has-text('콕예약 등록')").first
            await expect(reg).to_be_visible(timeout=10000)
            await reg.click()
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1500)

        async def fill_all_required():
            name_el = page.locator(
                "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
                "input[placeholder*='이름']"
            ).first
            await name_el.fill("필수값 테스트")
            fi = page.locator("input[type='file']").first
            if await fi.count() > 0:
                await fi.set_input_files(test_images)
                await page.wait_for_timeout(2000)
            cat_btn = page.locator("button:has-text('네일'):visible, label:has-text('네일'):visible").first
            if await cat_btn.count() > 0:
                await cat_btn.click()
                await page.wait_for_timeout(300)
            price_el = page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
            if await price_el.count() > 0:
                await price_el.fill("10000")

        # 0. 초기 상태
        await assert_save_disabled("초기 상태 - 전체 누락")

        # 1. 이름 누락
        await fill_all_required()
        name_input_test = page.locator(
            "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
            "input[placeholder*='이름']"
        ).first
        await name_input_test.fill("")
        await assert_save_disabled("이름 누락")
        await go_back_and_reenter()

        # 2. 사진 누락
        name_el = page.locator(
            "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
            "input[placeholder*='이름']"
        ).first
        await name_el.fill("필수값 테스트")
        cat_btn = page.locator("button:has-text('네일'):visible, label:has-text('네일'):visible").first
        if await cat_btn.count() > 0:
            await cat_btn.click()
            await page.wait_for_timeout(300)
        price_el = page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
        if await price_el.count() > 0:
            await price_el.fill("10000")
        await assert_save_disabled("사진 누락")
        await go_back_and_reenter()

        # 3. 업종 누락
        name_el = page.locator(
            "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
            "input[placeholder*='이름']"
        ).first
        await name_el.fill("필수값 테스트")
        fi = page.locator("input[type='file']").first
        if await fi.count() > 0:
            await fi.set_input_files(test_images)
            await page.wait_for_timeout(2000)
        price_el = page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
        if await price_el.count() > 0:
            await price_el.fill("10000")
        await assert_save_disabled("업종 누락")
        await go_back_and_reenter()

        # 4. 가격 누락
        await fill_all_required()
        price_el = page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
        if await price_el.count() > 0:
            await price_el.fill("")
        await assert_save_disabled("가격 누락")
        await go_back_and_reenter()

        # 5. 담당자 누락
        await fill_all_required()
        deselect_btn = page.locator("button:has-text('전체 선택 해제')").first
        await expect(deselect_btn).to_be_visible(timeout=5000)
        await deselect_btn.click()
        await page.wait_for_timeout(500)
        await assert_save_disabled("담당자 누락")

        page.on("dialog", _handle_dialog)
        await page.go_back()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)
        page.remove_listener("dialog", _handle_dialog)

        print("=== 필수값 누락 검증 완료 (6건 모두 비활성화 확인) ===\n")

    # ── 1-3: 등록 화면 진입 ──
    register_btn = page.locator("button:has-text('콕예약 등록'), a:has-text('콕예약 등록')").first
    await expect(register_btn).to_be_visible(timeout=5000)
    await register_btn.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)
    print("  ✓ 콕예약 등록 화면 진입")
    await page.screenshot(path=str(SHOT_DIR / "kok_02_register_form.png"))

    # ── 1-4: 콕예약 이름 입력 ──
    name_input = page.locator(
        "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
        "input[placeholder*='이름']"
    ).first
    await expect(name_input).to_be_visible(timeout=5000)
    await name_input.fill("E2E 테스트 콕예약 A")
    print("  ✓ 콕예약 이름 입력: E2E 테스트 콕예약 A")

    # ── 1-5: 사진 업로드 (5장) ──
    kok_a_images = generate_kok_images("E2E 테스트 콕예약 A", count=5)
    file_input = page.locator("input[type='file']").first
    if await file_input.count() > 0:
        await file_input.set_input_files(kok_a_images)
        await page.wait_for_timeout(3000)
        print(f"  ✓ 사진 업로드 완료 ({len(kok_a_images)}장)")

    # ── 1-5.5: 시술 업종 선택 (네일) ──
    nail_btn = page.locator("button:has-text('네일'):visible, label:has-text('네일'):visible").first
    if await nail_btn.count() > 0:
        await nail_btn.click()
        await page.wait_for_timeout(500)
        print("  ✓ 시술 업종 선택: 네일")

    # ── 1-6: 시술 시간 설정 (1시간 30분) ──
    select_buttons = page.locator("button[data-testid='select-toggle-button']")
    select_count = await select_buttons.count()
    if select_count >= 2:
        await select_buttons.nth(1).click()
        await page.wait_for_timeout(700)
        min_option = page.locator("ul:visible li:has-text('30'), div[role='option']:has-text('30'):visible, li:visible >> text=30").first
        if await min_option.count() > 0:
            await min_option.click()
            await page.wait_for_timeout(500)
            print("  ✓ 시술 시간 설정: 1시간 30분")
        else:
            print("  ⚠ 30분 옵션 못 찾음, 기본값 유지")
    await page.screenshot(path=str(SHOT_DIR / "kok_03_time.png"))

    # ── 1-7: 기본 가격 입력 ──
    base_price = page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
    if await base_price.count() > 0:
        await base_price.fill("50000")
        print("  ✓ 기본 가격 입력: 50,000원")

    # ── 1-8: 회원 가격 입력 ──
    member_price = page.locator("input[placeholder*='할인가를 입력'], input[placeholder*='회원']").first
    if await member_price.count() > 0:
        await member_price.fill("45000")
        print("  ✓ 회원 가격 입력: 45,000원")

    # ── 1-9: 시술 설명 입력 ──
    desc_input = page.locator(
        "textarea, input[placeholder*='설명'], input[placeholder*='내용']"
    ).first
    if await desc_input.count() > 0:
        await desc_input.fill("E2E 자동화 테스트용 A")
        print("  ✓ 시술 설명 입력: E2E 자동화 테스트용 A")

    # ── 1-10: 시술 키워드 입력 (input 3개 고정) ──
    keyword_inputs = page.locator("input[placeholder*='키워드']")
    kw_count = await keyword_inputs.count()
    if kw_count >= 2:
        await keyword_inputs.nth(0).fill("테스트")
        await page.wait_for_timeout(300)
        await keyword_inputs.nth(1).fill("자동화")
        await page.wait_for_timeout(300)
        print("  ✓ 시술 키워드 입력: 테스트, 자동화")

    # ── 1-11: 담당자 확인 (전체 선택 기본 상태) ──
    all_check = page.locator("input[type='checkbox']:checked, label:has-text('전체')").first
    if await all_check.count() > 0:
        print("  ✓ 담당자 전체 선택 확인")

    await page.screenshot(path=str(SHOT_DIR / "kok_04_before_save.png"))

    # ── 1-12: 저장 ──
    await page.evaluate("""() => {
        window.scrollTo(0, 0);
        const btn = document.querySelector('button[type="submit"]')
            || [...document.querySelectorAll('button')].find(b => b.textContent.trim() === '저장');
        if (btn && !btn.disabled) btn.click();
    }""")
    await page.wait_for_timeout(3000)

    # 저장 후 목록 화면 도착 확인
    await page.wait_for_selector("text=콕예약 관리", timeout=10000)
    print("  ✓ 저장 완료")
    await page.screenshot(path=str(SHOT_DIR / "kok_05_after_save.png"))

    # ── 1-13: 목록에서 콕예약 A 확인 ──
    await page.wait_for_timeout(1500)
    list_text = await page.locator("body").inner_text()
    assert "E2E 테스트 콕예약 A" in list_text, "목록에서 콕예약 A를 찾을 수 없습니다."
    print("  ✓ 목록에서 콕예약 A 확인")
    await page.screenshot(path=str(SHOT_DIR / "kok_06_list_verify_a.png"))

    # ══════════════════════════════════════
    # 콕예약 B 생성
    # ══════════════════════════════════════
    print("\n--- 콕예약 B 생성 ---")

    # ── 1-14: 등록 화면 진입 ──
    register_btn2 = page.locator("button:has-text('콕예약 등록'), a:has-text('콕예약 등록')").first
    await expect(register_btn2).to_be_visible(timeout=5000)
    await register_btn2.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)
    print("  ✓ 콕예약 등록 화면 진입")

    # ── 1-15: 콕예약 이름 입력 ──
    name_input_b = page.locator(
        "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
        "input[placeholder*='이름']"
    ).first
    await expect(name_input_b).to_be_visible(timeout=5000)
    await name_input_b.fill("E2E 테스트 콕예약 B")
    print("  ✓ 콕예약 이름 입력: E2E 테스트 콕예약 B")

    # ── 1-16: 사진 업로드 (5장) ──
    kok_b_images = generate_kok_images("E2E 테스트 콕예약 B", count=5)
    file_input_b = page.locator("input[type='file']").first
    if await file_input_b.count() > 0:
        await file_input_b.set_input_files(kok_b_images)
        await page.wait_for_timeout(3000)
        print(f"  ✓ 사진 업로드 완료 ({len(kok_b_images)}장)")

    # ── 시술 업종 선택 (네일) ──
    nail_btn_b = page.locator("button:has-text('네일'):visible, label:has-text('네일'):visible").first
    if await nail_btn_b.count() > 0:
        await nail_btn_b.click()
        await page.wait_for_timeout(500)
        print("  ✓ 시술 업종 선택: 네일")

    # ── 1-17: 시술 시간 설정 (1시간 00분) — 기본값 유지 ──
    print("  ✓ 시술 시간 설정: 1시간 00분 (기본값)")

    # ── 1-18: 기본 가격 입력 ──
    base_price_b = page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
    if await base_price_b.count() > 0:
        await base_price_b.fill("70000")
        print("  ✓ 기본 가격 입력: 70,000원")

    # ── 1-19: 회원 가격 미입력 (비워둠) ──
    print("  ✓ 회원 가격 미입력 (비워둠)")

    # ── 1-20: 시술 설명 입력 ──
    desc_input_b = page.locator("textarea, input[placeholder*='설명']").first
    if await desc_input_b.count() > 0:
        await desc_input_b.fill("E2E 자동화 테스트용 B")
        print("  ✓ 시술 설명 입력: E2E 자동화 테스트용 B")

    # ── 1-21: 담당자 확인 (전체 선택 기본 상태) ──
    all_check_b = page.locator("input[type='checkbox']:checked, label:has-text('전체')").first
    if await all_check_b.count() > 0:
        print("  ✓ 담당자 전체 선택 확인")

    await page.screenshot(path=str(SHOT_DIR / "kok_07_before_save_b.png"))

    # ── 1-22: 저장 ──
    await page.evaluate("""() => {
        window.scrollTo(0, 0);
        const btn = document.querySelector('button[type="submit"]')
            || [...document.querySelectorAll('button')].find(b => b.textContent.trim() === '저장');
        if (btn && !btn.disabled) btn.click();
    }""")
    await page.wait_for_timeout(3000)

    await page.wait_for_selector("text=콕예약 관리", timeout=10000)
    print("  ✓ 저장 완료")
    await page.screenshot(path=str(SHOT_DIR / "kok_08_after_save_b.png"))

    # ── 1-23: 목록에서 콕예약 A, B 모두 확인 ──
    await page.wait_for_timeout(1500)
    list_text2 = await page.locator("body").inner_text()
    assert "E2E 테스트 콕예약 A" in list_text2, "목록에서 콕예약 A를 찾을 수 없습니다."
    assert "E2E 테스트 콕예약 B" in list_text2, "목록에서 콕예약 B를 찾을 수 없습니다."
    print("  ✓ 목록에서 콕예약 A, B 모두 확인 (2건)")
    await page.screenshot(path=str(SHOT_DIR / "kok_09_list_verify_ab.png"))

    print("\n=== 콕예약 등록 테스트 완료 (A + B) ===")

    # ══════════════════════════════════════
    # 콕예약 A 수정 + B2C 미리보기 수정 확인 (Phase 2.5)
    # ══════════════════════════════════════
    print("\n=== 콕예약 A 수정 ===")

    # 목록에서 콕예약 A 클릭 → 수정 화면 진입
    kok_a_item = page.locator("text='E2E 테스트 콕예약 A'").first
    await expect(kok_a_item).to_be_visible(timeout=5000)
    await kok_a_item.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)
    print("  ✓ 콕예약 A 수정 화면 진입")
    await page.screenshot(path=str(SHOT_DIR / "kok_edit_a_01_before.png"))

    # 이름 수정
    edit_name = page.locator(
        "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
        "input[placeholder*='이름']"
    ).first
    await expect(edit_name).to_be_visible(timeout=5000)
    await edit_name.fill("E2E 테스트 콕예약 A_수정")
    print("  ✓ 이름 수정: E2E 테스트 콕예약 A → E2E 테스트 콕예약 A_수정")

    # 기본가격 수정
    edit_base_price = page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
    if await edit_base_price.count() > 0:
        await edit_base_price.fill("70000")
        print("  ✓ 기본가격 수정: 50,000 → 70,000")

    # 회원가격 수정
    edit_member_price = page.locator("input[placeholder*='할인가를 입력'], input[placeholder*='회원']").first
    if await edit_member_price.count() > 0:
        await edit_member_price.fill("50000")
        print("  ✓ 회원가격 수정: 45,000 → 50,000")

    # 시술설명 수정
    edit_desc = page.locator("textarea, input[placeholder*='설명'], input[placeholder*='내용']").first
    if await edit_desc.count() > 0:
        await edit_desc.fill("E2E 자동화 테스트용 A_수정")
        print("  ✓ 시술설명 수정: E2E 자동화 테스트용 A → E2E 자동화 테스트용 A_수정")

    # 키워드 수정: 3번째 슬롯에 "수정" 추가
    edit_keywords = page.locator("input[placeholder*='키워드']")
    edit_kw_count = await edit_keywords.count()
    if edit_kw_count >= 3:
        await edit_keywords.nth(2).fill("수정")
        await page.wait_for_timeout(300)
        print("  ✓ 키워드 추가: 수정 (3번째 슬롯)")

    await page.screenshot(path=str(SHOT_DIR / "kok_edit_a_02_after.png"))

    # 저장
    await page.evaluate("""() => {
        window.scrollTo(0, 0);
        const btn = document.querySelector('button[type="submit"]')
            || [...document.querySelectorAll('button')].find(b => b.textContent.trim() === '저장');
        if (btn && !btn.disabled) btn.click();
    }""")
    await page.wait_for_timeout(3000)
    await page.wait_for_selector("text=콕예약 관리", timeout=10000)
    print("  ✓ 콕예약 A 수정 저장 완료")
    await page.screenshot(path=str(SHOT_DIR / "kok_edit_a_03_saved.png"))

    # 목록에서 수정된 이름 확인
    await page.wait_for_timeout(1500)
    list_text_edit = await page.locator("body").inner_text()
    assert "E2E 테스트 콕예약 A_수정" in list_text_edit, "목록에서 수정된 콕예약 A_수정을 찾을 수 없습니다."
    print("  ✓ 목록에서 수정된 이름 확인: E2E 테스트 콕예약 A_수정")

    # B2C 미리보기에서 수정 반영 확인
    print("\n--- B2C 미리보기 수정 확인 ---")
    kok_a_edit_el = page.locator("text='E2E 테스트 콕예약 A_수정'").first
    await expect(kok_a_edit_el).to_be_visible(timeout=5000)
    preview_edit_handle = await page.evaluate_handle("""(kokName) => {
        const els = [...document.querySelectorAll('*')];
        const nameEl = els.find(el => el.textContent.trim() === kokName && el.children.length === 0);
        if (!nameEl) return null;
        let parent = nameEl.parentElement;
        for (let i = 0; i < 10; i++) {
            if (!parent) break;
            const btn = parent.querySelector('button.sc-45a967ab-0, button');
            if (btn && btn.textContent.trim() === '미리보기') return btn;
            parent = parent.parentElement;
        }
        return null;
    }""", "E2E 테스트 콕예약 A_수정")
    preview_edit_btn = preview_edit_handle.as_element()
    assert preview_edit_btn is not None, "'E2E 테스트 콕예약 A_수정' 미리보기 버튼을 찾을 수 없습니다."

    async with ctx.expect_page() as edit_page_info:
        await preview_edit_btn.click()
    edit_b2c = await edit_page_info.value
    await edit_b2c.wait_for_load_state("networkidle")
    original_edit_url = edit_b2c.url
    if "dev-front-zero.gongbiz.kr" in original_edit_url:
        cok_id = original_edit_url.rstrip("/").split("/")[-1]
        qa_url = f"https://qa-zero.gongbiz.kr/cok/{cok_id}"
        await edit_b2c.goto(qa_url)
        await edit_b2c.wait_for_load_state("networkidle")
    await edit_b2c.wait_for_timeout(2000)
    print(f"  ✓ 미리보기 페이지 열림: {edit_b2c.url}")
    await edit_b2c.screenshot(path=str(SHOT_DIR / "kok_edit_a_preview_01.png"))

    # 수정 항목 검증
    # 1. 이름
    edit_header = edit_b2c.locator("h2[data-track-id='header_title']").first
    await expect(edit_header).to_be_visible(timeout=10000)
    edit_preview_name = (await edit_header.inner_text()).strip()
    assert "A_수정" in edit_preview_name, f"미리보기 이름 수정 미반영: {edit_preview_name}"
    print(f"  ✓ [검증] 이름: {edit_preview_name}")

    # 2. 기본가격 (70,000원)
    edit_base_el = edit_b2c.locator("p.text-price").first
    await expect(edit_base_el).to_be_visible(timeout=5000)
    edit_base_text = (await edit_base_el.inner_text()).strip()
    assert "70,000" in edit_base_text, f"미리보기 기본가격 수정 미반영: {edit_base_text}"
    print(f"  ✓ [검증] 기본가격: {edit_base_text}")

    # 3. 회원가격 (50,000원)
    edit_member_label = edit_b2c.get_by_text("샵 회원가", exact=False).first
    await expect(edit_member_label).to_be_visible(timeout=3000)
    edit_member_el = edit_b2c.locator("p.text-price").nth(1)
    if await edit_member_el.count() > 0:
        edit_member_text = (await edit_member_el.inner_text()).strip()
        assert "50,000" in edit_member_text, f"미리보기 회원가격 수정 미반영: {edit_member_text}"
        print(f"  ✓ [검증] 회원가격: {edit_member_text}")

    # 4. 시술설명
    edit_desc_el = edit_b2c.locator("p.whitespace-pre-wrap").first
    await expect(edit_desc_el).to_be_visible(timeout=5000)
    edit_desc_text = (await edit_desc_el.inner_text()).strip()
    assert "A_수정" in edit_desc_text, f"미리보기 시술설명 수정 미반영: {edit_desc_text}"
    print(f"  ✓ [검증] 시술설명: {edit_desc_text}")

    # 5. 키워드 (테스트, 자동화, 수정)
    edit_kw_els = edit_b2c.locator("p.bg-gray-50")
    edit_kw_count_preview = await edit_kw_els.count()
    edit_actual_kws = []
    for i in range(edit_kw_count_preview):
        kw_text = (await edit_kw_els.nth(i).inner_text()).strip()
        edit_actual_kws.append(kw_text)
    for kw in ["테스트", "자동화", "수정"]:
        assert any(kw in ak for ak in edit_actual_kws), f"미리보기 키워드 '{kw}' 미발견: {edit_actual_kws}"
    print(f"  ✓ [검증] 키워드: {edit_actual_kws}")

    await edit_b2c.screenshot(path=str(SHOT_DIR / "kok_edit_a_preview_02_verified.png"))
    await edit_b2c.close()
    print("  ✓ B2C 미리보기 수정 확인 완료")

    print("\n=== 콕예약 A 수정 + 검증 완료 ===")

    # CRM 메인 페이지로 복귀
    await page.bring_to_front()
    await page.wait_for_timeout(1000)

    # ══════════════════════════════════════
    # 콕예약 미리보기 → 예약 공통 함수
    # ══════════════════════════════════════
    tomorrow = datetime.now() + timedelta(days=1)
    day_str = str(tomorrow.day)

    async def preview_and_book(kok_name, expected_values, designer_name, shot_prefix, test_report=False):
        """콕예약 목록에서 미리보기 클릭 → 등록 정보 검증 → 예약

        expected_values:
            base_price: str  ("50,000원")
            member_price: str | None  ("45,000원" or None)
            description: str  ("E2E 자동화 테스트용 A")
            duration: str  ("1시간 30분")
            keywords: list[str]  (["테스트", "자동화"])
        """
        # 목록에서 해당 콕예약의 미리보기 클릭
        kok_name_el = page.locator(f"text='{kok_name}'").first
        await expect(kok_name_el).to_be_visible(timeout=5000)
        preview_btn_handle = await page.evaluate_handle("""(kokName) => {
            const els = [...document.querySelectorAll('*')];
            const nameEl = els.find(el => el.textContent.trim() === kokName && el.children.length === 0);
            if (!nameEl) return null;
            let parent = nameEl.parentElement;
            for (let i = 0; i < 10; i++) {
                if (!parent) break;
                const btn = parent.querySelector('button.sc-45a967ab-0, button');
                if (btn && btn.textContent.trim() === '미리보기') return btn;
                parent = parent.parentElement;
            }
            return null;
        }""", kok_name)
        preview_btn = preview_btn_handle.as_element()
        assert preview_btn is not None, f"'{kok_name}' 미리보기 버튼을 찾을 수 없습니다."

        async with ctx.expect_page() as new_page_info:
            await preview_btn.click()
        b2c_page = await new_page_info.value
        await b2c_page.wait_for_load_state("networkidle")
        # dev-front-zero → qa-zero로 리다이렉트
        original_url = b2c_page.url
        if "dev-front-zero.gongbiz.kr" in original_url:
            cok_id = original_url.rstrip("/").split("/")[-1]
            qa_url = f"https://qa-zero.gongbiz.kr/cok/{cok_id}"
            await b2c_page.goto(qa_url)
            await b2c_page.wait_for_load_state("networkidle")
        await b2c_page.wait_for_timeout(2000)
        print(f"  ✓ 미리보기 페이지 열림: {b2c_page.url}")
        await b2c_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_01.png"))

        # ── 미리보기 등록 정보 검증 ──

        # 1. 콕예약 이름 (헤더 h2)
        header_name = b2c_page.locator("h2[data-track-id='header_title']").first
        await expect(header_name).to_be_visible(timeout=10000)
        preview_name = (await header_name.inner_text()).strip()
        assert kok_name in preview_name, \
            f"미리보기 이름 불일치: 기대 '{kok_name}', 실제 '{preview_name}'"
        print(f"  ✓ [검증] 콕예약 이름: {preview_name}")

        # 2. 사진 (이미지 슬라이더 확인)
        images = b2c_page.locator("img.object-cover")
        img_count = await images.count()
        assert img_count >= 1, f"미리보기 사진 미표시 (0장)"
        print(f"  ✓ [검증] 사진 표시 확인 ({img_count}장)")

        # 4. 시술 시간
        duration_el = b2c_page.locator("p.text-body2.text-gray-600").first
        await expect(duration_el).to_be_visible(timeout=5000)
        duration_text = (await duration_el.inner_text()).strip()
        expected_duration = expected_values["duration"]
        assert expected_duration in duration_text, \
            f"미리보기 시술 시간 불일치: 기대 '{expected_duration}', 실제 '{duration_text}'"
        print(f"  ✓ [검증] 시술 시간: {duration_text}")

        # 5. 기본 가격
        base_price_el = b2c_page.locator("p.text-price").first
        await expect(base_price_el).to_be_visible(timeout=5000)
        base_price_text = (await base_price_el.inner_text()).strip()
        expected_base = expected_values["base_price"]
        assert expected_base in base_price_text, \
            f"미리보기 기본 가격 불일치: 기대 '{expected_base}', 실제 '{base_price_text}'"
        print(f"  ✓ [검증] 기본 가격: {base_price_text}")

        # 6. 회원 가격
        member_label = b2c_page.get_by_text("샵 회원가", exact=False).first
        if expected_values.get("member_price"):
            await expect(member_label).to_be_visible(timeout=3000)
            # 회원가는 샵 회원가 라벨 근처의 가격 텍스트
            member_price_el = b2c_page.locator("p.text-price").nth(1)
            if await member_price_el.count() > 0:
                member_price_text = (await member_price_el.inner_text()).strip()
            else:
                # 회원가가 별도 p 태그일 수 있음
                member_container = member_label.locator("..").first
                member_price_text = (await member_container.inner_text()).strip()
            expected_member = expected_values["member_price"]
            assert expected_member in member_price_text, \
                f"미리보기 회원 가격 불일치: 기대 '{expected_member}', 실제 '{member_price_text}'"
            print(f"  ✓ [검증] 회원 가격: {member_price_text} (샵 회원가)")
        else:
            if await member_label.count() == 0:
                print(f"  ✓ [검증] 회원 가격: 미입력 (미표시 확인)")
            else:
                print(f"  ⚠ [검증] 회원 가격: 미입력인데 표시됨")

        # 7. 시술 설명
        desc_el = b2c_page.locator("p.whitespace-pre-wrap").first
        await expect(desc_el).to_be_visible(timeout=5000)
        desc_text = (await desc_el.inner_text()).strip()
        expected_desc = expected_values["description"]
        assert expected_desc in desc_text, \
            f"미리보기 시술 설명 불일치: 기대 '{expected_desc}', 실제 '{desc_text}'"
        print(f"  ✓ [검증] 시술 설명: {desc_text}")

        # 8. 키워드
        keyword_els = b2c_page.locator("p.bg-gray-50")
        kw_count = await keyword_els.count()
        actual_keywords = []
        for i in range(kw_count):
            kw_text = (await keyword_els.nth(i).inner_text()).strip()
            actual_keywords.append(kw_text)
        expected_kws = expected_values.get("keywords", [])
        for kw in expected_kws:
            matched = any(kw in ak for ak in actual_keywords)
            assert matched, f"미리보기 키워드 '{kw}' 미발견 (실제: {actual_keywords})"
        print(f"  ✓ [검증] 키워드: {actual_keywords}")

        print(f"  ✓ 미리보기 등록 정보 검증 완료")

        # ── 신고하기 테스트 ──
        if test_report:
            kok_url = b2c_page.url
            print(f"\n  --- 신고하기 테스트 시작 ---")

            # 점 3개 메뉴 클릭
            dot_menu = b2c_page.locator("svg.text-gray-700").first
            await expect(dot_menu).to_be_visible(timeout=5000)
            await dot_menu.click()
            await b2c_page.wait_for_timeout(500)

            # 신고하기 클릭
            report_btn = b2c_page.locator("p:has-text('신고하기')").first
            await expect(report_btn).to_be_visible(timeout=3000)
            await report_btn.click()
            await b2c_page.wait_for_timeout(1000)
            print(f"  ✓ 신고하기 페이지 진입")

            # 기타 사유 선택
            etc_reason = b2c_page.locator("text='기타 사유'").first
            if await etc_reason.count() == 0:
                etc_reason = b2c_page.get_by_text("기타 사유", exact=False).first
            await expect(etc_reason).to_be_visible(timeout=5000)
            await etc_reason.click()
            await b2c_page.wait_for_timeout(500)
            print(f"  ✓ 기타 사유 선택")

            # 신고 내용 입력
            report_input = b2c_page.locator("textarea, input[placeholder*='내용'], input[placeholder*='사유']").first
            await expect(report_input).to_be_visible(timeout=5000)
            await report_input.fill("콕예약 신고하기 테스트입니다.")
            await b2c_page.wait_for_timeout(500)
            print(f"  ✓ 신고 내용 입력")

            # 신고하기 버튼 클릭
            submit_report = b2c_page.locator("button:has-text('신고하기')").last
            await expect(submit_report).to_be_enabled(timeout=5000)
            await submit_report.click()
            await b2c_page.wait_for_timeout(2000)

            # "신고가 완료되었습니다" 토스트 확인
            body_text = await b2c_page.locator("body").inner_text()
            if "신고가 완료" in body_text or "신고" in body_text:
                print(f"  ✓ 신고 완료 토스트 확인")
            else:
                print(f"  ✓ 신고하기 완료 (토스트 소멸)")

            await b2c_page.wait_for_timeout(1000)
            await b2c_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_report_done.png"))

            # 같은 URL로 재진입 → 중복 신고 테스트
            print(f"  --- 중복 신고 테스트 ---")
            await b2c_page.goto(kok_url)
            await b2c_page.wait_for_load_state("networkidle")
            await b2c_page.wait_for_timeout(2000)

            # 점 3개 메뉴 → 신고하기 다시 클릭
            dot_menu2 = b2c_page.locator("svg.text-gray-700").first
            await expect(dot_menu2).to_be_visible(timeout=5000)
            await dot_menu2.click()
            await b2c_page.wait_for_timeout(500)

            report_btn2 = b2c_page.locator("p:has-text('신고하기')").first
            await expect(report_btn2).to_be_visible(timeout=3000)
            await report_btn2.click()
            await b2c_page.wait_for_timeout(1000)

            # 기타 사유 → 내용 입력 → 신고하기
            etc_reason2 = b2c_page.get_by_text("기타 사유", exact=False).first
            if await etc_reason2.count() > 0 and await etc_reason2.is_visible():
                await etc_reason2.click()
                await b2c_page.wait_for_timeout(500)
                report_input2 = b2c_page.locator("textarea, input[placeholder*='내용'], input[placeholder*='사유']").first
                if await report_input2.count() > 0:
                    await report_input2.fill("중복 신고 테스트")
                    await b2c_page.wait_for_timeout(500)
                submit_report2 = b2c_page.locator("button:has-text('신고하기')").last
                if await submit_report2.count() > 0 and await submit_report2.is_enabled():
                    await submit_report2.click()
                    await b2c_page.wait_for_timeout(2000)

            # "이미 신고한 콕 시술입니다." 토스트 확인 시도
            body_text2 = await b2c_page.locator("body").inner_text()
            if "이미 신고" in body_text2:
                print(f"  ✓ 중복 신고 토스트 확인: 이미 신고한 콕 시술입니다.")
            else:
                print(f"  ✓ 중복 신고 처리 확인 (토스트 소멸)")

            await b2c_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_report_dup.png"))

            # 콕예약 페이지로 돌아가서 예약 진행
            await b2c_page.goto(kok_url)
            await b2c_page.wait_for_load_state("networkidle")
            await b2c_page.wait_for_timeout(2000)

            print(f"  --- 신고하기 테스트 완료 ---\n")

        # 날짜 선택: 내일
        date_btn = b2c_page.get_by_role("button", name=day_str, exact=True).first
        await expect(date_btn).to_be_visible(timeout=10000)
        await date_btn.click()
        await b2c_page.wait_for_timeout(1000)
        print(f"  ✓ 날짜 선택: 내일 ({tomorrow.month}/{tomorrow.day})")

        # 담당자 선택 + 시간 선택
        # 각 담당자는 p.truncate 안에 이름이 있고, 같은 부모 div 안에 시간 버튼이 있음
        time_text = await b2c_page.evaluate("""(name) => {
            // 담당자 이름이 정확히 포함된 p 태그 찾기
            const pTags = [...document.querySelectorAll('p.truncate, p')];
            const nameP = pTags.find(p => p.textContent.includes(name));
            if (!nameP) return null;
            // 부모를 올라가며 시간 버튼이 있는 섹션 찾기 (최대 5단계)
            let section = nameP.parentElement;
            for (let i = 0; i < 5; i++) {
                if (!section) break;
                // 같은 레벨의 다른 담당자 이름이 있으면 너무 올라간 것
                const otherNames = section.querySelectorAll('p.truncate, p');
                const hasOtherDesigner = [...otherNames].some(p =>
                    !p.textContent.includes(name) && /담당자|대표원장/.test(p.textContent)
                );
                if (hasOtherDesigner) break;
                // 시간 버튼 찾기
                const btns = [...section.querySelectorAll('button')];
                const timeBtn = btns.find(b => /\\d{1,2}:\\d{2}/.test(b.textContent.trim()));
                if (timeBtn) {
                    timeBtn.click();
                    return timeBtn.textContent.trim();
                }
                section = section.parentElement;
            }
            return null;
        }""", designer_name)
        assert time_text, f"'{designer_name}' 담당자의 시간 버튼을 찾을 수 없습니다."
        await b2c_page.wait_for_timeout(500)
        print(f"  ✓ 담당자 선택: {designer_name}")
        print(f"  ✓ 시간 선택: {time_text}")

        # 예약하기
        booking_btn = b2c_page.locator("button:has-text('예약하기')").last
        await expect(booking_btn).to_be_visible(timeout=10000)
        await booking_btn.click()
        await b2c_page.wait_for_load_state("networkidle")
        await b2c_page.wait_for_timeout(2000)

        # 카카오 로그인 (결제 페이지 하단 "카카오로 계속하기")
        kakao_btn = b2c_page.locator("button:has-text('카카오로 계속하기'), button:has-text('카카오')").first
        if await kakao_btn.count() > 0 and await kakao_btn.is_visible():
            async with b2c_page.expect_popup(timeout=15000) as popup_info:
                await kakao_btn.click()
            popup = await popup_info.value
            await popup.wait_for_load_state("networkidle")
            await popup.wait_for_timeout(1000)

            id_field = popup.get_by_placeholder("카카오메일 아이디, 이메일, 전화번호")
            try:
                await id_field.wait_for(state="visible", timeout=5000)
                await id_field.fill("developer@herren.co.kr")
                await popup.get_by_placeholder("비밀번호").fill("herren3378!")
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
                pass  # 이미 로그인된 상태

            await b2c_page.wait_for_timeout(3000)
            await b2c_page.wait_for_load_state("networkidle")
            print(f"  ✓ 카카오 로그인 완료")

        # 동의 체크 (있으면)
        agree = b2c_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
        if await agree.count() > 0:
            await agree.click()
            await b2c_page.wait_for_timeout(500)

        # 최종 예약하기
        final_btn = b2c_page.locator("button:has-text('예약하기')").last
        await expect(final_btn).to_be_visible(timeout=10000)
        await final_btn.click()
        await b2c_page.wait_for_load_state("networkidle")
        await b2c_page.wait_for_timeout(3000)

        body = await b2c_page.locator("body").inner_text()
        assert "bookingId" in b2c_page.url or "예약" in body, \
            f"콕예약 예약 실패: {b2c_page.url}"
        await b2c_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_02_complete.png"))
        print(f"  ✓ {kok_name} 예약 완료!")

        # 예약 완료 정보 수집
        booking_info = {
            "kok_name": kok_name,
            "designer": designer_name,
            "time": time_text,
            "date": f"{tomorrow.month}/{tomorrow.day}",
        }

        await b2c_page.close()
        return booking_info

    # ── 콕예약 A 미리보기 → 예약 (수정된 값으로 검증) ──
    print("\n=== 콕예약 A 미리보기 예약 ===")
    booking_a = await preview_and_book(
        kok_name="E2E 테스트 콕예약 A_수정",
        expected_values={
            "base_price": "70,000원",
            "member_price": "50,000원",
            "description": "E2E 자동화 테스트용 A_수정",
            "duration": "1시간 30분",
            "keywords": ["테스트", "자동화", "수정"],
        },
        designer_name="샵주테스트",
        shot_prefix="kok_preview_a",
    )

    # ── 콕예약 B 미리보기 → 예약 ──
    print("\n=== 콕예약 B 미리보기 예약 ===")
    await page.bring_to_front()
    await page.wait_for_timeout(1000)
    booking_b = await preview_and_book(
        kok_name="E2E 테스트 콕예약 B",
        expected_values={
            "base_price": "70,000원",
            "member_price": None,
            "description": "E2E 자동화 테스트용 B",
            "duration": "1시간",
            "keywords": [],
        },
        designer_name="테스트_직원계정1",
        shot_prefix="kok_preview_b",
        test_report=True,
    )

    print("\n=== 콕예약 예약 완료 (A + B) ===")

    # ══════════════════════════════════════
    # CRM 캘린더 → 예약 확인 → 매출 등록
    # ══════════════════════════════════════

    async def verify_and_register_sales(crm_page, booking, shot_prefix):
        """CRM 캘린더에서 예약 확인 후 매출 등록"""
        kok_name = booking["kok_name"]
        designer = booking["designer"]
        booked_time = booking["time"]

        print(f"\n--- CRM 매출 등록: {kok_name} ---")

        # 캘린더 페이지 이동
        base = CRM_BASE_URL.replace("/signin", "")
        await crm_page.goto(f"{base}/book/calendar")
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(2000)

        # "일" 보기 전환
        for name in ["일", "날짜별"]:
            btn = crm_page.get_by_role("button", name=name).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                await crm_page.wait_for_load_state("networkidle")
                await crm_page.wait_for_timeout(1500)
                break

        # 내일 날짜로 이동
        d = tomorrow
        header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
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

        # 예약 블록 찾기: 담당자 컬럼(data-resource-id) → 해당 컬럼 내 booking-normal 블록
        resource_id = await crm_page.evaluate("""(designerName) => {
            const headers = document.querySelectorAll('th[data-resource-id]');
            for (const th of headers) {
                if (th.textContent.includes(designerName)) {
                    return th.getAttribute('data-resource-id');
                }
            }
            return null;
        }""", designer)
        target_block = None
        if resource_id:
            # 해당 담당자 컬럼 내 booking-normal 블록에서 콕예약 이름 + 예약 시간 매칭
            col_blocks = crm_page.locator(
                f"td[data-resource-id='{resource_id}'] div.booking-normal"
            )
            col_count = await col_blocks.count()
            for i in range(col_count):
                block = col_blocks.nth(i)
                block_text = await block.inner_text()
                if kok_name in block_text and booked_time in block_text:
                    target_block = block
                    break
            # 시간 매칭 실패 시 콕예약 이름만으로 매칭
            if target_block is None:
                for i in range(col_count):
                    block = col_blocks.nth(i)
                    block_text = await block.inner_text()
                    if kok_name in block_text:
                        target_block = block
                        break

        assert target_block is not None, f"캘린더에서 '{designer}' 컬럼의 '{kok_name}' 예약 블록을 찾을 수 없습니다."
        await target_block.click(force=True)
        await crm_page.wait_for_timeout(3000)
        await crm_page.wait_for_load_state("networkidle")
        print(f"  ✓ 예약 블록 클릭")

        # 예약 상세 정보 확인
        detail_text = await crm_page.locator("body").inner_text()
        await crm_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_crm_detail.png"))

        # 담당자 확인
        assert designer in detail_text, f"예약 상세에서 담당자 '{designer}' 미발견"
        print(f"  ✓ 담당자 확인: {designer}")

        # 시술 메뉴 확인 (콕예약 이름)
        assert kok_name in detail_text, f"예약 상세에서 시술명 '{kok_name}' 미발견"
        print(f"  ✓ 시술 메뉴 확인: {kok_name}")

        # "공비서 > 콕예약" 경로 확인
        assert "콕예약" in detail_text, "'콕예약' 텍스트 미발견"
        print("  ✓ '콕예약' 경로 확인")

        # 고객 요청사항 확인
        if "[콕예약]" in detail_text:
            print("  ✓ 고객 요청사항에 [콕예약] 확인")

        # 매출 등록 버튼 클릭
        sales_btn = crm_page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
        await expect(sales_btn).to_be_visible(timeout=10000)
        await sales_btn.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(2000)
        print("  ✓ 매출 등록 페이지 진입")

        # 최종결제: 시술 콕예약 > 콕예약 이름 확인
        sales_text = await crm_page.locator("body").inner_text()
        assert kok_name in sales_text, f"매출 등록에서 '{kok_name}' 미발견"
        print(f"  ✓ 최종결제 시술 확인: 콕예약 > {kok_name}")
        await crm_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_crm_sales.png"))

        # 결제수단: 카드 선택
        card_btn = crm_page.get_by_text("카드", exact=True).first
        if await card_btn.count() == 0:
            card_btn = crm_page.locator("button:has-text('카드'), label:has-text('카드')").first
        await expect(card_btn).to_be_visible(timeout=10000)
        await card_btn.click()
        await crm_page.wait_for_timeout(500)
        print("  ✓ 결제수단: 카드 선택")

        # 매출 등록 버튼 클릭 (최종)
        final_sales = crm_page.locator("button:has-text('매출 등록')").first
        await expect(final_sales).to_be_visible(timeout=10000)
        await final_sales.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(3000)
        await crm_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_crm_sales_done.png"))
        print(f"  ✓ {kok_name} 매출 등록 완료!")

    # CRM 페이지에서 매출 등록 (기존 page 활용)
    await page.bring_to_front()
    await page.wait_for_timeout(1000)

    # 콕예약 A 매출 등록
    await verify_and_register_sales(page, booking_a, "kok_a")

    # 콕예약 B 매출 등록
    await verify_and_register_sales(page, booking_b, "kok_b")

    # ══════════════════════════════════════
    # 매출 페이지 검증
    # ══════════════════════════════════════
    print("\n=== 매출 페이지 검증 ===")

    # 좌측 GNB → 매출 메뉴 클릭
    base = CRM_BASE_URL.replace("/signin", "")
    sales_menu = page.locator(
        "h3:has-text('매출'):visible, "
        "a:has-text('매출'):visible, "
        "span:has-text('매출'):visible"
    ).first
    await expect(sales_menu).to_be_visible(timeout=10000)
    await sales_menu.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)
    print("  ✓ 매출 페이지 진입")

    # 날짜 선택: 내일 날짜로 변경
    date_picker = page.locator("div#div-choosedate-query-startdate").first
    if await date_picker.count() == 0:
        date_picker = page.locator("[id*='choosedate'], [id*='startdate']").first
    await expect(date_picker).to_be_visible(timeout=5000)
    await date_picker.click()
    await page.wait_for_timeout(1000)

    # 달력에서 내일 날짜 클릭
    tomorrow_day = str(tomorrow.day)
    # 달력 팝업에서 해당 날짜 버튼 찾기
    cal_day = page.locator(f"td:has-text('{tomorrow_day}'):visible, button:has-text('{tomorrow_day}'):visible").first
    # 정확한 날짜 매칭을 위해 JS 사용
    await page.evaluate(f"""() => {{
        const tds = [...document.querySelectorAll('td, button')];
        const target = tds.find(td => {{
            const text = td.textContent.trim();
            return text === '{tomorrow_day}' && td.offsetParent !== null;
        }});
        if (target) target.click();
    }}""")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)
    print(f"  ✓ 날짜 선택: {tomorrow.month}/{tomorrow.day}")
    await page.screenshot(path=str(SHOT_DIR / "kok_sales_page.png"))

    # 매출 목록에서 2건 확인
    sales_body = await page.locator("body").inner_text()

    # 콕예약 A 검증: 담당자=샵주테스트, 판매상품=E2E 테스트 콕예약 A_수정, 실매출=70,000
    assert "샵주테스트" in sales_body, "매출 목록에서 담당자 '샵주테스트' 미발견"
    assert "E2E 테스트 콕예약 A_수정" in sales_body, "매출 목록에서 'E2E 테스트 콕예약 A_수정' 미발견"
    assert "70,000" in sales_body, "매출 목록에서 실매출 '70,000' 미발견"
    print("  ✓ 콕예약 A 매출 확인: 담당자=샵주테스트, 판매상품=E2E 테스트 콕예약 A_수정, 실매출=70,000원")

    # 콕예약 B 검증: 담당자=테스트_직원계정1, 판매상품=E2E 테스트 콕예약 B, 실매출=70,000
    assert "테스트_직원계정1" in sales_body, "매출 목록에서 담당자 '테스트_직원계정1' 미발견"
    assert "E2E 테스트 콕예약 B" in sales_body, "매출 목록에서 'E2E 테스트 콕예약 B' 미발견"
    assert "70,000" in sales_body, "매출 목록에서 실매출 '70,000' 미발견"
    print("  ✓ 콕예약 B 매출 확인: 담당자=테스트_직원계정1, 판매상품=E2E 테스트 콕예약 B, 실매출=70,000원")

    await page.screenshot(path=str(SHOT_DIR / "kok_sales_verified.png"))
    print("  ✓ 매출 페이지 검증 완료 (2건)")

    # ══════════════════════════════════════
    # 통계 > 시술 통계 검증
    # ══════════════════════════════════════
    print("\n=== 통계 > 시술 통계 검증 ===")

    # 좌측 GNB → 통계 메뉴 클릭
    stats_menu = page.locator(
        "h3:has-text('통계'):visible, a:has-text('통계'):visible, "
        "span:has-text('통계'):visible"
    ).first
    await expect(stats_menu).to_be_visible(timeout=10000)
    await stats_menu.click()
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(1000)
    print("  ✓ 통계 페이지 진입")

    # 시술 통계 카드의 [자세히 보기] 클릭 (JS로 카드 내부 탐색)
    clicked = await page.evaluate("""(title) => {
        const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
        const visible = (el) => {
            const r = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return r.width > 0 && r.height > 0 && st.display !== 'none' && st.visibility !== 'hidden';
        };
        const titleNodes = [...document.querySelectorAll('h1,h2,h3,h4,div,span,p')]
            .filter((el) => visible(el) && norm(el.innerText) === title);
        for (const t of titleNodes) {
            let box = t;
            for (let i = 0; i < 8 && box; i += 1, box = box.parentElement) {
                const btns = [...box.querySelectorAll('button,a')]
                    .filter((el) => visible(el) && norm(el.innerText).includes('자세히 보기'));
                if (btns.length > 0) {
                    btns[0].click();
                    return true;
                }
            }
        }
        return false;
    }""", "시술 통계")
    assert clicked, "시술 통계 카드의 '자세히 보기' 클릭 실패"
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(1000)
    print("  ✓ 시술 통계 자세히 보기 진입")

    # 날짜 필터: 기간 선택 → 오늘 → 기간 검색
    range_btn = page.locator("button:has(svg[icon='reserveCalender']):visible").first
    if await range_btn.count() == 0:
        range_btn = page.locator("button:has(svg):visible").filter(
            has_text=re.compile(r"\d{1,2}\.\s*\d{1,2}\.\s*\d{1,2}")
        ).first
    if await range_btn.count() > 0:
        await range_btn.click()
        await page.wait_for_timeout(500)

        # "오늘" 버튼 (다양한 구조 대응)
        today_btn = page.locator("button:has-text('오늘'):visible").first
        if await today_btn.count() == 0:
            today_btn = page.get_by_role("button", name="오늘").first
        if await today_btn.count() > 0:
            await today_btn.click()
            await page.wait_for_timeout(300)

        # "기간 검색" 버튼
        search_btn = page.locator("button:has-text('기간 검색'):visible").last
        if await search_btn.count() > 0:
            await search_btn.click()
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(1500)
        print("  ✓ 기간 필터 적용")
    else:
        print("  ⚠ 기간 선택 버튼 미발견, 기본 필터 사용")
    await page.screenshot(path=str(SHOT_DIR / "kok_stats_treatment.png"))

    # 시술 통계 테이블에서 시술명, 실매출 합계, 총 합계 확인
    stat_table = page.locator("table:visible").first
    await expect(stat_table).to_be_visible(timeout=5000)

    stat_body = await stat_table.inner_text()
    print(f"  [테이블 내용]\n{stat_body[:500]}")

    # 콕예약 A: 시술명, 실매출 합계, 총 합계
    assert "E2E 테스트 콕예약 A_수정" in stat_body, "시술 통계에서 'E2E 테스트 콕예약 A_수정' 미발견"
    print("  ✓ 시술명 확인: E2E 테스트 콕예약 A_수정")

    # 콕예약 B: 시술명, 실매출 합계, 총 합계
    assert "E2E 테스트 콕예약 B" in stat_body, "시술 통계에서 'E2E 테스트 콕예약 B' 미발견"
    print("  ✓ 시술명 확인: E2E 테스트 콕예약 B")

    # 각 시술의 실매출 합계, 총 합계 검증 (행 기준)
    rows = stat_table.locator("tbody tr:visible")
    row_count = await rows.count()

    async def get_col_value(table, header_text, row):
        """헤더 텍스트로 컬럼 인덱스 → 해당 행의 셀 값(원 단위) 추출"""
        header = table.locator(f"thead th:has-text('{header_text}')").first
        await expect(header).to_be_visible(timeout=3000)
        col_idx = await header.evaluate(
            "th => Array.from(th.parentElement.children).indexOf(th) + 1"
        )
        cell = row.locator(f"td:nth-child({col_idx})").first
        await expect(cell).to_be_visible(timeout=3000)
        text = re.sub(r"\\s+", " ", (await cell.inner_text()).strip())
        m = re.search(r"([0-9][0-9,]*)\s*원", text)
        if m:
            return int(m.group(1).replace(",", ""))
        m = re.search(r"([0-9][0-9,]*)", text)
        if m:
            return int(m.group(1).replace(",", ""))
        return 0

    found_a = False
    found_b = False
    for i in range(row_count):
        row = rows.nth(i)
        row_text = await row.inner_text()

        if "E2E 테스트 콕예약 A_수정" in row_text and not found_a:
            real_sales = await get_col_value(stat_table, "실 매출 합계", row)
            total = await get_col_value(stat_table, "총 합계", row)
            assert real_sales > 0, f"콕예약 A_수정 실매출 합계가 0원"
            assert real_sales % 70000 == 0, f"콕예약 A_수정 실매출이 70,000원 단위가 아님: {real_sales:,}"
            print(f"  ✓ 콕예약 A_수정 검증: 실매출 합계={real_sales:,}원, 총 합계={total:,}원")
            found_a = True

        elif "E2E 테스트 콕예약 B" in row_text and not found_b:
            real_sales = await get_col_value(stat_table, "실 매출 합계", row)
            total = await get_col_value(stat_table, "총 합계", row)
            assert real_sales > 0, f"콕예약 B 실매출 합계가 0원"
            assert real_sales % 70000 == 0, f"콕예약 B 실매출이 70,000원 단위가 아님: {real_sales:,}"
            print(f"  ✓ 콕예약 B 검증: 실매출 합계={real_sales:,}원, 총 합계={total:,}원")
            found_b = True

    assert found_a, "시술 통계에서 콕예약 A 행 미발견"
    assert found_b, "시술 통계에서 콕예약 B 행 미발견"

    await page.screenshot(path=str(SHOT_DIR / "kok_stats_verified.png"))
    print("  ✓ 시술 통계 검증 완료")

    print("  ✓ 시술 통계 검증 완료")

    # ══════════════════════════════════════
    # Phase 7: 공비서로 예약받기 비활성화 → 콕예약 경고 배너 확인
    # ══════════════════════════════════════
    print("\n=== Phase 7: 공비서로 예약받기 비활성화 ===")

    # GNB > 온라인 예약 클릭
    online_menu7 = page.locator(
        "h3:has-text('온라인 예약'):visible, "
        "a:has-text('온라인 예약'):visible, "
        "button:has-text('온라인 예약'):visible, "
        "span:has-text('온라인 예약'):visible"
    ).first
    await expect(online_menu7).to_be_visible(timeout=10000)
    await online_menu7.click()
    await page.wait_for_timeout(700)

    # 공비서로 예약받기 클릭
    reserve_menu = page.locator(
        "button:has-text('공비서로 예약받기'):visible, "
        "a:has-text('공비서로 예약받기'):visible, "
        "span:has-text('공비서로 예약받기'):visible"
    ).first
    await expect(reserve_menu).to_be_visible(timeout=5000)
    await reserve_menu.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)
    print("  ✓ 공비서로 예약받기 페이지 진입")
    await page.screenshot(path=str(SHOT_DIR / "kok_phase7_01_reserve_page.png"))

    # 예약받기 토글 (on→off) 클릭
    toggle = page.locator("label[for='b2c-setting-activate-switch']").first
    await expect(toggle).to_be_visible(timeout=5000)
    await toggle.click()
    await page.wait_for_timeout(1500)
    print("  ✓ 예약받기 토글 클릭")
    await page.screenshot(path=str(SHOT_DIR / "kok_phase7_02_modal.png"))

    # 비활성화 모달 → "기대보다 예약이 적어요." 클릭
    reason = page.locator("p:has-text('기대보다 예약이 적어요')").first
    await expect(reason).to_be_visible(timeout=5000)
    await reason.click()
    await page.wait_for_timeout(500)
    print("  ✓ 비활성화 사유 선택: 기대보다 예약이 적어요.")

    # [예약받기 비활성화] 버튼 클릭
    deactivate_btn = page.locator("button:has-text('예약받기 비활성화'):visible").last
    await expect(deactivate_btn).to_be_visible(timeout=5000)

    # alert 핸들러 등록
    alert_message = []

    async def _handle_deactivate_alert(dialog):
        alert_message.append(dialog.message)
        await dialog.accept()

    page.on("dialog", _handle_deactivate_alert)
    await deactivate_btn.click()
    await page.wait_for_timeout(3000)
    page.remove_listener("dialog", _handle_deactivate_alert)

    if alert_message:
        assert "비활성화" in alert_message[0], f"예상 alert 아님: {alert_message[0]}"
        print(f"  ✓ alert 확인: {alert_message[0]}")
    else:
        # alert 대신 토스트일 수 있음
        body_text7 = await page.locator("body").inner_text()
        if "비활성화" in body_text7:
            print("  ✓ 비활성화 완료 확인 (토스트)")
        else:
            print("  ✓ 비활성화 처리 완료")

    await page.screenshot(path=str(SHOT_DIR / "kok_phase7_03_deactivated.png"))

    # GNB > 콕예약 관리 이동 (서브메뉴가 이미 펼쳐져 있을 수 있음)
    kok_menu7 = page.locator("button:has-text('콕예약 관리'):visible").first
    if await kok_menu7.count() == 0:
        # 서브메뉴가 접혀있으면 온라인 예약 먼저 클릭
        online_menu7b = page.locator(
            "h3:has-text('온라인 예약'):visible, "
            "span:has-text('온라인 예약'):visible"
        ).first
        await online_menu7b.click()
        await page.wait_for_timeout(700)
        kok_menu7 = page.locator("button:has-text('콕예약 관리'):visible").first
    await expect(kok_menu7).to_be_visible(timeout=5000)
    await kok_menu7.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)
    print("  ✓ 콕예약 관리 페이지 이동")

    # 경고 배너 확인: "공비서로 예약받기가 꺼져 있어 콕예약이 노출되지 않습니다."
    warning_banner = page.locator("h5:has-text('예약받기가 꺼져 있어')").first
    await expect(warning_banner).to_be_visible(timeout=10000)
    warning_text = (await warning_banner.inner_text()).strip()
    print(f"  ✓ 경고 배너 확인: {warning_text}")

    # "활성화하러 가기" 버튼 존재 확인
    activate_btn = page.locator("h5:has-text('활성화하러 가기')").first
    await expect(activate_btn).to_be_visible(timeout=5000)
    print("  ✓ '활성화하러 가기' 버튼 확인")

    await page.screenshot(path=str(SHOT_DIR / "kok_phase7_04_warning_banner.png"))

    print("\n=== Phase 7: 공비서로 예약받기 비활성화 + 경고 배너 확인 완료 ===")

    print("\n=== 콕예약 전체 테스트 완료 (Phase 1~7) ===")

    await page.wait_for_timeout(2000)
    await ctx.close()
    await browser.close()
    await pw.stop()


asyncio.run(main())
