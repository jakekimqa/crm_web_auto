"""공통 유틸: 브라우저 셋업, 로그인, 팝업 처리, 페이지 관리"""

import os
import re
from datetime import datetime

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright, expect


class CommonMixin:
    def __init__(self):
        self.base_url = os.getenv("B2B_BASE_URL", "https://crm-dev2.gongbiz.kr/signin")
        self.correct_id = os.getenv("B2B_ID", "autoqatest1")
        self.correct_password = os.getenv("B2B_PASSWORD", "gong2023@@")
        self.wrong_password = os.getenv("B2B_WRONG_PASSWORD", "gong2022@@")
        self.shop_name = os.getenv("B2B_SHOP_NAME", "자동화_헤렌네일")
        self.owner_name = os.getenv("B2B_OWNER_NAME", "샵주테스트")
        self.headless = os.getenv("B2B_HEADLESS", "0") == "1"
        self.mmdd = datetime.now().strftime("%m%d")
        self.expected_home_sales = os.getenv("B2B_EXPECTED_HOME_SALES", "320,000원")
        self.expected_home_reservations = os.getenv("B2B_EXPECTED_HOME_RESERVATIONS", "3")
        self.skip_referrer = os.getenv("SKIP_REFERRER", "0") == "1"
        self.skip_staff_statistics = os.getenv("SKIP_STAFF_STATISTICS", "0") == "1"

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    async def setup(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            slow_mo=0 if self.headless else 1000,
        )
        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        self.page = await self.context.new_page()

    async def teardown(self):
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
            self.context = None
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None
        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

    async def login(self):
        print("=== [v2] 로그인 테스트 시작 ===")
        await self.page.goto(self.base_url, timeout=60000)

        print("1. 잘못된 비밀번호로 로그인 시도")
        await self.page.fill('input[name="id"], input[type="text"]', self.correct_id)
        await self.page.fill('input[name="password"], input[type="password"]', self.wrong_password)
        await self.page.click('button[type="submit"], .login-btn')
        await self.page.wait_for_selector("text=아이디 또는 비밀번호를 다시 확인하세요.", timeout=5000)
        print("✓ 에러 메시지 확인 완료")

        print("2. 올바른 정보로 로그인")
        await self.page.fill('input[name="id"], input[type="text"]', self.correct_id)
        await self.page.fill('input[name="password"], input[type="password"]', self.correct_password)
        await self.page.click('button[type="submit"], .login-btn')
        await self.page.wait_for_load_state("networkidle")

        print(f"3. {self.shop_name} 샵으로 이동")
        await self.page.wait_for_selector(f"text={self.shop_name}", timeout=10000)
        await self.page.click("text=샵으로 이동")
        await self.page.wait_for_load_state("networkidle", timeout=60000)

        # 공지 팝업이 있으면 닫기
        await self._dismiss_notice_popup()

        print("4. 샵 정보 검증")
        assert await self.page.locator(f"text={self.shop_name}").first.is_visible(), "샵 이름이 올바르지 않습니다."
        assert await self.page.locator(f"text={self.owner_name}").first.is_visible(), "점주 이름이 올바르지 않습니다."
        print("=== [v2] 로그인 테스트 완료 ===\n")

    async def _dismiss_notice_popup(self):
        """캘린더 진입 시 운영 공지 팝업이 있으면 '하루 동안 보지 않기' 클릭"""
        try:
            dismiss_btn = self.page.locator("text=하루 동안 보지 않기").first
            await dismiss_btn.wait_for(state="visible", timeout=3000)
            await dismiss_btn.click()
            await self.page.wait_for_timeout(500)
            print("✓ 공지 팝업 닫기 완료")
        except Exception:
            pass  # 팝업이 없으면 무시

    async def _dismiss_active_dimmer(self):
        for _ in range(5):
            dimmer = self.page.locator("#modal-dimmer.isActiveDimmed").first
            if await dimmer.count() > 0 and await dimmer.is_visible():
                await self.page.keyboard.press("Escape")
                await self.page.wait_for_timeout(250)
                continue
            break

    async def focus_main_page(self):
        if self.page is None or self.page.is_closed():
            if self.context and self.context.pages:
                for p in self.context.pages:
                    if not p.is_closed():
                        self.page = p
                        break
        assert self.page is not None and not self.page.is_closed(), "메인 페이지를 찾지 못했습니다."
        await self.page.bring_to_front()
        await self.page.wait_for_load_state("domcontentloaded")
        await self._dismiss_popup()

    async def _dismiss_popup(self):
        """팝업이 있으면 '하루 동안 보지 않기' 클릭, 또는 모달 닫기 버튼 클릭"""
        try:
            # 1) "하루 동안 보지 않기" 버튼/라벨
            dismiss_btn = self.page.locator(
                "button:has-text('하루 동안 보지 않기'):visible, "
                "label:has-text('하루 동안 보지 않기'):visible"
            ).first
            if await dismiss_btn.count() > 0 and await dismiss_btn.is_visible():
                await dismiss_btn.click()
                await self.page.wait_for_timeout(500)
                print("✓ 팝업 닫기 완료 (하루 동안 보지 않기)")
                return
            # 2) event-popup 모달의 닫기(X) 버튼
            modal = self.page.locator("div.modal-wrapper:has(div.modal-dimmer.isActiveDimmed):visible").first
            if await modal.count() > 0:
                close_btn = modal.locator("button:visible").first
                if await close_btn.count() > 0:
                    await close_btn.click()
                    await self.page.wait_for_timeout(500)
                    print("✓ 모달 팝업 닫기 완료")
        except Exception:
            pass

    async def _ensure_active_page(self):
        if self.page is not None and not self.page.is_closed():
            return
        if self.context and self.context.pages:
            for p in reversed(self.context.pages):
                if not p.is_closed():
                    self.page = p
                    break
        assert self.page is not None and not self.page.is_closed(), "활성 페이지를 찾지 못했습니다."

    @staticmethod
    def _extract_amount(text, label):
        m = re.search(rf"{label}\s*([0-9,]+)\s*원", text)
        return int(m.group(1).replace(",", "")) if m else None

    @staticmethod
    def _extract_amount_fuzzy(text, labels):
        compact = re.sub(r"\s+", " ", text)
        for label in labels:
            patterns = [
                rf"{label}\s*([0-9,]+)\s*원",
                rf"{label}[^0-9]{{0,20}}([0-9,]+)\s*원",
            ]
            for pattern in patterns:
                m = re.search(pattern, compact)
                if m:
                    return int(m.group(1).replace(",", ""))
        return None
