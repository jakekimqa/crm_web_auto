import os
import re
import asyncio
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
        self.expected_home_sales = os.getenv("B2B_EXPECTED_HOME_SALES", "320,000원")
        self.expected_home_reservations = os.getenv("B2B_EXPECTED_HOME_RESERVATIONS", "3")

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
        # 등록 직후 리스트 반영 지연을 고려해 재시도한다.
        for _ in range(15):
            await self._ensure_active_page()
            list_item = self.page.locator(
                f"tr:has-text('{customer_name}'), li:has-text('{customer_name}'), div:has-text('{customer_name}')"
            ).first
            if await list_item.count() > 0 and await list_item.is_visible():
                return
            await self.page.wait_for_timeout(500)
        raise AssertionError(f"고객 리스트에서 고객 미노출: {customer_name}")

    async def _customer_exists_in_list(self, customer_name):
        list_item = self.page.locator(
            f"tr:has-text('{customer_name}'), li:has-text('{customer_name}'), div:has-text('{customer_name}')"
        ).first
        return await list_item.count() > 0 and await list_item.is_visible()

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

    async def _get_customer_summary_amounts(self, detail_page):
        text = re.sub(r"\s+", " ", await detail_page.locator("body").inner_text())
        sales = self._extract_amount_fuzzy(text, ["실 매출", "실매출"])
        membership = self._extract_amount_fuzzy(text, ["정액권", "회원권"])
        return sales, membership

    async def _get_ticket_count(self, detail_page):
        text = re.sub(r"\s+", " ", await detail_page.locator("body").inner_text())
        patterns = [
            r"티켓\s*(\d+)\s*회",
            r"보유\s*티켓\s*(\d+)\s*회",
            r"남은\s*티켓\s*(\d+)\s*회",
        ]
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                return int(m.group(1))
        return None

    async def _get_left_ticket_row(self, detail_page):
        candidates = [
            detail_page.locator("dl, li, div, section, article").filter(
                has_text=re.compile(r"티켓")
            ).filter(
                has=detail_page.get_by_role("button", name=re.compile(r"^\s*충전\s*$"))
            ),
            detail_page.locator("dl, li, div, section, article").filter(
                has=detail_page.get_by_text(re.compile(r"보유\s*티켓|남은\s*티켓|티켓"))
            ).filter(
                has=detail_page.get_by_role("button", name=re.compile(r"^\s*충전\s*$"))
            ),
        ]

        for locator in candidates:
            count = await locator.count()
            for idx in range(count):
                item = locator.nth(idx)
                text = re.sub(r"\s+", " ", await item.inner_text())
                if re.search(r"정액권|회원권", text):
                    continue
                if re.search(r"티켓", text):
                    return item
        raise AssertionError("좌측 티켓 충전 영역을 찾지 못했습니다.")

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
        await self.page.wait_for_timeout(1000)

        list_item = self.page.locator(f"tr:has-text('{customer_name}'), li:has-text('{customer_name}')").first
        await expect(list_item).to_be_visible(timeout=5000)
        try:
            async with self.context.expect_page(timeout=10000) as new_page_info:
                await list_item.click()
            detail_page = await new_page_info.value
            await detail_page.wait_for_load_state("domcontentloaded")
            await detail_page.bring_to_front()
            return detail_page
        except PlaywrightTimeoutError:
            # 환경에 따라 새 창이 아니라 현재 창/패널로 상세가 열릴 수 있음
            await list_item.click()
            await self.page.wait_for_timeout(1200)
            await self.page.wait_for_load_state("domcontentloaded")
            await self.page.bring_to_front()
            return self.page

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
        before_sales, before_membership = await self._get_customer_summary_amounts(detail_page)
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

        # 회원권 충전 레이어 확인
        modal = detail_page.locator("#modal-content:visible, [role='dialog']:visible, [aria-modal='true']:visible").first
        if await modal.count() == 0:
            modal = detail_page.locator("body")

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
        after_sales, after_membership = await self._get_customer_summary_amounts(detail_page)
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

        before_count = await self._get_ticket_count(detail_page)
        if before_count is None:
            before_count = 0

        ticket_row = await self._get_left_ticket_row(detail_page)
        await expect(ticket_row).to_be_visible(timeout=5000)
        popup_task = asyncio.create_task(detail_page.wait_for_event("popup", timeout=4000))
        await ticket_row.get_by_role("button", name=re.compile(r"^\s*충전\s*$")).first.click()

        try:
            ticket_charging_page = await popup_task
            await ticket_charging_page.wait_for_load_state("domcontentloaded")
        except PlaywrightTimeoutError:
            popup_task.cancel()
            ticket_charging_page = detail_page

        modal = ticket_charging_page.locator("#modal-content:visible, [role='dialog']:visible, [aria-modal='true']:visible").first
        if await modal.count() == 0:
            modal = ticket_charging_page.locator("body")
        await ticket_charging_page.wait_for_timeout(300)

        modal_text = re.sub(r"\s+", " ", await modal.inner_text())
        if not re.search(r"10\s*만원권\s*\(?카드\)?", modal_text):
            dropdown = modal.locator(
                "button.select-display:visible, [data-testid='select-toggle-button']:visible, button:has-text('만원권'):visible"
            ).first
            if await dropdown.count() > 0:
                await dropdown.click()
                option = ticket_charging_page.get_by_role(
                    "button",
                    name=re.compile(r"10\s*만원권\s*\(?카드\)?")
                ).locator(":visible").first
                if await option.count() > 0:
                    await option.click()

        submit_candidates = ["충전", "등록", "저장", "확인"]
        submit_clicked = False
        for label in submit_candidates:
            submit_btn = ticket_charging_page.locator("button:visible").filter(
                has_text=re.compile(rf"^\s*{re.escape(label)}\s*$")
            ).last
            if await submit_btn.count() > 0:
                await submit_btn.click()
                submit_clicked = True
                break

        assert submit_clicked, "티켓 충전 제출 버튼을 찾지 못했습니다."

        if ticket_charging_page is not detail_page:
            try:
                await ticket_charging_page.wait_for_event("close", timeout=7000)
            except PlaywrightTimeoutError:
                pass

        await detail_page.bring_to_front()
        await detail_page.wait_for_timeout(2000)

        after_count = None
        for _ in range(10):
            after_count = await self._get_ticket_count(detail_page)
            if after_count is not None and after_count > before_count:
                break
            await detail_page.wait_for_timeout(500)

        if after_count is not None and after_count > before_count:
            pass
        else:
            detail_text = re.sub(r"\s+", " ", await detail_page.locator("body").inner_text())
            assert re.search(r"10\s*만원권", detail_text), "티켓 충전 후 10만원권 노출 확인 실패"

        if detail_page is not self.page and not detail_page.is_closed():
            await detail_page.close()
            await self.focus_main_page()

    async def family_add_and_verify(self, owner_name=None, member_name=None):
        """패밀리 추가: owner 고객 상세 → 패밀리 탭 → member 검색·추가 → 멤버 확인"""
        if owner_name is None:
            owner_name = f"자동화_{self.mmdd}_1"
        if member_name is None:
            member_name = f"자동화_{self.mmdd}_3"

        # 고객차트 열기 → 고객 행 클릭 → 새 탭
        await self._open_customer_chart()
        await self._dismiss_active_dimmer()
        await self.page.wait_for_timeout(1000)

        row = self.page.locator(f"tr:has-text('{owner_name}')").first
        await expect(row).to_be_visible(timeout=5000)
        try:
            async with self.context.expect_page(timeout=10000) as new_page_info:
                await row.click()
            detail_page = await new_page_info.value
            await detail_page.wait_for_load_state("domcontentloaded")
            await detail_page.bring_to_front()
        except PlaywrightTimeoutError:
            # fallback: 같은 페이지에서 상세 열림
            detail_page = self.page
            await detail_page.wait_for_timeout(1200)

        print(f"✓ 고객 상세 진입: {detail_page.url}")

        # 패밀리 탭 클릭
        family_tab = detail_page.locator("button[role='tab']").filter(has_text="패밀리").first
        if await family_tab.count() == 0:
            family_tab = detail_page.locator("button:has-text('패밀리')").first
        await expect(family_tab).to_be_visible(timeout=10000)
        await family_tab.click()
        await detail_page.wait_for_timeout(1000)
        print("✓ 패밀리 탭 클릭 완료")

        # 이미 멤버가 추가되어 있는지 확인
        body_text = await detail_page.locator("body").inner_text()
        already_added = member_name in body_text

        if already_added:
            print(f"✓ {member_name} 이미 패밀리 멤버로 등록됨 — 추가 스킵")
        else:
            # 패밀리 추가하기 버튼 (빈 상태 또는 멤버 추가 버튼)
            add_family_btn = detail_page.get_by_role("button", name="패밀리 추가하기").first
            if await add_family_btn.count() == 0:
                add_family_btn = detail_page.locator(
                    "button:has-text('패밀리 추가하기'), button:has-text('멤버 추가'), button:has-text('추가하기')"
                ).first
            await expect(add_family_btn).to_be_visible(timeout=10000)
            await add_family_btn.click()
            await detail_page.wait_for_timeout(1000)
            print("✓ 패밀리 추가하기 클릭")

            # 고객 검색
            search_input = detail_page.get_by_placeholder("고객 이름, 연락처, 메모").first
            await expect(search_input).to_be_visible(timeout=5000)
            await search_input.type(member_name, delay=50)
            await detail_page.wait_for_timeout(2000)

            # 검색 결과에서 고객 선택
            results = detail_page.locator(
                "[class*='search'] li, [class*='dropdown'] li, [class*='list'] li, [class*='option']"
            ).filter(has_text=re.compile(re.escape(member_name)))
            if await results.count() > 0:
                await results.first.click()
            else:
                option = detail_page.get_by_text(member_name, exact=False).first
                await expect(option).to_be_visible(timeout=5000)
                await option.click()
            await detail_page.wait_for_timeout(500)
            print(f"✓ {member_name} 선택")

            # 모달 내 추가 버튼 클릭
            modal = detail_page.locator("#modal-content:visible, [role='dialog']:visible").first
            if await modal.count() > 0:
                add_btn = modal.get_by_role("button", name="추가", exact=True).first
            else:
                add_btn = detail_page.get_by_role("button", name="추가", exact=True).first
            await expect(add_btn).to_be_visible(timeout=5000)
            await add_btn.click(force=True)
            await detail_page.wait_for_timeout(2000)
            print("✓ 패밀리 추가 완료")

        # 멤버 영역 확인
        body_text = await detail_page.locator("body").inner_text()
        assert owner_name in body_text, f"멤버에 {owner_name}이 보이지 않습니다"
        print(f"✓ 멤버 확인: {owner_name}")
        assert member_name in body_text, f"멤버에 {member_name}이 보이지 않습니다"
        print(f"✓ 멤버 확인: {member_name}")

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

    async def _move_calendar_to_today(self):
        # 예약/검증 기준 날짜를 항상 오늘로 맞춘다.
        today_btn = self.page.get_by_role("button", name="오늘").first
        if await today_btn.count() == 0:
            today_btn = self.page.locator("button.fc-today-button:visible").first
        if await today_btn.count() > 0 and await today_btn.is_visible():
            await today_btn.click(force=True)
            await self.page.wait_for_timeout(400)

    def _reservation_scenarios(self):
        return [
            {"customer": f"자동화_{self.mmdd}_1", "time": "오후 4:00", "display_time": "오후 4:00", "menu_category": "손", "menu_item": "젤 기본"},
            {"customer": f"자동화_{self.mmdd}_2", "time": "오후 5:00", "display_time": "오후 5:00", "menu_category": "티켓", "menu_item": "10만원권"},
            {"customer": f"자동화_{self.mmdd}_3", "time": "오후 6:00", "display_time": "오후 6:00", "menu_category": "손", "menu_item": "케어"},
        ]

    async def make_reservations(self):
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()
        reservations = self._reservation_scenarios()

        async def open_reservation_form():
            for _ in range(5):
                # 다른 모달(알림/충전 등)이 떠 있을 수 있으므로 예약등록 모달만 인정
                modal = self.page.locator("#modal-content:visible, [role='dialog']:visible").first
                if await modal.count() > 0:
                    # 진입 직후 렌더 지연을 허용
                    await self.page.wait_for_timeout(300)
                    has_customer_search = await modal.locator("input#customer-search:visible").count() > 0
                    has_reserve_title = await modal.locator("h4:has-text('예약 등록'):visible, :text-is('예약 등록')").count() > 0
                    if has_customer_search or has_reserve_title:
                        return modal
                    await self.page.keyboard.press("Escape")
                    await self.page.wait_for_timeout(250)
                await self._dismiss_active_dimmer()
                await self.page.locator("#floating-layout button:visible").first.click(force=True)
                await self.page.wait_for_timeout(250)
                for cand in [
                    self.page.get_by_role("menuitem", name="예약 등록").locator(":visible").first,
                    self.page.get_by_role("button", name="예약 등록").locator(":visible").first,
                    self.page.locator("h4:has-text('예약 등록'):visible").first,
                    self.page.locator("button:has-text('예약 등록'):visible, [role='menuitem']:has-text('예약 등록'):visible").first,
                ]:
                    if await cand.count() == 0:
                        continue
                    try:
                        await cand.click(force=True, timeout=4000)
                        await self.page.wait_for_selector(
                            "#modal-content:visible input#customer-search:visible, [role='dialog']:visible input#customer-search:visible",
                            timeout=5000
                        )
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
        await self._move_calendar_to_today()
        expected = self._reservation_scenarios()
        await self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        for r in expected:
            reserve_card = None
            # 하단 시간대(예: 오후 6시) 카드가 뷰포트 밖일 수 있어 스크롤+재시도
            for step in range(8):
                reserve_card = self.page.locator("div.BOOKING.booking-normal").filter(has_text=r["customer"]).first
                if await reserve_card.count() == 0:
                    reserve_card = self.page.locator(
                        "div, li, article"
                    ).filter(
                        has_text=re.compile(
                            rf"{re.escape(r['display_time'])}.*{re.escape(r['customer'])}|{re.escape(r['customer'])}.*{re.escape(r['display_time'])}"
                        )
                    ).first
                if await reserve_card.count() == 0:
                    reserve_card = self.page.get_by_text(r["customer"], exact=True).first

                if await reserve_card.count() > 0 and await reserve_card.is_visible():
                    break

                # 시간축/캘린더 스크롤 영역을 아래로 내려 이벤트를 렌더링
                await self.page.mouse.wheel(0, 400)
                await self.page.wait_for_timeout(300)
                if step == 3:
                    # 중간에 해당 시간 라벨 근처로 점프 시도
                    time_slot = self.page.locator(f"text={r['display_time']}").first
                    if await time_slot.count() > 0:
                        try:
                            await time_slot.scroll_into_view_if_needed()
                        except Exception:
                            pass
            assert reserve_card is not None, f"예약 카드 찾기 실패: {r['customer']}"
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
                await self.page.wait_for_timeout(500)
                try:
                    await self.page.wait_for_load_state("networkidle")
                    still_open = self.page.locator("div:has(button:has-text('나가기'))").filter(has_text=r["customer"]).first
                    if await still_open.count() == 0 or not await still_open.is_visible():
                        closed = True
                        break
                except Exception:
                    # navigation으로 context가 바뀐 경우 — 패널이 닫힌 것으로 간주
                    closed = True
                    break
            assert closed, f"상세 패널 닫기 실패: {r['customer']}"

    async def _assert_sales_registration_page(self, expected_total=None):
        title = self.page.get_by_role("heading", name="매출 등록").locator(":visible").first
        if await title.count() == 0:
            title = self.page.locator("h1:has-text('매출 등록'):visible").first
        await expect(title).to_be_visible(timeout=5000)
        if expected_total is not None:
            total = self.page.locator("h2:visible").filter(has_text=re.compile(r"원")).first
            await expect(total).to_contain_text(expected_total, timeout=5000)

    async def _find_sales_save_click_point(self):
        return await self.page.evaluate(
            """() => {
                const buttons = [...document.querySelectorAll('button')]
                  .filter((b) => {
                    const text = (b.innerText || '').replace(/\\s+/g, ' ').trim();
                    if (!text.includes('매출') || !text.includes('저장')) return false;
                    if (b.disabled) return false;
                    const r = b.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                  });
                if (!buttons.length) return null;
                buttons.sort((a, b) => {
                  const ar = a.getBoundingClientRect();
                  const br = b.getBoundingClientRect();
                  if (ar.y === br.y) return br.width - ar.width;
                  return br.y - ar.y;
                });
                const r = buttons[0].getBoundingClientRect();
                return { x: r.left + (r.width / 2), y: r.top + (r.height / 2) };
            }"""
        )

    async def _click_sales_save_button(self):
        point = await self._find_sales_save_click_point()
        if point is None:
            raise AssertionError("매출 저장 버튼을 찾지 못했습니다.")
        dialog_messages = []

        def _auto_dismiss(dlg):
            dialog_messages.append(dlg.message)
            asyncio.create_task(dlg.dismiss())

        self.page.on("dialog", _auto_dismiss)
        try:
            await self.page.mouse.click(point["x"], point["y"])
            await self.page.wait_for_timeout(700)
        finally:
            self.page.remove_listener("dialog", _auto_dismiss)
        return dialog_messages

    async def _open_sales_registration_from_calendar(self, customer):
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()
        await self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)
        reserve_card = None
        for _ in range(8):
            reserve_card = self.page.locator("div.BOOKING.booking-normal").filter(has_text=customer).first
            if await reserve_card.count() == 0:
                reserve_card = self.page.get_by_text(customer, exact=True).first
            if await reserve_card.count() > 0 and await reserve_card.is_visible():
                break
            await self.page.mouse.wheel(0, 400)
            await self.page.wait_for_timeout(250)
        await expect(reserve_card).to_be_visible(timeout=5000)
        await reserve_card.click()
        await self.page.wait_for_timeout(400)
        sales_reg_btn = self.page.locator("button:has-text('매출 등록'):visible").last
        await expect(sales_reg_btn).to_be_visible(timeout=5000)
        await sales_reg_btn.click()
        await self.page.wait_for_timeout(500)

    async def sales_registrations_1(self):
        customer = f"자동화_{self.mmdd}_1"
        print(f"{customer} 매출등록 시작=====")
        await self._open_sales_registration_from_calendar(customer)
        await self._assert_sales_registration_page(expected_total="20,000원")

        membership_input = self.page.locator('input[name="정액권($membership원)"]').nth(1)
        await membership_input.click()
        await membership_input.fill("21000")
        dialog_messages = await self._click_sales_save_button()
        if dialog_messages:
            print("message:", dialog_messages[-1])

        await membership_input.click()
        await membership_input.fill("20000")
        await self._click_sales_save_button()
        print("✓ 매출 등록 1 완료")

    async def sales_registrations_2(self):
        customer = f"자동화_{self.mmdd}_2"
        print(f"{customer} 매출등록 시작=====")
        await self._open_sales_registration_from_calendar(customer)
        await self._assert_sales_registration_page(expected_total="0원")

        plus_btn = self.page.locator("button:has(svg[icon='systemRoundPlus'])").locator(":visible").last
        await plus_btn.click()
        ticket_value = await self.page.evaluate(
            """() => {
                const visible = (el) => {
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                };
                const candidates = [...document.querySelectorAll('input')]
                  .filter((i) => visible(i))
                  .filter((i) => {
                    const name = i.getAttribute('name') || '';
                    return name.includes('티켓');
                  });
                return candidates.length ? candidates[0].value : null;
            }"""
        )
        assert ticket_value is not None and ticket_value.strip() == "2", "티켓 차감 값 검증 실패(기대 2)"
        await self._click_sales_save_button()
        print("✓ 매출 등록 2 완료")

    async def sales_registrations_3(self):
        customer = f"자동화_{self.mmdd}_3"
        print(f"{customer} 매출등록 시작=====")
        await self._open_sales_registration_from_calendar(customer)
        await self._assert_sales_registration_page(expected_total="10,000원")

        insert_cash = self.page.locator('input[name="현금"]').nth(1)
        await insert_cash.click()
        await insert_cash.fill("5000")
        insert_card = self.page.locator('input[name="카드"]').nth(1)
        await insert_card.click()
        await insert_card.fill("5000")
        await self._click_sales_save_button()
        print("✓ 매출 등록 3 완료")

    async def sales_registrations_4(self):
        print("미등록고객 제품 매출등록 시작=====")
        await self.page.locator("h3:has-text('매출')").first.click()
        await self.page.locator(".new-item").first.click()
        await self.page.wait_for_load_state("networkidle")

        await self.page.locator("label:has(p:has-text('미등록 고객'))").locator(":visible").first.click()
        cust_name = self.page.locator("div.sc-e29c3c15-1.view p.kunnIt").first
        await expect(cust_name).to_have_text("미등록고객", timeout=2000)

        clicked_product_tab = await self.page.evaluate(
            """() => {
                const nodes = [...document.querySelectorAll('div,button')];
                const tab = nodes.find((el) => {
                    const text = (el.textContent || '').replace(/\\s+/g, '').trim();
                    if (text !== '제품0') return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 0 && r.height > 0;
                });
                if (!tab) return false;
                tab.click();
                return true;
            }"""
        )
        assert clicked_product_tab, "'제품0' 탭을 찾지 못했습니다."
        await self.page.wait_for_timeout(500)

        product_select = self.page.locator("button.select-display:visible").filter(
            has_text=re.compile(r"제품을 선택해 주세요\\.|제품을 선택해 주세요")
        ).first
        await expect(product_select).to_be_visible(timeout=5000)
        await product_select.click()

        group_btn = self.page.locator(
            "button:has-text('미분류'):visible, li:has-text('미분류'):visible, [role='option']:has-text('미분류'):visible"
        ).first
        await expect(group_btn).to_be_visible(timeout=5000)
        await group_btn.click()
        await self.page.wait_for_timeout(300)

        item_btn = self.page.locator(
            "button:has-text('01_제품_테스트'):visible, li:has-text('01_제품_테스트'):visible, [role='option']:has-text('01_제품_테스트'):visible"
        ).first
        await expect(item_btn).to_be_visible(timeout=5000)
        await item_btn.click()
        await self.page.wait_for_timeout(300)

        insert_naver = self.page.locator('input[name="네이버페이"]').nth(1)
        await insert_naver.click()
        await insert_naver.fill("5000")
        insert_receivable = self.page.locator('input[name="미수금"]').nth(1)
        await insert_receivable.click()
        await insert_receivable.fill("5000")
        await self._click_sales_save_button()
        print("✓ 매출 등록 4 완료")

    async def verify_shop_status_today_summary(self, expected_sales=None, expected_reservations=None):
        await self.focus_main_page()

        def shop_status_locator():
            return self.page.locator(
                "a:has-text('샵 현황'):visible, a:has-text('샵현황'):visible, "
                "button:has-text('샵 현황'):visible, button:has-text('샵현황'):visible, "
                "h4:has-text('샵 현황'):visible, h4:has-text('샵현황'):visible, "
                "li:has-text('샵 현황'):visible, li:has-text('샵현황'):visible, "
                "span:has-text('샵 현황'):visible, span:has-text('샵현황'):visible"
            ).first

        shop_status_menu = shop_status_locator()
        # 홈이 이미 펼쳐진 상태일 수 있으므로, 샵 현황이 안 보일 때만 홈 클릭
        if await shop_status_menu.count() == 0 or not await shop_status_menu.is_visible():
            home_menu = self.page.locator("h3:has-text('홈'):visible").first
            await expect(home_menu).to_be_visible(timeout=5000)
            await home_menu.click()
            await self.page.wait_for_timeout(400)

        shop_status_menu = shop_status_locator()
        await expect(shop_status_menu).to_be_visible(timeout=5000)
        await shop_status_menu.click()
        await self.page.wait_for_load_state("domcontentloaded")
        await self.page.wait_for_timeout(700)

        metric_values = self.page.locator("p.color-primary-300:visible")
        await expect(metric_values.first).to_be_visible(timeout=5000)
        texts = [t.strip() for t in await metric_values.all_inner_texts()]

        sales_text = next((t for t in texts if "원" in t and re.search(r"\d", t)), "")
        assert sales_text, f"오늘의 실매출 값(p.color-primary-300) 찾기 실패: {texts}"

        reserve_value_el = self.page.locator(
            "div:has(> h3:has-text('예약')) > p.color-primary-300:visible"
        ).first
        if await reserve_value_el.count() > 0 and await reserve_value_el.is_visible():
            reserve_text = (await reserve_value_el.inner_text()).strip()
        else:
            reserve_text = next((t for t in texts if re.fullmatch(r"[0-9]+", re.sub(r"\s+", "", t))), "")
        assert reserve_text, f"오늘의 예약 값 찾기 실패: {texts}"

        sales_match = re.search(r"([0-9][0-9,]*)\s*원", sales_text)
        assert sales_match is not None, f"오늘의 실매출 금액 파싱 실패: {sales_text}"
        sales_value = int(sales_match.group(1).replace(",", ""))

        reserve_match = re.search(r"([0-9]+)", reserve_text)
        assert reserve_match is not None, f"오늘의 예약 건수 파싱 실패: {reserve_text}"
        reserve_value = int(reserve_match.group(1))

        # 기대값이 주어진 경우에만 고정값 비교
        if expected_sales is not None:
            expected_sales_value = int(re.sub(r"\D", "", str(expected_sales)) or "0")
            assert sales_value == expected_sales_value, (
                f"오늘의 실매출 검증 실패 (기대: {expected_sales_value}, 실제: {sales_value})"
            )
        if expected_reservations is not None:
            expected_reservation_value = int(re.sub(r"\D", "", str(expected_reservations)) or "0")
            assert reserve_value == expected_reservation_value, (
                f"오늘의 예약 검증 실패 (기대: {expected_reservation_value}, 실제: {reserve_value})"
            )

        print(f"✓ 오늘의 실매출 검증 완료: {sales_value:,}원")
        print(f"✓ 오늘의 예약 검증 완료: {reserve_value}건")

    async def _open_statistics_page(self):
        await self.focus_main_page()
        stats_menu = self.page.locator(
            "h3:has-text('통계'):visible, a:has-text('통계'):visible, button:has-text('통계'):visible"
        ).first
        await expect(stats_menu).to_be_visible(timeout=5000)
        await stats_menu.click()
        await self.page.wait_for_load_state("domcontentloaded")
        await self.page.wait_for_timeout(700)

    async def _open_stat_detail(self, card_title):
        # 카드 제목 기준으로 같은 카드 컨테이너 안의 [자세히 보기]를 클릭한다.
        clicked = await self.page.evaluate(
            """(title) => {
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
            }""",
            card_title,
        )
        assert clicked, f"'{card_title} 카드의 자세히 보기 클릭 실패"
        await self.page.wait_for_load_state("domcontentloaded")
        await self.page.wait_for_timeout(700)

    async def _apply_today_filter(self):
        range_btn = self.page.locator(
            "button:has(svg[icon='reserveCalender']):visible"
        ).filter(
            has_text=re.compile(r"\d{1,2}\.\s*\d{1,2}\.\s*\d{1,2}")
        ).first
        if await range_btn.count() == 0:
            range_btn = self.page.locator(
                "button.sc-c8a80cb6-2:has(svg[icon='reserveCalender']):visible, "
                "button:has(svg[icon='reserveCalender']):visible"
            ).first
        await expect(range_btn).to_be_visible(timeout=5000)
        await range_btn.click()
        await self.page.wait_for_timeout(500)

        today_btn = self.page.locator(
            "button.sc-c8a80cb6-6:has(h4:has-text('오늘')):visible, "
            "button:has(h4:has-text('오늘')):visible"
        ).first
        if await today_btn.count() == 0:
            today_btn = self.page.get_by_role("button", name="오늘").locator(":visible").first
        await expect(today_btn).to_be_visible(timeout=3000)
        await today_btn.click()
        await self.page.wait_for_timeout(300)

        search_btn = self.page.get_by_role("button", name=re.compile(r"기간 검색$")).locator(":visible").first
        if await search_btn.count() == 0:
            search_btn = self.page.locator("button:has-text('기간 검색'):visible").last
        if await search_btn.count() == 0:
            search_btn = self.page.get_by_text("기간 검색", exact=False).locator(":visible").last
        await expect(search_btn).to_be_visible(timeout=3000)
        await search_btn.click()
        await self.page.wait_for_timeout(700)

    async def _get_table_value_by_header(self, table, header_text, row=None):
        header = table.locator(f"thead th:has-text('{header_text}')").first
        await expect(header).to_be_visible(timeout=3000)
        col_idx = await header.evaluate("th => Array.from(th.parentElement.children).indexOf(th) + 1")
        target_row = row or table.locator("tbody tr:visible").first
        cell = target_row.locator(f"td:nth-child({col_idx})").first
        await expect(cell).to_be_visible(timeout=3000)
        text = re.sub(r"\s+", " ", (await cell.inner_text()).strip())
        m = re.search(r"([0-9][0-9,]*)\s*원", text)
        assert m is not None, f"{header_text} 값 파싱 실패: {text}"
        return int(m.group(1).replace(",", ""))

    async def _find_today_row_in_table(self, table):
        rows = table.locator("tbody tr:visible")
        row_count = await rows.count()
        month = int(self.mmdd[:2])
        day = int(self.mmdd[2:])
        yy = datetime.now().strftime("%y")
        patterns = [
            f"{yy}. {month}. {day}",
            f"{month}. {day}",
            f"{month}.{day}",
            f"{self.mmdd[:2]}.{self.mmdd[2:]}",
        ]
        for i in range(row_count):
            r = rows.nth(i)
            text = re.sub(r"\s+", " ", (await r.inner_text()).strip())
            if any(p in text for p in patterns):
                return r
        return rows.first

    async def _table_has_today_row(self, table):
        month = int(self.mmdd[:2])
        day = int(self.mmdd[2:])
        yy = datetime.now().strftime("%y")
        patterns = [
            f"{yy}. {month}. {day}",
            f"{month}. {day}",
            f"{month}.{day}",
            f"{self.mmdd[:2]}.{self.mmdd[2:]}",
        ]
        txt = re.sub(r"\s+", " ", (await table.inner_text()).strip())
        return any(p in txt for p in patterns)

    async def _go_back_from_statistics_detail(self):
        back_btn = self.page.locator("button:has(h4:has-text('뒤로가기')):visible, button:has-text('뒤로가기'):visible").first
        await expect(back_btn).to_be_visible(timeout=5000)
        await back_btn.click()
        await self.page.wait_for_timeout(700)

    async def verify_statistics_details(self):
        # 기존 호환용: 상세 검증만 필요한 테스트가 있으면 재사용 가능
        await self.verify_shop_status_and_statistics()

    async def verify_shop_status_and_statistics(self):
        # 1) 홈 > 샵 현황 요약
        await self.verify_shop_status_today_summary()

        # 2) 통계 > 상품별/결제수단별 상세
        await self._open_statistics_page()

        await self._open_stat_detail("상품별 통계")
        await self._apply_today_filter()
        product_tables = self.page.locator("table:visible").filter(
            has_text=re.compile(r"실\s*매출\s*합계|정액권\s*판매|티켓\s*판매|총\s*합계")
        )
        product_table = product_tables.first
        product_count = await product_tables.count()
        for i in range(product_count):
            t = product_tables.nth(i)
            if await self._table_has_today_row(t):
                product_table = t
                break
        await expect(product_table).to_be_visible(timeout=5000)

        product_row = await self._find_today_row_in_table(product_table)
        product_sales = await self._get_table_value_by_header(product_table, "실 매출 합계", row=product_row)
        product_membership = await self._get_table_value_by_header(product_table, "정액권 판매", row=product_row)
        product_ticket = await self._get_table_value_by_header(product_table, "티켓 판매", row=product_row)
        product_total = await self._get_table_value_by_header(product_table, "총 합계", row=product_row)
        assert product_sales == 320000, f"상품별 통계 실 매출 합계 불일치: {product_sales}"
        assert product_membership == 200000, f"상품별 통계 정액권 판매 불일치: {product_membership}"
        assert product_ticket == 100000, f"상품별 통계 티켓 판매 불일치: {product_ticket}"
        assert product_total == 360000, f"상품별 통계 총 합계 불일치: {product_total}"
        print("✓ 상품별 통계 검증 완료: 실매출 320,000 / 정액권 200,000 / 티켓 100,000 / 총합계 360,000")
        await self._go_back_from_statistics_detail()

        await self._open_stat_detail("결제 수단별 통계")
        await self._apply_today_filter()
        payment_table = self.page.locator("table:visible").filter(
            has_text=re.compile(r"실\s*매출\s*합계|차감\s*합계|총\s*합계")
        ).first
        await expect(payment_table).to_be_visible(timeout=5000)
        payment_row = await self._find_today_row_in_table(payment_table)
        payment_sales = await self._get_table_value_by_header(payment_table, "실 매출 합계", row=payment_row)
        payment_deduct = await self._get_table_value_by_header(payment_table, "차감 합계", row=payment_row)
        payment_total = await self._get_table_value_by_header(payment_table, "총 합계", row=payment_row)
        assert payment_sales == 320000, f"결제수단 통계 실 매출 합계 불일치: {payment_sales}"
        assert payment_deduct == 40000, f"결제수단 통계 차감 합계 불일치: {payment_deduct}"
        assert payment_total == 360000, f"결제수단 통계 총 합계 불일치: {payment_total}"
        print("✓ 결제 수단별 통계 검증 완료: 실매출 320,000 / 차감 40,000 / 총합계 360,000")


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
async def test_sales_registrations_1_to_4_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.sales_registrations_1()
        await runner.sales_registrations_2()
        await runner.sales_registrations_3()
        await runner.sales_registrations_4()
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_verify_shop_status_today_summary_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.verify_shop_status_today_summary()
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_verify_statistics_details_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.verify_shop_status_and_statistics()
    finally:
        await runner.teardown()
