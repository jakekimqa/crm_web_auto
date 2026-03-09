import os
import re
from datetime import datetime

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright, expect


class B2BAutomationV2:
    def __init__(self):
        self.base_url = os.getenv("B2B_BASE_URL", "https://crm-dev4.gongbiz.kr/signin")
        self.correct_id = os.getenv("B2B_ID", "autoqatest1")
        self.correct_password = os.getenv("B2B_PASSWORD", "gong2023@@")
        self.wrong_password = os.getenv("B2B_WRONG_PASSWORD", "gong2022@@")
        self.shop_name = os.getenv("B2B_SHOP_NAME", "자동화_헤렌네일")
        self.owner_name = os.getenv("B2B_OWNER_NAME", "샵주테스트")
        self.headless = os.getenv("B2B_HEADLESS", "0") == "1"
        self.mmdd = datetime.now().strftime("%m%d")

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
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def login(self):
        print("=== [v2] 로그인 테스트 시작 ===")
        await self.page.goto(self.base_url)

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
        await self.page.wait_for_load_state("networkidle")

        print("4. 샵 정보 검증")
        assert await self.page.locator(f"text={self.shop_name}").first.is_visible(), "샵 이름이 올바르지 않습니다."
        assert await self.page.locator(f"text={self.owner_name}").first.is_visible(), "점주 이름이 올바르지 않습니다."
        print("=== [v2] 로그인 테스트 완료 ===\n")

    async def _open_customer_chart(self):
        # 고객차트 화면 여부 판단: URL + 검색 입력이 모두 맞을 때만 이미 진입으로 간주
        search_box = self.page.locator("input#customer-search:visible").first
        if "/customer" in self.page.url and await search_box.count() > 0 and await search_box.is_visible():
            return

        await self.page.locator("h3:has-text('고객')").first.click()
        chart_button = self.page.get_by_role("button", name="고객차트").first
        if await chart_button.count() == 0:
            chart_button = self.page.get_by_text("고객차트", exact=False).first
        await expect(chart_button).to_be_visible(timeout=5000)
        await chart_button.click()
        await self.page.wait_for_load_state("networkidle")
        await expect(self.page.locator("input#customer-search:visible").first).to_be_visible(timeout=5000)

    async def _open_new_customer_modal(self):
        for _ in range(5):
            dimmer = self.page.locator("#modal-dimmer.isActiveDimmed").first
            if await dimmer.count() > 0 and await dimmer.is_visible():
                await self.page.keyboard.press("Escape")
                await self.page.wait_for_timeout(250)

            open_btn = self.page.locator("button:has-text('신규 고객 등록'):visible").first
            try:
                await open_btn.click(force=True, timeout=3000)
                await self.page.wait_for_selector("#customer-name:visible", timeout=5000)
                return
            except PlaywrightTimeoutError:
                await self.page.wait_for_timeout(250)
            except Exception:
                await self.page.wait_for_timeout(250)
        raise AssertionError("신규 고객 등록 모달 열기 실패")

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

    async def _ensure_active_page(self):
        if self.page is not None and not self.page.is_closed():
            return
        if self.context and self.context.pages:
            for p in reversed(self.context.pages):
                if not p.is_closed():
                    self.page = p
                    break
        assert self.page is not None and not self.page.is_closed(), "활성 페이지를 찾지 못했습니다."

    async def _assert_customer_exists_in_list(self, customer_name):
        list_item = self.page.locator(f"tr:has-text('{customer_name}'), li:has-text('{customer_name}')").first
        await expect(list_item).to_be_visible(timeout=5000)

    async def _customer_exists_in_list(self, customer_name):
        list_item = self.page.locator(f"tr:has-text('{customer_name}'), li:has-text('{customer_name}')").first
        return await list_item.count() > 0 and await list_item.is_visible()

    @staticmethod
    def _extract_amount(text, label):
        m = re.search(rf"{label}\s*([0-9,]+)\s*원", text)
        return int(m.group(1).replace(",", "")) if m else None

    async def _close_duplicate_modal(self):
        # 1) 중복 알림 모달에서 [취소]
        cancel_button = self.page.locator(
            "#modal-content:visible button:has-text('취소'):visible, [role='dialog']:visible button:has-text('취소'):visible"
        ).first
        if await cancel_button.count() > 0:
            await cancel_button.click()
        else:
            fallback_cancel = self.page.locator("button:has-text('취소'):visible").first
            if await fallback_cancel.count() > 0:
                await fallback_cancel.click()
            else:
                await self.page.keyboard.press("Escape")

        # 2) 우측 신규 고객 등록 SIDE 모달 닫기 (X 아이콘 우선)
        for _ in range(6):
            if await self.page.locator("#customer-name:visible").count() == 0:
                break
            side_x = self.page.locator(
                "#modal-content[type='SIDE'] header svg[icon='systemX']:visible, "
                "#modal-content[type='SIDE'] header .sc-63ba4f11-1:visible"
            ).first
            if await side_x.count() > 0:
                await side_x.click(force=True)
            else:
                await self.page.keyboard.press("Escape")
            await self.page.wait_for_timeout(250)

        assert await self.page.locator("#customer-name:visible").count() == 0, "신규고객등록(우측) 창 닫기 실패"

    async def _assert_duplicate_modal(self):
        duplicate_text = self.page.get_by_text(re.compile(r"이미 등록된.*(연락처|고객)|해당 고객차트"))
        await expect(duplicate_text).to_be_visible(timeout=5000)
        print("message: 중복 고객/연락처 알림 확인")
        await self._close_duplicate_modal()

    async def _assert_duplicate_contact_modal_exact(self):
        exact_text = self.page.get_by_text(re.compile(r"이미\s*등록된\s*고객\s*연락처입니다\.?"))
        await expect(exact_text).to_be_visible(timeout=5000)
        print("message: 이미 등록된 고객 연락처입니다.")
        await self._close_duplicate_modal()

    async def add_customers(self, verify_duplicates=True):
        print("=== [v2] 고객 추가 테스트 시작 ===")
        await self._open_customer_chart()

        customers = [
            (f"자동화_{self.mmdd}_1", f"010{self.mmdd}0001"),
            (f"자동화_{self.mmdd}_2", f"010{self.mmdd}0002"),
            (f"자동화_{self.mmdd}_3", f"010{self.mmdd}0003"),
        ]

        for idx, (name, phone) in enumerate(customers, 1):
            print(f"{idx}. 고객 추가: {name}, {phone}")
            await self._ensure_active_page()

            # 맨 먼저 리스트에 이미 있으면 신규 등록 자체를 스킵
            if await self._customer_exists_in_list(name):
                print(f"✓ {name} 이미 존재 - 고객 추가 스킵")
                continue

            await self._open_new_customer_modal()
            await self.page.fill("#customer-name", name)
            await self.page.fill("#customer-contact", phone)
            await self.page.locator("button:has-text('고객 등록'):visible").last.click()
            await self._ensure_active_page()
            await self.page.wait_for_timeout(1500)

            # 룰: 자동화_{mmdd}_1 등록 시 중복 연락처 문구가 뜨면 실패하지 않고 다음 단계로 진행
            duplicate_text = self.page.get_by_text(re.compile(r"이미\s*등록된\s*고객\s*연락처입니다\.?")).first
            if idx == 1 and await duplicate_text.count() > 0 and await duplicate_text.is_visible():
                print(f"✓ {name} 중복 감지 - 고객추가 스킵하고 다음 단계 진행")
                await self._close_duplicate_modal()
                continue

            await self._assert_customer_exists_in_list(name)
            print(f"✓ {name} 등록 완료")

        if not verify_duplicates:
            print("=== [v2] 고객 추가 테스트 완료(중복 검증 스킵) ===\n")
            return

        print("4. 중복 연락처(동일 이름+동일 연락처) 테스트")
        await self._open_new_customer_modal()
        await self.page.fill("#customer-name", customers[0][0])
        await self.page.fill("#customer-contact", customers[0][1])
        await self.page.locator("button:has-text('고객 등록'):visible").last.click()
        await self._assert_duplicate_contact_modal_exact()
        print("=== [v2] 고객 추가 테스트 완료 ===\n")

    async def open_customer_detail_from_list(self, customer_name):
        await self._open_customer_chart()
        await self._dismiss_active_dimmer()

        list_item = self.page.locator(f"tr:has-text('{customer_name}'), li:has-text('{customer_name}')").first
        await expect(list_item).to_be_visible(timeout=5000)
        async with self.context.expect_page(timeout=10000) as new_page_info:
            await list_item.click(force=True)
        detail_page = await new_page_info.value
        await detail_page.wait_for_load_state("domcontentloaded")

        await detail_page.bring_to_front()
        return detail_page

    async def assert_customer_name_visible_top_left(self, detail_page, customer_name):
        # 상단 영역 내 고객명 노출 검증 (좌측 상단 헤더/프로필 텍스트)
        top_name = detail_page.locator(
            "header :text-is('{name}'), "
            "div:has(> h1:text-is('{name}')), "
            "div:has(> h2:text-is('{name}')), "
            "h1:text-is('{name}'), h2:text-is('{name}'), h3:text-is('{name}')"
            .replace("{name}", customer_name)
        ).first

        if await top_name.count() == 0:
            top_name = detail_page.get_by_text(customer_name, exact=True).first

        await expect(top_name).to_be_visible(timeout=5000)
        print(f"✓ 고객상세 좌측 상단 이름 노출 확인: {customer_name}")

    async def membership_charge_and_verify(self, customer_name=None):
        if customer_name is None:
            customer_name = f"자동화_{self.mmdd}_1"

        detail_page = await self.open_customer_detail_from_list(customer_name)
        await self.assert_customer_name_visible_top_left(detail_page, customer_name)
        before_text = re.sub(r"\s+", " ", await detail_page.locator("body").inner_text())
        before_sales = self._extract_amount(before_text, "실 매출")
        before_membership = self._extract_amount(before_text, "정액권")
        assert before_sales is not None and before_membership is not None, "충전 전 금액 파싱 실패"

        # 정액권 옆 [충전] 버튼 클릭
        membership_row = detail_page.locator("dl, li, div, section, article").filter(
            has_text=re.compile(r"정액권|회원권")
        ).filter(
            has=detail_page.get_by_role("button", name="충전")
        ).first
        await expect(membership_row).to_be_visible(timeout=5000)
        charge_btn = membership_row.get_by_role("button", name="충전").first
        await expect(charge_btn).to_be_visible(timeout=5000)
        await charge_btn.click()

        # 회원권 충전 모달 확인
        modal = detail_page.locator("#modal-content:visible, [role='dialog']:visible, [aria-modal='true']:visible").first
        await expect(modal).to_be_visible(timeout=5000)
        await expect(modal.get_by_text(re.compile(r"회원권\s*충전|정액권\s*충전")).first).to_be_visible(timeout=5000)

        # 정액권 선택 드롭다운 (기본: 100만원(카드)) 열기
        dropdown = modal.locator(
            "button.select-display:visible, [data-testid='select-toggle-button']:visible, button:has-text('100'):visible"
        ).first
        await expect(dropdown).to_be_visible(timeout=5000)
        await dropdown.click()

        # 20만원(현금) 선택
        option_200k_cash = detail_page.get_by_role("button", name=re.compile(r"20\s*만원.*현금")).locator(":visible").first
        await expect(option_200k_cash).to_be_visible(timeout=5000)
        await option_200k_cash.click()
        print("✓ 회원권 옵션 선택: 20만원(현금)")

        # 모달 [충전] 클릭
        submit_btn = None
        for label in ["충전", "충전하기", "등록", "저장", "확인"]:
            candidate = modal.get_by_role("button", name=re.compile(rf"^\s*{re.escape(label)}\s*$")).locator(":visible").first
            if await candidate.count() > 0:
                submit_btn = candidate
                break
        if submit_btn is None:
            submit_btn = modal.locator(
                "button:has-text('충전'):visible, button:has-text('충전하기'):visible, button:has-text('등록'):visible, button:has-text('저장'):visible, button:has-text('확인'):visible"
            ).first
            if await submit_btn.count() == 0:
                submit_btn = None
        assert submit_btn is not None, "회원권 충전 모달 제출 버튼을 찾지 못했습니다."
        await submit_btn.click()

        # 적용 반영 대기
        await detail_page.wait_for_timeout(1500)
        try:
            await detail_page.wait_for_selector("#modal-dimmer.isActiveDimmed", state="hidden", timeout=5000)
        except Exception:
            pass

        # 좌측 수치 검증: 실매출 200,000원 / 정액권 220,000원
        page_text = await detail_page.locator("body").inner_text()
        compact = re.sub(r"\s+", " ", page_text)
        after_sales = self._extract_amount(compact, "실 매출")
        after_membership = self._extract_amount(compact, "정액권")
        assert after_sales is not None and after_membership is not None, "충전 후 금액 파싱 실패"
        assert after_sales >= before_sales + 200000, f"실매출 증가 검증 실패: before={before_sales}, after={after_sales}"
        assert after_membership >= before_membership + 220000, (
            f"정액권 증가 검증 실패: before={before_membership}, after={after_membership}"
        )
        print(f"✓ 좌측 금액 검증 완료: 실매출 {before_sales}->{after_sales}, 정액권 {before_membership}->{after_membership}")
        if detail_page is not self.page and not detail_page.is_closed():
            await detail_page.close()
            await self.focus_main_page()

    async def ticket_charge_and_verify(self, customer_name=None):
        if customer_name is None:
            customer_name = f"자동화_{self.mmdd}_2"

        detail_page = await self.open_customer_detail_from_list(customer_name)
        await self.assert_customer_name_visible_top_left(detail_page, customer_name)

        before_text = re.sub(r"\s+", " ", await detail_page.locator("body").inner_text())
        before_match = re.search(r"티켓\s*(\d+)\s*회", before_text)
        before_count = int(before_match.group(1)) if before_match else 0

        ticket_row = detail_page.locator("dl, li, div, section, article").filter(
            has_text=re.compile(r"티켓")
        ).filter(
            has=detail_page.get_by_role("button", name="충전")
        ).first
        await expect(ticket_row).to_be_visible(timeout=5000)
        await ticket_row.get_by_role("button", name="충전").first.click()

        modal = detail_page.locator("#modal-content:visible, [role='dialog']:visible, [aria-modal='true']:visible").first
        await expect(modal).to_be_visible(timeout=5000)
        ticket_tab = modal.locator("h3:has-text('티켓 충전'):visible").first
        if await ticket_tab.count() == 0:
            ticket_tab = modal.get_by_text("티켓 충전", exact=True).first
        await expect(ticket_tab).to_be_visible(timeout=5000)
        await ticket_tab.click()
        await detail_page.wait_for_timeout(300)

        modal_text = re.sub(r"\s+", " ", await modal.inner_text())
        if not re.search(r"10\s*만원권.*카드", modal_text):
            dropdown = modal.locator(
                "button.select-display:visible, [data-testid='select-toggle-button']:visible, button:has-text('만원권'):visible"
            ).first
            if await dropdown.count() > 0:
                await dropdown.click()
                option = detail_page.get_by_role("button", name=re.compile(r"10\s*만원권.*카드")).locator(":visible").first
                if await option.count() > 0:
                    await option.click()

        submit_btn = modal.locator("button:has-text('충전'):visible, button:has-text('등록'):visible").first
        await expect(submit_btn).to_be_visible(timeout=5000)
        await submit_btn.click()
        await detail_page.wait_for_timeout(1500)

        after_text = re.sub(r"\s+", " ", await detail_page.locator("body").inner_text())
        after_match = re.search(r"티켓\s*(\d+)\s*회", after_text)
        assert after_match is not None, "티켓 충전 후 수량 파싱 실패"
        after_count = int(after_match.group(1))
        assert after_count > before_count, f"티켓 수량 증가 실패: before={before_count}, after={after_count}"
        assert "티켓충전" in after_text, "티켓 충전 이력 확인 실패"

        if detail_page is not self.page and not detail_page.is_closed():
            await detail_page.close()
            await self.focus_main_page()

    async def ensure_calendar_page(self):
        await self.focus_main_page()
        if "/book/calendar" in self.page.url:
            return
        shop_link = self.page.locator("a.shop-name-link:visible, a[href='/book/calendar']:visible").first
        if await shop_link.count() > 0:
            await shop_link.click()
            await self.page.wait_for_load_state("domcontentloaded")
            await self.page.wait_for_timeout(500)
            if "/book/calendar" in self.page.url:
                return
        home_menu = self.page.get_by_text("홈", exact=True).first
        await expect(home_menu).to_be_visible(timeout=5000)
        await home_menu.click()
        calendar_menu = self.page.get_by_text("예약 캘린더", exact=True).first
        await expect(calendar_menu).to_be_visible(timeout=5000)
        await calendar_menu.click()
        await self.page.wait_for_load_state("domcontentloaded")
        await self.page.wait_for_timeout(700)

    def _reservation_scenarios(self):
        return [
            {"customer": f"자동화_{self.mmdd}_1", "time": "오후 4:00", "display_time": "오후 4:00", "menu_category": "손", "menu_item": "젤 기본"},
            {"customer": f"자동화_{self.mmdd}_2", "time": "오후 5:00", "display_time": "오후 5:00", "menu_category": "티켓", "menu_item": "10만원권"},
            {"customer": f"자동화_{self.mmdd}_3", "time": "오후 6:00", "display_time": "오후 6:00", "menu_category": "손", "menu_item": "케어"},
        ]

    async def make_reservations(self):
        await self.ensure_calendar_page()
        reservations = self._reservation_scenarios()

        async def open_reservation_form():
            for _ in range(5):
                modal = self.page.locator("#modal-content:visible, [role='dialog']:visible").first
                if await modal.count() > 0:
                    return modal
                await self._dismiss_active_dimmer()
                await self.page.locator("#floating-layout button:visible").first.click(force=True)
                await self.page.wait_for_timeout(250)
                for cand in [
                    self.page.get_by_role("menuitem", name="예약 등록").locator(":visible").first,
                    self.page.get_by_role("button", name="예약 등록").locator(":visible").first,
                    self.page.locator("h4:has-text('예약 등록'):visible").first,
                ]:
                    if await cand.count() == 0:
                        continue
                    try:
                        await cand.click(force=True, timeout=4000)
                        await self.page.wait_for_selector("#modal-content:visible, [role='dialog']:visible", timeout=5000)
                        return self.page.locator("#modal-content:visible, [role='dialog']:visible").first
                    except Exception:
                        continue
                await self.page.keyboard.press("Escape")
            raise AssertionError("예약 등록 모달 진입 실패")

        for reservation in reservations:
            dialog = None
            for _ in range(3):
                dialog = await open_reservation_form()
                customer_search = dialog.locator("input#customer-search:visible").first
                await expect(customer_search).to_be_visible(timeout=5000)
                await customer_search.fill(reservation["customer"])
                await customer_search.press("Enter")
                await self.page.wait_for_timeout(1000)

                selected = False
                for c in [
                    dialog.locator(f"li:has-text('{reservation['customer']}'):visible").first,
                    dialog.locator(f"button:has-text('{reservation['customer']}'):visible").first,
                    dialog.locator(f"div:has-text('{reservation['customer']}'):visible").first,
                ]:
                    if await c.count() == 0:
                        continue
                    try:
                        await c.click(timeout=3000)
                        selected = True
                        break
                    except Exception:
                        continue
                if not selected:
                    try:
                        await customer_search.press("ArrowDown")
                        await customer_search.press("Enter")
                        selected = True
                    except Exception:
                        selected = False

                await self.page.wait_for_timeout(400)
                if selected and await dialog.locator("#createBookingTime:visible").count() > 0:
                    break
                await self.page.keyboard.press("Escape")
                await self.page.wait_for_timeout(250)
            else:
                raise AssertionError(f"예약 모달에서 고객 선택/시간 필드 로드 실패: {reservation['customer']}")

            time_dropdown = dialog.locator(
                "#createBookingTime:visible, button.select-display:has-text('오전'):visible, button.select-display:has-text('오후'):visible"
            ).first
            await expect(time_dropdown).to_be_visible(timeout=5000)
            await time_dropdown.click(force=True)
            await self.page.locator(f"button:has-text('{reservation['time']}'):visible").first.click(force=True)

            await self.page.locator("#bookingItemGroupSelect button.select-display:visible").first.click()
            await self.page.locator(f"button:has-text('{reservation['menu_category']}'):visible").first.click()
            await self.page.wait_for_timeout(300)
            await self.page.locator(f"button:has-text('{reservation['menu_item']}'):visible").first.click()
            await self.page.wait_for_timeout(300)

            await self.page.locator("button:has-text('등록'):visible").first.click()
            await self.page.wait_for_load_state("networkidle")
            try:
                await self.page.wait_for_selector("#modal-dimmer.isActiveDimmed", state="hidden", timeout=5000)
            except Exception:
                await self.page.keyboard.press("Escape")

    async def verify_calendar_reservations(self):
        await self.ensure_calendar_page()
        expected = self._reservation_scenarios()
        await self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()
        # 일 단위에서 우측(chevron-right)으로 다음 날(3/10) 이동
        next_icon = self.page.locator("span.fc-icon.fc-icon-chevron-right:visible").first
        await expect(next_icon).to_be_visible(timeout=5000)
        await next_icon.evaluate("(el) => el.closest('button')?.click()")
        await self.page.wait_for_timeout(500)

        for r in expected:
            reserve_card = self.page.locator("div.BOOKING.booking-normal").filter(has_text=r["customer"]).first
            if await reserve_card.count() == 0:
                reserve_card = self.page.locator(
                    "div, li, article"
                ).filter(
                    has_text=re.compile(rf"{re.escape(r['display_time'])}.*{re.escape(r['customer'])}|{re.escape(r['customer'])}.*{re.escape(r['display_time'])}")
                ).first
            if await reserve_card.count() == 0:
                reserve_card = self.page.get_by_text(r["customer"], exact=True).first
            await expect(reserve_card).to_be_visible(timeout=5000)
            await reserve_card.click(force=True)
            await self.page.wait_for_timeout(300)
            detail_panel = self.page.locator("div:has(button:has-text('나가기'))").filter(has_text=r["customer"]).first
            if await detail_panel.count() == 0:
                detail_panel = self.page.locator("div").filter(has_text=r["customer"]).filter(has_text=r["display_time"]).first
            text = await detail_panel.inner_text()
            assert r["customer"] in text, f"고객명 검증 실패: {r['customer']}"
            assert r["display_time"] in text, f"예약시간 검증 실패: {r['display_time']}"
            # 반드시 상세 패널을 닫고(뒤로가기/나가기) 다음 고객 검증으로 진행
            closed = False
            for _ in range(5):
                exit_btn = self.page.locator(
                    "button.sc-45a967ab-0:has-text('나가기'):visible, button:has-text('나가기'):visible"
                ).first
                if await exit_btn.count() > 0:
                    await exit_btn.click(force=True)
                else:
                    await self.page.keyboard.press("Escape")
                await self.page.wait_for_timeout(300)
                still_open = self.page.locator("div:has(button:has-text('나가기'))").filter(has_text=r["customer"]).first
                if await still_open.count() == 0 or not await still_open.is_visible():
                    closed = True
                    break
            assert closed, f"상세 패널 닫기 실패: {r['customer']}"


@pytest.mark.asyncio
async def test_login_and_add_customers_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.add_customers()
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_customer_detail_name_from_list_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.add_customers(verify_duplicates=True)
        target_name = f"자동화_{runner.mmdd}_1"
        detail_page = await runner.open_customer_detail_from_list(target_name)
        await runner.assert_customer_name_visible_top_left(detail_page, target_name)
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_membership_charge_from_customer_detail_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        target_name = f"자동화_{runner.mmdd}_1"
        await runner.membership_charge_and_verify(target_name)
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_ticket_charge_from_customer_detail_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        target_name = f"자동화_{runner.mmdd}_2"
        await runner.ticket_charge_and_verify(target_name)
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_make_reservations_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.make_reservations()
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_verify_calendar_reservations_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.verify_calendar_reservations()
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_full_e2e_from_start_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.add_customers(verify_duplicates=True)
        await runner.membership_charge_and_verify(f"자동화_{runner.mmdd}_1")
        await runner.ticket_charge_and_verify(f"자동화_{runner.mmdd}_2")
        await runner.make_reservations()
        await runner.verify_calendar_reservations()
    finally:
        await runner.teardown()
