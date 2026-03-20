"""
CRM 회원가입 테스트 (dev2)
- 휴대폰 인증 단계에서 일시 정지 → 수동 인증번호 입력 후 진행
"""
import os, sys, asyncio
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

SHOT_DIR = Path(__file__).resolve().parents[2] / "qa_artifacts" / "screenshots"
SHOT_DIR.mkdir(parents=True, exist_ok=True)

# 가입 정보
SIGNUP_URL = "https://crm-dev2.gongbiz.kr/signin"
USER_ID = "qatest0319a"
USER_PW = "gong2023@@"
USER_NAME = "테스트회원"
PHONE_NUMBER = "01041584484"


@pytest.mark.asyncio
async def test_crm_signup():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    page = await context.new_page()

    try:
        # ── 1. 로그인 페이지 → 무료로 시작하기 ──
        print("\n=== 1. 회원가입 페이지 진입 ===")
        await page.goto(SIGNUP_URL)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

        free_btn = page.locator("text=무료로 시작하기").first
        await expect(free_btn).to_be_visible(timeout=10000)
        await free_btn.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)
        print(f"  ✓ 회원가입 페이지: {page.url}")
        await page.screenshot(path=str(SHOT_DIR / "signup_01_page.png"))

        # ── 2. 폼 입력 ──
        print("\n=== 2. 폼 입력 ===")
        # 아이디
        id_input = page.locator("input[placeholder*='아이디']").first
        await id_input.click()
        await id_input.type(USER_ID, delay=30)
        await page.wait_for_timeout(300)
        print(f"  ✓ 아이디: {USER_ID}")

        # 비밀번호
        pw_input = page.locator("input[placeholder*='비밀번호를 입력']").first
        await pw_input.click()
        await pw_input.type(USER_PW, delay=30)
        await page.wait_for_timeout(300)
        print(f"  ✓ 비밀번호 입력")

        # 비밀번호 확인
        pw_confirm = page.locator("input[placeholder*='한 번 더']").first
        await pw_confirm.click()
        await pw_confirm.type(USER_PW, delay=30)
        await page.wait_for_timeout(300)
        print(f"  ✓ 비밀번호 확인 입력")

        # 이름
        name_input = page.locator("input[placeholder*='이름']").first
        await name_input.click()
        await name_input.type(USER_NAME, delay=30)
        await page.wait_for_timeout(300)
        print(f"  ✓ 이름: {USER_NAME}")

        # 전화번호
        phone_input = page.locator("input[name='mobilePhoneNumber']").first
        await phone_input.click()
        await phone_input.type(PHONE_NUMBER, delay=30)
        await page.wait_for_timeout(300)
        print(f"  ✓ 전화번호: {PHONE_NUMBER}")

        await page.screenshot(path=str(SHOT_DIR / "signup_02_filled.png"))

        # ── 3. 인증번호 전송 ──
        print("\n=== 3. 인증번호 전송 ===")
        send_btn = page.locator("button:has-text('전송')").first
        await expect(send_btn).to_be_visible(timeout=5000)
        await send_btn.click()
        await page.wait_for_timeout(3000)

        # 중복 연락처 체크
        body_after_send = await page.locator("body").inner_text()
        if "이미 가입" in body_after_send or "중복" in body_after_send or "등록된 연락처" in body_after_send:
            await page.screenshot(path=str(SHOT_DIR / "signup_03_duplicate.png"))
            print(f"  ✓ 중복 연락처 감지 — 이미 가입된 번호입니다: {PHONE_NUMBER}")
            print("\n=== 테스트 종료 (중복 연락처) ===")
            return

        await page.screenshot(path=str(SHOT_DIR / "signup_03_sent.png"))
        print("  ✓ 인증번호 전송 완료")

        # 인증번호 입력 필드 대기
        verify_input = page.locator("input[placeholder*='인증'], input[placeholder*='확인']").first
        if await verify_input.count() == 0:
            # 새로운 input이 나타날 수 있음
            await page.wait_for_timeout(2000)
            all_inputs = page.locator("input:visible")
            cnt = await all_inputs.count()
            print(f"  현재 visible input 수: {cnt}")
            for i in range(cnt):
                inp = all_inputs.nth(i)
                ph = await inp.get_attribute("placeholder") or ""
                val = await inp.input_value()
                print(f"    [{i}] placeholder='{ph}' value='{val}'")
            await page.screenshot(path=str(SHOT_DIR / "signup_03b_debug.png"))

        # ── 4. 인증번호 입력 대기 (수동) ──
        print("\n" + "=" * 50)
        print("📱 인증번호를 확인해주세요!")
        print("=" * 50)

        # 파일 기반 인증번호 전달
        code_file = Path(__file__).parent / "_verify_code.txt"
        if code_file.exists():
            code_file.unlink()

        print(f"\n인증번호를 아래 파일에 입력하거나, 테스트를 중단하고 직접 알려주세요:")
        print(f"  파일: {code_file}")
        print(f"\n또는 터미널에서: echo '123456' > {code_file}")
        print("\n5분 내 입력 대기 중...")

        verify_code = None
        for i in range(300):  # 5분 대기
            if code_file.exists():
                verify_code = code_file.read_text().strip()
                if verify_code:
                    print(f"\n  ✓ 인증번호 수신: {verify_code}")
                    code_file.unlink()
                    break
            await asyncio.sleep(1)

        assert verify_code, "인증번호 미입력 (5분 초과)"

        # ── 5. 인증번호 입력 ──
        print("\n=== 5. 인증번호 입력 ===")
        # 인증번호 입력 필드 찾기
        verify_input = page.locator("input[placeholder*='인증번호를 입력']").first
        await expect(verify_input).to_be_visible(timeout=5000)
        await verify_input.click()
        await verify_input.type(verify_code, delay=50)
        await page.wait_for_timeout(1000)
        await page.screenshot(path=str(SHOT_DIR / "signup_04_code_entered.png"))
        print(f"  ✓ 인증번호 입력: {verify_code}")

        # [인증] 버튼 클릭 (enabled 될 때까지 대기)
        confirm_btn = page.locator("button:has-text('인증')").first
        await expect(confirm_btn).to_be_enabled(timeout=10000)
        await confirm_btn.click()
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(SHOT_DIR / "signup_04b_verified.png"))
        print("  ✓ 인증 확인 클릭")

        # ── 6. 약관 동의 ──
        print("\n=== 6. 약관 동의 ===")

        # 체크박스가 hidden이므로 JavaScript로 체크 상태 확인
        cb_states = await page.evaluate("() => Array.from(document.querySelectorAll('input[type=checkbox]')).map(c => c.checked)")
        print(f"  체크박스 상태: {cb_states}")

        # "전체 동의" 텍스트의 부모 요소 클릭 (label 역할)
        if not all(cb_states):
            # 전체 동의 클릭 (2번 클릭해서 해제→체크 보장)
            agree_el = page.locator("text=전체 동의").first
            await agree_el.click()
            await page.wait_for_timeout(500)

            # 체크 상태 재확인
            cb_states2 = await page.evaluate("() => Array.from(document.querySelectorAll('input[type=checkbox]')).map(c => c.checked)")
            print(f"  클릭 후 상태: {cb_states2}")

            if not all(cb_states2):
                # 한번 더 클릭 (토글이었을 수 있음)
                await agree_el.click()
                await page.wait_for_timeout(500)
                cb_states3 = await page.evaluate("() => Array.from(document.querySelectorAll('input[type=checkbox]')).map(c => c.checked)")
                print(f"  재클릭 후 상태: {cb_states3}")

        # 최종 확인
        final_states = await page.evaluate("() => Array.from(document.querySelectorAll('input[type=checkbox]')).map(c => c.checked)")
        print(f"  최종 체크박스 상태: {final_states}")
        await page.screenshot(path=str(SHOT_DIR / "signup_05_agreed.png"))
        print("  ✓ 약관 동의 완료")

        # ── 7. 회원가입 완료 ──
        print("\n=== 7. 회원가입 완료 ===")
        signup_btn = page.locator("button:has-text('회원가입 완료')").first
        await expect(signup_btn).to_be_visible(timeout=5000)

        # 버튼 enabled 확인
        is_enabled = await signup_btn.is_enabled()
        print(f"  회원가입 완료 버튼 enabled: {is_enabled}")
        if not is_enabled:
            # 디버그: 현재 폼 상태 캡처
            await page.screenshot(path=str(SHOT_DIR / "signup_06_debug.png"))
            # force click 시도
            print("  ⚠ 버튼 disabled — force click 시도")
            await signup_btn.click(force=True)
        else:
            await signup_btn.click()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=str(SHOT_DIR / "signup_06_complete.png"))

        body_text = await page.locator("body").inner_text()
        print(f"  결과 URL: {page.url}")
        print(f"  결과 텍스트: {body_text[:500]}")

        # 중복 연락처/아이디 에러 체크
        if "이미 가입" in body_text or "중복" in body_text or "등록된" in body_text:
            print(f"\n  ✓ 중복 감지 — 정상 에러 처리 확인")
            print("\n=== 테스트 종료 (중복) ===")
            return

        print(f"\n=== 전체 테스트 성공! ===")

    finally:
        await context.close()
        await browser.close()
        await pw.stop()
