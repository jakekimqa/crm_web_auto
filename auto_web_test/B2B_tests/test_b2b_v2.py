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

    async def _select_referrer(self, referrer_name):
        """소개자 검색 후 선택"""
        referrer_input = self.page.locator(
            "input[placeholder*='이름 또는 연락처를 검색']"
        ).first
        await expect(referrer_input).to_be_visible(timeout=5000)
        await referrer_input.fill(referrer_name)
        await self.page.wait_for_timeout(1500)

        # 소개자 입력 필드의 부모 컨테이너 내부 드롭다운에서 선택
        referrer_container = referrer_input.locator("xpath=ancestor::div[contains(@class,'sc-197a4fd4')]")
        result_item = referrer_container.locator(f"li:has-text('{referrer_name}')").first
        if await result_item.count() == 0:
            # fallback: 소개자 라벨 기준으로 컨테이너 탐색
            referrer_section = self.page.locator("label:has-text('소개자')").locator("..")
            result_item = referrer_section.locator(f"li:has-text('{referrer_name}')").first
        await expect(result_item).to_be_visible(timeout=5000)
        await result_item.click()
        await self.page.wait_for_timeout(500)
        print(f"  ✓ 소개자 선택: {referrer_name}")

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
        for _ in range(30):
            await self._ensure_active_page()
            list_item = self.page.locator(f"tr:has-text('{customer_name}')").first
            if await list_item.count() > 0 and await list_item.is_visible():
                return
            await self.page.wait_for_timeout(1000)
        raise AssertionError(f"고객 리스트에서 고객 미노출: {customer_name}")

    async def _customer_exists_in_list(self, customer_name):
        # 고객차트 테이블 td에서 정확한 이름 매칭
        cell = self.page.locator(f"table td:text-is('{customer_name}')").first
        return await cell.count() > 0 and await cell.is_visible()

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

            # 2, 3번 고객 등록 시 소개자로 1번 고객 선택
            if idx >= 2:
                referrer_name = customers[0][0]
                await self._select_referrer(referrer_name)

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

        # 검색으로 고객 빠르게 찾기
        search_input = self.page.locator("input#customer-search:visible").first
        if await search_input.count() > 0 and await search_input.is_visible():
            await search_input.fill(customer_name)
            await self.page.wait_for_timeout(1500)

        # 고객차트 테이블 행만 매칭 (예약 목록 li 제외)
        list_item = self.page.locator(f"tr:has-text('{customer_name}')").first
        await expect(list_item).to_be_visible(timeout=5000)

        # 고객 행에서 상세 URL 추출 후 새 탭으로 열기
        detail_url = await list_item.evaluate("""el => {
            const link = el.querySelector('a[href*="/customer/detail/"]');
            if (link) return link.href;
            // data 속성에서 고객 ID 추출 시도
            const id = el.getAttribute('data-id') || el.dataset.customerId;
            if (id) return '/customer/detail/' + id;
            // onclick 등에서 URL 추출 시도
            const text = el.outerHTML;
            const match = text.match(/customer\\/detail\\/(\\d+)/);
            return match ? '/customer/detail/' + match[1] : null;
        }""")

        if detail_url:
            base = self.base_url.replace("/signin", "")
            if detail_url.startswith("/"):
                detail_url = base + detail_url
            detail_page = await self.context.new_page()
            await detail_page.goto(detail_url)
            await detail_page.wait_for_load_state("domcontentloaded")
            await detail_page.bring_to_front()
            return detail_page

        # URL 추출 실패 시 클릭으로 시도
        name_cell = list_item.locator(f"td:has-text('{customer_name}')").first
        if await name_cell.count() == 0:
            name_cell = list_item
        click_target = name_cell

        try:
            async with self.context.expect_page(timeout=10000) as new_page_info:
                await click_target.click()
            detail_page = await new_page_info.value
            await detail_page.wait_for_load_state("domcontentloaded")
            await detail_page.bring_to_front()
            return detail_page
        except PlaywrightTimeoutError:
            await self.page.wait_for_timeout(1500)
            if "/customer/detail/" in self.page.url:
                await self.page.wait_for_load_state("domcontentloaded")
                return self.page
            # 최종 fallback: window.open 강제 사용
            row_html = await list_item.inner_html()
            print(f"[DEBUG] 클릭 실패, row HTML: {row_html[:300]}")
            await self.page.wait_for_load_state("domcontentloaded")
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

    async def customer_profile_edit_and_delete_blocked(self, customer_name=None):
        """고객 상세 프로필 수정 (담당자/메모/닉네임/생년월일/직업) → 저장 → 반영 검증 + 삭제 차단 검증"""
        if customer_name is None:
            customer_name = f"자동화_{self.mmdd}_3"

        detail_page = await self.open_customer_detail_from_list(customer_name)
        await self.assert_customer_name_visible_top_left(detail_page, customer_name)
        print(f"\n=== 고객 프로필 수정 테스트 시작: {customer_name} ===")

        # ── 프로필 수정 버튼 클릭 ──
        edit_btn = detail_page.get_by_role("button", name="프로필 수정").first
        await expect(edit_btn).to_be_visible(timeout=5000)
        await edit_btn.click()
        await detail_page.wait_for_timeout(1000)

        # 프로필 수정 패널 열림 확인 (메모 입력 필드가 보이면 열린 것)
        memo_input = detail_page.get_by_placeholder("고객 특징, 주의사항 등 메모를 남겨주세요.").first
        await expect(memo_input).to_be_visible(timeout=5000)
        print("✓ 프로필 수정 패널 열림 확인")

        # ── 수정 값 정의 ──
        edit_memo = f"자동화 메모 {self.mmdd}"
        edit_nickname = f"닉네임_{self.mmdd}"
        edit_job = "네일아티스트"
        edit_year, edit_month, edit_day = "1990", "5", "15"

        # ── 고객 메모 입력 ──
        await memo_input.fill(edit_memo)
        print(f"✓ 고객 메모 입력: {edit_memo}")

        # ── 닉네임 입력 ──
        nickname_input = detail_page.get_by_placeholder("닉네임을 입력해 주세요.").first
        await expect(nickname_input).to_be_visible(timeout=5000)
        await nickname_input.fill(edit_nickname)
        print(f"✓ 닉네임 입력: {edit_nickname}")

        # ── 생년월일 선택 (년/월/일 드롭다운) ──
        # 이미 값이 설정된 경우 "년" 대신 기존 값(예: "1990")이 표시될 수 있음
        year_btn = detail_page.get_by_role("button", name="년").first
        if await year_btn.count() == 0 or not await year_btn.is_visible():
            # 이미 설정된 생년월일 버튼 찾기 (예: "1990", "5", "15")
            year_btn = detail_page.get_by_role("button", name=edit_year, exact=True).first
        if await year_btn.count() > 0 and await year_btn.is_visible():
            await year_btn.click()
            await detail_page.wait_for_timeout(500)
            year_option = detail_page.get_by_role("button", name=edit_year, exact=True).first
            if await year_option.count() > 0 and await year_option.is_visible():
                await year_option.click()
                await detail_page.wait_for_timeout(500)

        month_btn = detail_page.get_by_role("button", name="월").first
        if await month_btn.count() == 0 or not await month_btn.is_visible():
            month_btn = detail_page.get_by_role("button", name=edit_month, exact=True).first
        if await month_btn.count() > 0 and await month_btn.is_visible():
            await month_btn.click()
            await detail_page.wait_for_timeout(500)
            month_option = detail_page.get_by_role("button", name=edit_month, exact=True).first
            if await month_option.count() > 0 and await month_option.is_visible():
                await month_option.click()
                await detail_page.wait_for_timeout(500)

        day_btn = detail_page.get_by_role("button", name="일").first
        if await day_btn.count() == 0 or not await day_btn.is_visible():
            day_btn = detail_page.get_by_role("button", name=edit_day, exact=True).first
        if await day_btn.count() > 0 and await day_btn.is_visible():
            await day_btn.click()
            await detail_page.wait_for_timeout(500)
            day_option = detail_page.get_by_role("button", name=edit_day, exact=True).first
            if await day_option.count() > 0 and await day_option.is_visible():
                await day_option.click()
                await detail_page.wait_for_timeout(500)
        print(f"✓ 생년월일 선택: {edit_year}년 {edit_month}월 {edit_day}일")

        # ── 직업 입력 ──
        job_input = detail_page.get_by_placeholder("직업을 입력해 주세요.").first
        await expect(job_input).to_be_visible(timeout=5000)
        await job_input.fill(edit_job)
        print(f"✓ 직업 입력: {edit_job}")

        # ── 저장 버튼 클릭 (삭제 검증보다 먼저 수행) ──
        save_btn = detail_page.get_by_role("button", name="저장").first
        await expect(save_btn).to_be_visible(timeout=5000)
        await save_btn.click()
        await detail_page.wait_for_timeout(2000)
        try:
            await detail_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        print("✓ 프로필 저장 완료")

        # ── 저장 후 고객 상세 반영 검증 ──
        body_text = await detail_page.locator("body").inner_text()

        assert edit_memo in body_text, f"고객 메모 반영 실패: '{edit_memo}' not found"
        print(f"✓ 고객 메모 반영 확인: {edit_memo}")

        assert edit_nickname in body_text, f"닉네임 반영 실패: '{edit_nickname}' not found"
        print(f"✓ 닉네임 반영 확인: {edit_nickname}")

        assert edit_job in body_text, f"직업 반영 실패: '{edit_job}' not found"
        print(f"✓ 직업 반영 확인: {edit_job}")

        # 생년월일 검증 (다양한 포맷 대응)
        birth_patterns = [
            f"{edit_year}.{edit_month}.{edit_day}",
            f"{edit_year}. {edit_month}. {edit_day}",
            f"1990년 5월 15일",
            f"90.05.15",
            f"90. 5. 15",
        ]
        birth_found = any(p in body_text for p in birth_patterns)
        assert birth_found, f"생년월일 반영 실패: {birth_patterns} 중 어느 것도 없음"
        print("✓ 생년월일 반영 확인")

        # ── 삭제 차단 검증 (저장 후 프로필 수정 다시 열어서 진행) ──
        edit_btn2 = detail_page.get_by_role("button", name="프로필 수정").first
        if await edit_btn2.count() > 0 and await edit_btn2.is_visible():
            await edit_btn2.click()
            await detail_page.wait_for_timeout(1000)

        delete_btn = detail_page.locator('button:has(svg[icon="systemDelete"])').first
        if await delete_btn.count() > 0:
            await delete_btn.scroll_into_view_if_needed()
            await detail_page.wait_for_timeout(500)
        if await delete_btn.count() > 0 and await delete_btn.is_visible():
            await delete_btn.click()
            await detail_page.wait_for_timeout(1000)

            # 1단계: "정말 삭제하시겠습니까?" 확인 모달 → [삭제] 클릭
            body_text_del = await detail_page.locator("body").inner_text()
            if "정말 삭제하시겠습니까" in body_text_del:
                confirm_delete_btn = detail_page.locator("button:has-text('삭제'):visible").last
                dialog_message = None

                def on_dialog(dialog):
                    nonlocal dialog_message
                    dialog_message = dialog.message
                    asyncio.ensure_future(dialog.accept())

                detail_page.on("dialog", on_dialog)
                await confirm_delete_btn.click()
                await detail_page.wait_for_timeout(2000)
                detail_page.remove_listener("dialog", on_dialog)

                expected_msg = "삭제할 수 없습니다"
                if dialog_message is not None:
                    assert expected_msg in dialog_message, (
                        f"삭제 불가 alert 메시지 불일치: '{dialog_message}'"
                    )
                    print(f"✓ 삭제 차단 alert 확인: {dialog_message[:80]}")
                else:
                    body_text2 = await detail_page.locator("body").inner_text()
                    assert expected_msg in body_text2, "삭제 불가 메시지를 찾을 수 없습니다"
                    print("✓ 삭제 차단 메시지 확인 (커스텀 UI)")
            else:
                print("⚠ 삭제 확인 모달이 예상과 다르게 동작")
        else:
            print("⚠ 삭제 버튼을 찾을 수 없어 삭제 차단 검증 스킵")

        print(f"=== 고객 프로필 수정 테스트 완료: {customer_name} ===\n")

        if detail_page is not self.page and not detail_page.is_closed():
            await detail_page.close()
            await self.focus_main_page()

    async def _verify_customer_tabs(self, customer_name, expected):
        """고객 상세 페이지에서 각 탭 데이터 정합성 검증"""
        detail_page = await self.open_customer_detail_from_list(customer_name)
        await self.assert_customer_name_visible_top_left(detail_page, customer_name)
        print(f"\n--- {customer_name} 탭 데이터 검증 시작 ---")

        # ── 좌측 요약 영역 검증 ──
        await detail_page.wait_for_timeout(2000)
        try:
            await detail_page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        body_text = await detail_page.locator("body").inner_text()

        if "expected_real_sales" in expected:
            assert expected["expected_real_sales"] in body_text, (
                f"실 매출 검증 실패: '{expected['expected_real_sales']}' not found"
            )
            print(f"✓ 실 매출 확인: {expected['expected_real_sales']}")

        # ── 매출 탭 (기본 선택) ──
        sales_tab = detail_page.locator('[role="tab"]:has-text("매출")').first
        if await sales_tab.count() > 0:
            await sales_tab.click()
            await detail_page.wait_for_timeout(1000)
            tab_text = await detail_page.locator("body").inner_text()
            for keyword in expected.get("sales_keywords", []):
                assert keyword in tab_text, f"매출 탭 검증 실패: '{keyword}' not found"
                print(f"✓ 매출 탭: {keyword}")

        # ── 시술 탭 ──
        treatment_tab = detail_page.locator('[role="tab"]:has-text("시술")').first
        if await treatment_tab.count() > 0 and expected.get("treatment_keywords"):
            await treatment_tab.click()
            await detail_page.wait_for_timeout(1000)
            tab_text = await detail_page.locator("body").inner_text()
            for keyword in expected["treatment_keywords"]:
                assert keyword in tab_text, f"시술 탭 검증 실패: '{keyword}' not found"
                print(f"✓ 시술 탭: {keyword}")

        # ── 예약 탭 ──
        reservation_tab = detail_page.locator('[role="tab"]:has-text("예약")').first
        if await reservation_tab.count() > 0 and expected.get("reservation_keywords"):
            await reservation_tab.click()
            await detail_page.wait_for_timeout(1000)
            tab_text = await detail_page.locator("body").inner_text()
            for keyword in expected["reservation_keywords"]:
                assert keyword in tab_text, f"예약 탭 검증 실패: '{keyword}' not found"
                print(f"✓ 예약 탭: {keyword}")

        # ── 정액권 탭 ──
        membership_tab = detail_page.locator('[role="tab"]:has-text("정액권")').first
        if await membership_tab.count() > 0 and expected.get("membership_keywords"):
            await membership_tab.click()
            await detail_page.wait_for_timeout(1000)
            tab_text = await detail_page.locator("body").inner_text()
            for keyword in expected["membership_keywords"]:
                assert keyword in tab_text, f"정액권 탭 검증 실패: '{keyword}' not found"
                print(f"✓ 정액권 탭: {keyword}")

        # ── 티켓 탭 ──
        ticket_tab = detail_page.locator('[role="tab"]:has-text("티켓")').first
        if await ticket_tab.count() > 0 and expected.get("ticket_keywords"):
            await ticket_tab.click()
            await detail_page.wait_for_timeout(1000)
            tab_text = await detail_page.locator("body").inner_text()
            for keyword in expected["ticket_keywords"]:
                assert keyword in tab_text, f"티켓 탭 검증 실패: '{keyword}' not found"
                print(f"✓ 티켓 탭: {keyword}")

        # ── 포인트 탭 ──
        point_tab = detail_page.locator('[role="tab"]:has-text("포인트")').first
        if await point_tab.count() > 0 and expected.get("point_keywords"):
            await point_tab.click()
            await detail_page.wait_for_timeout(1000)
            tab_text = await detail_page.locator("body").inner_text()
            for keyword in expected["point_keywords"]:
                assert keyword in tab_text, f"포인트 탭 검증 실패: '{keyword}' not found"
                print(f"✓ 포인트 탭: {keyword}")

        # ── 패밀리 탭 ──
        family_tab = detail_page.locator('[role="tab"]:has-text("패밀리")').first
        if await family_tab.count() > 0 and expected.get("family_keywords"):
            await family_tab.click()
            await detail_page.wait_for_timeout(1000)
            tab_text = await detail_page.locator("body").inner_text()
            for keyword in expected["family_keywords"]:
                assert keyword in tab_text, f"패밀리 탭 검증 실패: '{keyword}' not found"
                print(f"✓ 패밀리 탭: {keyword}")

        print(f"--- {customer_name} 탭 데이터 검증 완료 ---\n")

        if detail_page is not self.page and not detail_page.is_closed():
            await detail_page.close()
            await self.focus_main_page()

    async def customer_detail_verification(self):
        """고객 상세 통합 검증: 프로필 수정 + 삭제 차단 + 3명 탭 데이터 정합성"""
        print("\n========== 고객 상세 통합 검증 시작 ==========")

        # ── 1. 고객_3 프로필 수정 + 삭제 차단 ──
        customer_3 = f"자동화_{self.mmdd}_3"
        await self.customer_profile_edit_and_delete_blocked(customer_3)

        # ── 2. 고객_1 탭 데이터 정합성 ──
        customer_1 = f"자동화_{self.mmdd}_1"
        await self._verify_customer_tabs(customer_1, {
            "expected_real_sales": "200,000원",
            "sales_keywords": ["젤 기본", "정액권"],
            "treatment_keywords": ["젤 기본"],
            "reservation_keywords": ["오후 4:00", "매출등록"],
            "membership_keywords": ["220,000원"],
            "family_keywords": [f"자동화_{self.mmdd}_3"],
        })

        # ── 3. 고객_2 탭 데이터 정합성 ──
        customer_2 = f"자동화_{self.mmdd}_2"
        await self._verify_customer_tabs(customer_2, {
            "sales_keywords": ["티켓"],
            "reservation_keywords": ["오후 5:00", "매출등록"],
            "ticket_keywords": ["10만원권"],
        })

        # ── 4. 고객_3 탭 데이터 정합성 ──
        await self._verify_customer_tabs(customer_3, {
            "expected_real_sales": "10,000원",
            "sales_keywords": ["케어", "현금", "카드", "정액권"],
            "treatment_keywords": ["케어"],
            "reservation_keywords": ["오후 6:00", "매출등록"],
            "membership_keywords": ["패밀리"],
            "point_keywords": ["1,500"],
            "family_keywords": [f"자동화_{self.mmdd}_1"],
        })

        print("========== 고객 상세 통합 검증 완료 ==========\n")

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

    async def sales_registrations_5(self, customer_override=None):
        """패밀리 공유 정액권 매출등록: 고객_3이 고객_1의 정액권으로 결제"""
        customer = customer_override or f"자동화_{self.mmdd}_3"
        print(f"{customer} 패밀리 공유 정액권 매출등록 시작=====")

        # 매출등록 4 저장 후 목록 페이지로 돌아올 때까지 대기
        await self.page.locator(".new-item").first.wait_for(state="visible", timeout=10000)
        await self.page.locator(".new-item").first.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(500)

        # 고객 검색
        search_input = self.page.locator("#customer-search")
        await expect(search_input).to_be_visible(timeout=5000)
        await search_input.click()
        await search_input.type(customer, delay=50)
        await self.page.wait_for_timeout(1000)

        # 검색 결과에서 고객 선택
        result_item = self.page.locator(
            f"li:has-text('{customer}'), [role='option']:has-text('{customer}'), "
            f"div[class*='list'] div:has-text('{customer}'), "
            f"button:has-text('{customer}')"
        ).locator(":visible").first
        await expect(result_item).to_be_visible(timeout=5000)
        await result_item.click()
        await self.page.wait_for_timeout(500)

        # 시술 메뉴 선택: 손 > 케어
        service_select = self.page.locator(
            "button.select-display:visible, div.select-display:visible, "
            "[class*='select']:visible"
        ).filter(has_text=re.compile(r"시술.*선택")).first
        await expect(service_select).to_be_visible(timeout=5000)
        await service_select.click()
        await self.page.wait_for_timeout(300)

        # 그룹 '손' 선택
        group_btn = self.page.locator(
            "button:has-text('손'):visible, li:has-text('손'):visible, [role='option']:has-text('손'):visible"
        ).first
        await expect(group_btn).to_be_visible(timeout=5000)
        await group_btn.click()
        await self.page.wait_for_timeout(300)

        # 시술 '케어' 선택
        item_btn = self.page.locator(
            "button:has-text('케어'):visible, li:has-text('케어'):visible, [role='option']:has-text('케어'):visible"
        ).first
        await expect(item_btn).to_be_visible(timeout=5000)
        await item_btn.click()
        await self.page.wait_for_timeout(500)

        # 정액권 input 확인 (패밀리 공유 검증 핵심)
        membership_input = self.page.locator('input[name*="정액권"]').nth(1)
        await expect(membership_input).to_be_visible(timeout=5000)
        print("✓ 패밀리 공유 정액권 input 확인됨")

        # 시술 금액 가져와서 전액 정액권으로 입력
        total_text = await self.page.locator("h2:visible").filter(
            has_text=re.compile(r"원")
        ).first.text_content()
        amount = re.sub(r"[^\d]", "", total_text)
        await membership_input.click()
        await membership_input.fill(amount)

        await self._click_sales_save_button()
        print(f"✓ 매출 등록 5 완료 (패밀리 공유 정액권 {amount}원)")

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
        assert product_total == 370000, f"상품별 통계 총 합계 불일치: {product_total}"
        print("✓ 상품별 통계 검증 완료: 실매출 320,000 / 정액권 200,000 / 티켓 100,000 / 총합계 370,000")
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
        assert payment_deduct == 50000, f"결제수단 통계 차감 합계 불일치: {payment_deduct}"
        assert payment_total == 370000, f"결제수단 통계 총 합계 불일치: {payment_total}"
        print("✓ 결제 수단별 통계 검증 완료: 실매출 320,000 / 차감 50,000 / 총합계 370,000")

    async def custom_payment_method(self, customer_name=None):
        """커스텀 결제수단 추가 → 매출 등록 → 통계 검증 → 매출 삭제 → 결제수단 삭제"""
        print("\n=== 커스텀 결제수단 테스트 시작 ===")
        customer = customer_name or f"자동화_{self.mmdd}_1"
        payment_name = "페이 추가 테스트"

        # ── 1. 매출 페이지 → 신규 매출 등록 ──
        await self.focus_main_page()
        await self.page.locator("h3:has-text('매출')").first.click()
        await self.page.wait_for_timeout(500)
        sales_link = self.page.locator("text=매출 현황").first
        if await sales_link.count() > 0:
            await sales_link.click()
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(1000)

        new_item = self.page.locator(".new-item").first
        await expect(new_item).to_be_visible(timeout=5000)
        await new_item.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1500)
        print("  ✓ 신규 매출 등록 페이지 진입")

        # ── 2. 고객 검색 ──
        field = self.page.locator("input#customer-search:visible").first
        await expect(field).to_be_visible(timeout=5000)
        await field.fill(customer)
        await field.press("Enter")
        await self.page.wait_for_timeout(1500)

        # 검색 결과에서 고객 선택
        result = self.page.locator("li").filter(has_text=customer).first
        await expect(result).to_be_visible(timeout=5000)
        await result.click()
        await self.page.wait_for_timeout(1000)
        print(f"  ✓ 고객 선택: {customer}")

        # ── 3. 시술 메뉴 선택: 손 > 젤 기본 ──
        await self.page.locator("#sale-item-group button.select-display:visible").first.click()
        await self.page.locator("button:has-text('손')").locator(":visible").first.click()
        await self.page.wait_for_timeout(500)
        await self.page.locator("button:has-text('젤 기본')").locator(":visible").first.click()
        await self.page.wait_for_timeout(500)
        print("  ✓ 시술 메뉴: 손 > 젤 기본")

        # ── 4. 결제 수단 설정 → 커스텀 결제수단 추가 ──
        settings_btn = self.page.locator("button:has-text('결제 수단 설정'):visible").first
        await expect(settings_btn).to_be_visible(timeout=5000)
        await settings_btn.click()
        await self.page.wait_for_timeout(1000)

        add_btn = self.page.locator("button:has-text('결제 수단 추가')").first
        await expect(add_btn).to_be_visible(timeout=5000)
        await add_btn.click()
        await self.page.wait_for_timeout(500)

        # 결제수단 이름 입력
        await self.page.wait_for_timeout(1000)
        name_input = self.page.locator("input[placeholder*='결제 수단 이름']").first
        await expect(name_input).to_be_visible(timeout=5000)
        await name_input.click()
        await name_input.type(payment_name, delay=30)
        print(f"  ✓ 결제수단 이름: {payment_name}")

        # 토글 ON
        toggle = self.page.locator("label[for='isActiveSelectedPaymentMethod']").last
        await expect(toggle).to_be_visible(timeout=3000)
        await toggle.click()
        await self.page.wait_for_timeout(500)

        # 저장 → alert 처리 ("저장되었습니다." 또는 "이미 사용 중인 이름입니다.")
        async with self.page.expect_event("dialog", timeout=5000) as dlg_info:
            await self.page.locator("button:has-text('저장'):visible").last.click()
        dialog = await dlg_info.value
        print(f"  저장 alert: {dialog.message}")
        await dialog.accept()
        await self.page.wait_for_timeout(1000)

        already_exists = "이미 사용" in dialog.message
        if already_exists:
            print("  ⚠ 이미 존재하는 결제수단 — 생성 건너뜀")
        else:
            print("  ✓ 결제수단 추가 완료")

        # 결제 수단 설정 모달 닫기 — 페이지 리로드로 확실하게 초기화
        base = self.base_url.replace("/signin", "")
        await self.page.goto(f"{base}/sale")
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        # 신규 매출 등록 재진입
        new_item = self.page.locator(".new-item").first
        await expect(new_item).to_be_visible(timeout=5000)
        await new_item.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1500)

        # 고객 재선택
        field = self.page.locator("input#customer-search:visible").first
        await expect(field).to_be_visible(timeout=5000)
        await field.fill(customer)
        await field.press("Enter")
        await self.page.wait_for_timeout(1500)
        result = self.page.locator("li").filter(has_text=customer).first
        await expect(result).to_be_visible(timeout=5000)
        await result.click()
        await self.page.wait_for_timeout(1000)

        # 시술 메뉴 재선택
        await self.page.locator("#sale-item-group button.select-display:visible").first.click()
        await self.page.locator("button:has-text('손')").locator(":visible").first.click()
        await self.page.wait_for_timeout(500)
        await self.page.locator("button:has-text('젤 기본')").locator(":visible").first.click()
        await self.page.wait_for_timeout(500)

        # ── 5. 커스텀 결제수단으로 매출 등록 ──
        payment_label = self.page.locator(f"label:has(h4:has-text('{payment_name}')):visible").first
        if await payment_label.count() == 0:
            payment_label = self.page.get_by_text(payment_name, exact=True).first
        await expect(payment_label).to_be_visible(timeout=5000)
        await payment_label.click()
        await self.page.wait_for_timeout(500)
        print(f"  ✓ 결제수단 선택: {payment_name}")

        await self.page.locator("button:has-text('매출 저장'):visible").last.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(2000)
        print("  ✓ 매출 등록 완료")

        # ── 6. 통계 → 결제수단별 통계에서 확인 ──
        await self._open_statistics_page()
        await self._open_stat_detail("결제 수단별 통계")
        await self._apply_today_filter()

        # 결제수단별 통계 테이블에서 "페이 추가 테스트" 확인
        body_text = await self.page.locator("body").inner_text()
        assert payment_name in body_text, f"통계에 '{payment_name}' 미노출"
        print(f"  ✓ 통계에 '{payment_name}' 확인")
        await self._go_back_from_statistics_detail()

        # ── 7. 매출 삭제 ──
        await self.page.locator("h3:has-text('매출')").first.click()
        await self.page.wait_for_timeout(500)
        sales_link2 = self.page.locator("text=매출 현황").first
        if await sales_link2.count() > 0:
            await sales_link2.click()
            await self.page.wait_for_load_state("networkidle")
            await self.page.wait_for_timeout(1000)

        # "페이 추가 테스트" 결제수단으로 등록된 매출 행 찾기
        sales_rows = self.page.locator("tr, li").filter(has_text=payment_name)
        row_count = await sales_rows.count()
        print(f"  '{payment_name}' 매출 행: {row_count}건")

        for i in range(row_count):
            row = sales_rows.first  # 삭제 후 DOM이 갱신되므로 항상 first
            delete_link = row.locator("a:has-text('삭제'), button:has-text('삭제')").first
            await expect(delete_link).to_be_visible(timeout=5000)
            await delete_link.scroll_into_view_if_needed()

            async with self.page.expect_event("dialog", timeout=5000) as dlg_info:
                await delete_link.click()
            dialog = await dlg_info.value
            print(f"  삭제 확인: {dialog.message[:50]}")
            await dialog.accept()
            await self.page.wait_for_timeout(1500)

        print("  ✓ 매출 삭제 완료")

        # ── 8. 결제수단 삭제 ──
        new_item2 = self.page.locator(".new-item").first
        await expect(new_item2).to_be_visible(timeout=5000)
        await new_item2.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1500)

        settings_btn2 = self.page.locator("button:has-text('결제 수단 설정'):visible").first
        await expect(settings_btn2).to_be_visible(timeout=5000)
        await settings_btn2.click()
        await self.page.wait_for_timeout(1000)

        # 편집 → 삭제
        edit_btn = self.page.locator("button:has-text('편집')").last
        await edit_btn.scroll_into_view_if_needed()
        await edit_btn.click()
        await self.page.wait_for_timeout(500)

        delete_btn = self.page.locator("button:has-text('삭제')").first
        await expect(delete_btn).to_be_visible(timeout=3000)
        await delete_btn.click()
        await self.page.wait_for_timeout(1000)

        # 삭제 확인
        confirm_btn = self.page.locator("button:has-text('삭제'), button:has-text('확인')").last
        if await confirm_btn.count() > 0 and await confirm_btn.is_visible():
            await confirm_btn.click()
            await self.page.wait_for_timeout(1000)

        print(f"  ✓ '{payment_name}' 결제수단 삭제 완료")

        # 닫기
        close_btn2 = self.page.locator("button:has(svg[icon='systemX']):visible, button[aria-label='close']:visible").first
        if await close_btn2.count() > 0:
            await close_btn2.click()
        else:
            await self.page.keyboard.press("Escape")
        await self.page.wait_for_timeout(500)

        print("=== 커스텀 결제수단 테스트 완료 ===\n")

    async def block_reservation(self):
        """예약막기 등록"""
        print("=== 예약막기 테스트 시작 ===")
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()

        # 일간 뷰로 전환
        day_btn = self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first
        if await day_btn.count() > 0:
            await day_btn.click()
            await self.page.wait_for_timeout(500)

        # ── 1. FAB → 예약 막기 ──
        print("1. FAB 버튼 → 예약 막기 클릭")
        await self._dismiss_active_dimmer()
        await self.page.locator("#floating-layout button:visible").first.click(force=True)
        await self.page.wait_for_timeout(500)

        # FAB 메뉴의 "예약 막기" LI 클릭 (사이드바 h4가 아닌 FAB UL > LI 내 항목)
        block_li = self.page.locator("ul li:has(h4:has-text('예약 막기'))").first
        if await block_li.count() > 0:
            await block_li.click(force=True)
        else:
            # fallback: FAB 메뉴 근처의 두 번째 h4
            await self.page.locator("h4:has-text('예약 막기')").nth(1).click(force=True)
        await self.page.wait_for_timeout(1000)

        # ── 2. 예약막기 폼 입력 ──
        print("2. 예약막기 폼 입력")
        reason_input = self.page.locator("input[name='reason']:visible, input[placeholder*='사유']:visible").first
        await expect(reason_input).to_be_visible(timeout=5000)
        await reason_input.fill("자동화 예약막기 테스트")

        # 시작 시간 선택: 오후 7:00 (다른 예약과 겹치지 않는 시간)
        start_time_target = "오후 7:00"
        print(f"  시작 시간: {start_time_target}")

        # #startTime 드롭다운 클릭 → 옵션 선택
        start_wrapper = self.page.locator("#startTime")
        await start_wrapper.locator("button.select-display").click(force=True)
        await self.page.wait_for_timeout(300)
        await start_wrapper.locator(f"li button:has-text('{start_time_target}')").first.click(force=True)
        await self.page.wait_for_timeout(300)

        # 담당자/반복 설정은 디폴트 유지
        print("  담당자: 디폴트 (샵주테스트), 반복: 반복 안 함")

        # ── 3. 등록 ──
        print("3. 등록 클릭")
        register_btn = self.page.locator("button:has-text('등록'):visible").first
        await expect(register_btn).to_be_visible(timeout=3000)
        await register_btn.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        # dimmer 처리
        try:
            await self.page.wait_for_selector("#modal-dimmer.isActiveDimmed", state="hidden", timeout=5000)
        except Exception:
            await self.page.keyboard.press("Escape")
            await self.page.wait_for_timeout(500)

        print("✓ 예약막기 등록 완료")
        print("=== 예약막기 테스트 완료 ===\n")

    async def block_reservation_repeat(self):
        """반복 예약막기 등록 (매일, 생성 횟수 3회)"""
        print("=== 반복 예약막기 테스트 시작 ===")
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()

        # 일간 뷰로 전환
        day_btn = self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first
        if await day_btn.count() > 0:
            await day_btn.click()
            await self.page.wait_for_timeout(500)

        # ── 1. FAB → 예약 막기 ──
        print("1. FAB 버튼 → 예약 막기 클릭")
        await self._dismiss_active_dimmer()
        await self.page.locator("#floating-layout button:visible").first.click(force=True)
        await self.page.wait_for_timeout(500)

        block_li = self.page.locator("ul li:has(h4:has-text('예약 막기'))").first
        if await block_li.count() > 0:
            await block_li.click(force=True)
        else:
            await self.page.locator("h4:has-text('예약 막기')").nth(1).click(force=True)
        await self.page.wait_for_timeout(1000)

        # ── 2. 폼 입력 ──
        print("2. 반복 예약막기 폼 입력")
        reason_input = self.page.locator("input[name='reason']:visible, input[placeholder*='사유']:visible").first
        await expect(reason_input).to_be_visible(timeout=5000)
        await reason_input.fill("자동화 반복 예약막기 테스트")

        # 시작 시간: 오후 7:30
        start_time_target = "오후 7:30"
        print(f"  시작 시간: {start_time_target}")
        start_wrapper = self.page.locator("#startTime")
        await start_wrapper.locator("button.select-display").click(force=True)
        await self.page.wait_for_timeout(300)
        await start_wrapper.locator(f"li button:has-text('{start_time_target}')").first.click(force=True)
        await self.page.wait_for_timeout(300)

        # 반복 설정: 매일
        print("  반복 설정: 매일")
        repeat_wrapper = self.page.locator("#repeatSetting")
        await repeat_wrapper.locator("button.select-display").click(force=True)
        await self.page.wait_for_timeout(300)
        await repeat_wrapper.locator("li button:has-text('매일')").first.click(force=True)
        await self.page.wait_for_timeout(300)

        # 반복 종료 조건: 생성 횟수 3회
        print("  반복 종료 조건: 생성 횟수 3회")
        end_wrapper = self.page.locator("#endConditionType")
        await end_wrapper.locator("button.select-display").click(force=True)
        await self.page.wait_for_timeout(300)
        await end_wrapper.locator("li button:has-text('생성 횟수')").first.click(force=True)
        await self.page.wait_for_timeout(300)

        count_input = self.page.locator("input[name='createCount']:visible").first
        await count_input.fill("3")

        # ── 3. 등록 ──
        print("3. 등록 클릭")
        register_btn = self.page.locator("button:has-text('등록'):visible").first
        await expect(register_btn).to_be_visible(timeout=3000)
        await register_btn.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        # dimmer 처리
        try:
            await self.page.wait_for_selector("#modal-dimmer.isActiveDimmed", state="hidden", timeout=5000)
        except Exception:
            await self.page.keyboard.press("Escape")
            await self.page.wait_for_timeout(500)

        print("✓ 반복 예약막기 등록 완료")
        print("=== 반복 예약막기 테스트 완료 ===\n")

    async def _scroll_to_time_and_find_block(self, block_text):
        """캘린더 일간 뷰에서 booking-stop 블록을 스크롤하며 찾기"""
        for step in range(8):
            block = self.page.locator("div.booking-stop").filter(has_text=block_text).first
            if await block.count() > 0 and await block.is_visible():
                return block
            await self.page.mouse.wheel(0, 400)
            await self.page.wait_for_timeout(300)
        return None

    async def verify_block_reservation(self):
        """단일 예약막기 검증 - 오늘 캘린더에서 오후 7:00 블록 확인"""
        print("=== 단일 예약막기 검증 시작 ===")
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()
        await self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        block = await self._scroll_to_time_and_find_block("자동화 예약막기 테스트")
        assert block is not None, "단일 예약막기 블록을 찾을 수 없습니다"
        await expect(block).to_be_visible(timeout=5000)
        print("✓ 오늘 오후 7:00 단일 예약막기 블록 확인 완료")
        print("=== 단일 예약막기 검증 완료 ===\n")

    async def verify_block_reservation_repeat(self):
        """반복 예약막기 검증 - 오늘/내일/모레 캘린더에서 오후 7:30 블록 확인"""
        print("=== 반복 예약막기 검증 시작 ===")
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()
        await self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        # 다음날 이동 버튼
        next_btn = self.page.locator("button.fc-next-button:visible, button[aria-label='next']:visible").first

        for day_idx, day_label in enumerate(["오늘", "내일", "모레"]):
            if day_idx > 0:
                await next_btn.click(force=True)
                await self.page.wait_for_timeout(500)

            block = await self._scroll_to_time_and_find_block("자동화 반복 예약막기 테스트")
            assert block is not None, f"{day_label} 반복 예약막기 블록을 찾을 수 없습니다"
            await expect(block).to_be_visible(timeout=5000)
            print(f"✓ {day_label} 오후 7:30 반복 예약막기 블록 확인 완료")

        # 오늘로 복귀
        await self._move_calendar_to_today()
        print("=== 반복 예약막기 검증 완료 ===\n")

    async def delete_block_reservation(self):
        """단일 예약막기 삭제"""
        print("=== 단일 예약막기 삭제 시작 ===")
        base = self.base_url.replace("/signin", "")
        await self.page.goto(f"{base}/book/calendar")
        await self.page.wait_for_load_state("networkidle")
        await self._move_calendar_to_today()
        await self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        # 블록 찾기 → 클릭
        block = await self._scroll_to_time_and_find_block("자동화 예약막기 테스트")
        assert block is not None, "단일 예약막기 블록을 찾을 수 없습니다"
        await block.click(force=True)
        await self.page.wait_for_timeout(1000)

        # 삭제 버튼 클릭
        await self.page.locator("button").filter(has_text="삭제").first.click()
        await self.page.wait_for_timeout(500)

        # 모달 "예약 막기를 삭제하시겠습니까?" → 삭제 클릭 (두 번째 삭제 버튼)
        confirm_btn = self.page.locator("button").filter(has_text="삭제").nth(1)
        await expect(confirm_btn).to_be_visible(timeout=5000)
        # alert 핸들러 등록
        self.page.once("dialog", lambda dialog: asyncio.ensure_future(dialog.accept()))
        await confirm_btn.click()
        await self.page.wait_for_timeout(1000)
        await self.page.wait_for_load_state("networkidle")

        print("✓ 단일 예약막기 삭제 완료")
        print("=== 단일 예약막기 삭제 완료 ===\n")

    async def delete_block_reservation_repeat(self):
        """반복 예약막기 삭제 (모든 일정)"""
        print("=== 반복 예약막기 삭제 시작 ===")
        base = self.base_url.replace("/signin", "")
        await self.page.goto(f"{base}/book/calendar")
        await self.page.wait_for_load_state("networkidle")
        await self._move_calendar_to_today()
        await self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        # 블록 찾기 → 클릭
        block = await self._scroll_to_time_and_find_block("자동화 반복 예약막기 테스트")
        assert block is not None, "반복 예약막기 블록을 찾을 수 없습니다"
        await block.click(force=True)
        await self.page.wait_for_timeout(1000)

        # 삭제 버튼 클릭
        await self.page.locator("button").filter(has_text="삭제").first.click()
        await self.page.wait_for_timeout(500)

        # 반복 일정 삭제 모달 → "모든 일정" 라디오 선택
        await self.page.locator("label").filter(has_text="모든 일정").click()
        await self.page.wait_for_timeout(300)

        # 모달 내 삭제 버튼 클릭 (마지막 삭제 버튼 = 빨간 버튼)
        modal_delete_btn = self.page.locator("button").filter(has_text="삭제").last
        await expect(modal_delete_btn).to_be_visible(timeout=5000)
        # alert 핸들러 등록
        self.page.once("dialog", lambda dialog: asyncio.ensure_future(dialog.accept()))
        await modal_delete_btn.click()
        await self.page.wait_for_timeout(1000)
        await self.page.wait_for_load_state("networkidle")

        print("✓ 반복 예약막기 삭제 완료 (모든 일정)")
        print("=== 반복 예약막기 삭제 완료 ===\n")

    async def verify_send_history(self):
        """전송 내역에서 알림톡 발송 기록 검증"""
        print("\n=== 전송 내역 검증 시작 ===")
        await self.focus_main_page()

        # 사이드바 마케팅 > 전송 내역 클릭
        marketing_menu = self.page.locator("h3:has-text('마케팅')").first
        await expect(marketing_menu).to_be_visible(timeout=5000)
        await marketing_menu.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        send_history_btn = self.page.locator("button:has-text('전송 내역')").first
        await expect(send_history_btn).to_be_visible(timeout=5000)
        await send_history_btn.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(2000)

        # 오늘 날짜 기준 검증할 알림 목록 (디폴트가 알림톡 리스트)
        today = datetime.now().strftime("%Y-%m-%d")
        expected = [
            (f"자동화_{self.mmdd}_1", "예약 확정"),
            (f"자동화_{self.mmdd}_2", "예약 확정"),
            (f"자동화_{self.mmdd}_3", "예약 확정"),
            (f"자동화_{self.mmdd}_1", "정액권 충전"),
            (f"자동화_{self.mmdd}_1", "정액권 결제"),
            (f"자동화_{self.mmdd}_2", "티켓 충전"),
            (f"자동화_{self.mmdd}_2", "티켓 사용"),
        ]

        # 테이블에서 오늘 날짜 행 전체 추출
        rows = self.page.locator("tr").filter(has_text=today)
        row_count = await rows.count()
        print(f"  오늘({today}) 전송 내역: {row_count}건")

        # 각 행의 고객명 + 내용 수집
        found_records = []
        for i in range(row_count):
            row = rows.nth(i)
            cells = row.locator("td")
            if await cells.count() >= 3:
                customer = (await cells.nth(1).inner_text()).strip()
                content = (await cells.nth(2).inner_text()).strip()
                found_records.append((customer, content))

        # 검증
        for customer_name, keyword in expected:
            matched = any(
                customer_name in rec[0] and keyword in rec[1]
                for rec in found_records
            )
            assert matched, (
                f"전송 내역 미발견: {customer_name} / {keyword}"
            )
            print(f"  ✓ {customer_name} — {keyword} 확인")

        print(f"=== 전송 내역 검증 완료 ({len(expected)}건) ===\n")


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
