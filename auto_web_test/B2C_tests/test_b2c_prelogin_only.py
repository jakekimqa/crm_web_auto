"""B2C 로그인 전 기능 테스트 (좋아요 → 앱 다운로드 모달 검증) - 단독 실행용"""
import asyncio, os, re
from playwright.async_api import async_playwright, expect

ZERO_BASE_URL = os.getenv("ZERO_BASE_URL", "https://qa-zero.gongbiz.kr")


async def main():
    headless = os.getenv("B2B_HEADLESS", "1") == "1"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(viewport={"width": 430, "height": 932})
        page = await context.new_page()

        # 1) 메인 진입
        await page.goto(f"{ZERO_BASE_URL}/main", wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(1000)
        print("✓ 메인 페이지 진입")

        # 2) 매거진 첫 번째 아이템 클릭
        magazine_item = page.locator('a[href^="/magazine/"]').first
        await expect(magazine_item).to_be_visible(timeout=10000)
        await magazine_item.click()
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(1000)
        print("✓ 매거진 상세 진입")
        await page.screenshot(path="/tmp/b2c_prelogin_01_magazine_detail.png")

        # 3) 하단 스크롤 → 좋아요(하트) 버튼 클릭
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1000)

        like_btn = page.locator('button[class*="rounded-[70px]"]').first
        await expect(like_btn).to_be_visible(timeout=5000)
        await like_btn.click()
        await page.wait_for_timeout(1000)
        print("✓ 매거진 좋아요 클릭")

        # 4) 앱 다운로드 모달 확인
        app_modal = page.locator('div[role="dialog"]')
        await expect(app_modal).to_be_visible(timeout=5000)
        app_download_btn = app_modal.locator('button[data-track-id="web_app_download_click"]')
        await expect(app_download_btn).to_be_visible(timeout=3000)
        modal_text = await app_download_btn.text_content()
        assert "공비서 앱으로 예약하기" in modal_text, f"앱 다운로드 버튼 텍스트 불일치: {modal_text}"
        print(f"✓ 앱 다운로드 모달 확인: {modal_text.strip()}")
        await page.screenshot(path="/tmp/b2c_prelogin_03_modal.png")

        # 5) 모달 닫기
        close_btn = page.locator('button[aria-label="배너 닫기"]')
        await expect(close_btn).to_be_visible(timeout=3000)
        await close_btn.click()
        await page.wait_for_timeout(500)
        print("✓ 모달 닫기")

        # 6) 메인으로 돌아가기
        await page.go_back()
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(1000)

        # 7) 콕예약 탭 클릭
        cok_tab = page.locator('a[href="/cok"]')
        await expect(cok_tab).to_be_visible(timeout=5000)
        await cok_tab.click()
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(1000)
        print("✓ 콕예약 탭 진입")

        # 8) 콕예약 첫 번째 아이템 클릭
        cok_item = page.locator('a[id^="cok-list-"]').first
        await expect(cok_item).to_be_visible(timeout=10000)
        await cok_item.click()
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(1000)
        print("✓ 콕예약 상세 진입")

        # 9) 콕예약 좋아요 버튼 클릭
        like_btn2 = page.locator('button[class*="rounded-[70px]"]').first
        await expect(like_btn2).to_be_visible(timeout=5000)
        await like_btn2.click()
        await page.wait_for_timeout(1000)
        print("✓ 콕예약 좋아요 클릭")

        # 10) 앱 다운로드 모달 확인
        app_modal2 = page.locator('div[role="dialog"]')
        await expect(app_modal2).to_be_visible(timeout=5000)
        app_download_btn2 = app_modal2.locator('button[data-track-id="web_app_download_click"]')
        await expect(app_download_btn2).to_be_visible(timeout=3000)
        print("✓ 콕예약 앱 다운로드 모달 확인")
        await page.screenshot(path="/tmp/b2c_prelogin_04_cok_modal.png")

        # 11) 모달 닫기 → 마이 탭
        close_btn2 = page.locator('button[aria-label="배너 닫기"]')
        await expect(close_btn2).to_be_visible(timeout=3000)
        await close_btn2.click()
        await page.wait_for_timeout(500)

        await page.go_back()
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(500)

        # 11-1) 예약내역 탭 클릭
        booking_tab = page.locator('a[href="/bookings"]')
        await expect(booking_tab).to_be_visible(timeout=5000)
        await booking_tab.click()
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(1000)

        app_btn = page.locator('button[data-track-id="web_app_download_click"]', has_text="공비서 앱에서 확인하기")
        await expect(app_btn).to_be_visible(timeout=5000)
        print("✓ 예약내역 → '공비서 앱에서 확인하기' 버튼 확인")

        my_tab = page.locator('a[href="/my"]')
        await expect(my_tab).to_be_visible(timeout=5000)
        await my_tab.click()
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(1000)
        print("✓ 마이 탭 진입")
        await page.screenshot(path="/tmp/b2c_prelogin_05_my.png")

        # 12) 로그인/회원가입 버튼 확인
        login_link = page.locator('a[href*="/login"]', has_text="로그인 / 회원가입")
        await expect(login_link).to_be_visible(timeout=5000)
        print("✓ 로그인/회원가입 버튼 확인")

        print("\n=== 로그인 전 기능 테스트 완료 ===")
        await page.wait_for_timeout(2000)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
