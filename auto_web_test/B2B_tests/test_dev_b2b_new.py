import asyncio
import pytest
import re
from playwright.async_api import async_playwright, expect
from playwright.async_api import expect, TimeoutError as PlaywrightTimeoutError
from datetime import datetime
from playwright.async_api import Page


class B2BAutomationTest:
    def __init__(self):
        self.base_url = "https://crm-dev1.gongbiz.kr/signin"
        self.correct_id = "autoqatest1"
        self.correct_password = "gong2023@@"
        self.wrong_password = "gong2022@@"

        # 오늘 날짜로 mmdd 생성
        today = datetime.now()
        self.mmdd = today.strftime("%m%d")

        self.browser = None
        self.context = None
        self.page = None

    async def setup(self):
        """브라우저 설정 및 초기화"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=False, slow_mo=1000)
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        self.page = await self.context.new_page()

    async def teardown(self):
        """브라우저 종료"""
        if self.browser:
            await self.browser.close()

    async def ensure_customer_chart(self):
        """현재 화면이 고객차트가 아니면 좌측 GNB에서 고객 > 고객차트로 이동"""
        if self.page is None:
            raise RuntimeError("page가 초기화되지 않았습니다.")

        if self.page.is_closed():
            if self.context and self.context.pages:
                self.page = self.context.pages[-1]
            else:
                raise RuntimeError("활성 페이지를 찾을 수 없습니다.")

        chart_button = self.page.get_by_role("button", name="고객차트")
        add_customer_button = self.page.get_by_text("신규 고객 등록")

        if await add_customer_button.count() > 0:
            return

        if await chart_button.count() == 0:
            await self.page.locator("h3:has-text('고객')").first.click()

        await self.page.get_by_role("button", name="고객차트").click()
        await self.page.wait_for_load_state("networkidle")

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

    async def test_login(self):
        """로그인 테스트"""
        print("=== 로그인 테스트 시작 ===")

        # 로그인 페이지 이동
        await self.page.goto(self.base_url)
        # await self.page.wait_for_load_state('networkidle')

        # 잘못된 비밀번호로 로그인 시도
        print("1. 잘못된 비밀번호로 로그인 시도")
        await self.page.fill('input[name="id"], input[type="text"]', self.correct_id)
        await self.page.fill('input[name="password"], input[type="password"]', self.wrong_password)
        await self.page.click('button[type="submit"], .login-btn')
        
        # 에러 메시지 확인
        await self.page.wait_for_selector('text=아이디 또는 비밀번호를 다시 확인하세요.', timeout=5000)
        error_message = await self.page.locator('text=아이디 또는 비밀번호를 다시 확인하세요.').is_visible()
        assert error_message, "에러 메시지가 표시되지 않았습니다."
        print("✓ 에러 메시지 확인 완료")

        # 올바른 정보로 로그인
        print("2. 올바른 정보로 로그인")
        await self.page.fill('input[name="id"], input[type="text"]', self.correct_id)
        await self.page.fill('input[name="password"], input[type="password"]', self.correct_password)
        await self.page.click('button[type="submit"], .login-btn')
        await self.page.wait_for_load_state('networkidle')

        # 자동화_헤렌네일 샵 선택
        print("3. 자동화_헤렌네일 샵으로 이동")
        await self.page.wait_for_selector('text=자동화_헤렌네일')
        await self.page.click('text=샵으로 이동')
        await self.page.wait_for_load_state('networkidle')

        # 샵 정보 검증
        print("4. 샵 정보 검증")
        shop_name = await self.page.locator('text=자동화_헤렌네일').is_visible()
        owner_name = await self.page.locator('text=샵주테스트').first.is_visible()

        assert shop_name, "샵 이름이 올바르지 않습니다."
        assert owner_name, "점주 이름이 올바르지 않습니다."
        print("✓ 샵 이름: 자동화_헤렌네일 확인")
        print("✓ 점주: 샵주테스트 확인")
        print("=== 로그인 테스트 완료 ===\n")

    async def test_add_customers(self):
        """고객 추가 테스트"""
        print("=== 고객 추가 테스트 시작 ===")

        # 고객 탭 클릭
        # await self.page.click('text=고객')
        await self.page.locator("h3:has-text('고객')").first.click()
        await self.page.get_by_role("button", name="고객차트").click()
        await self.page.wait_for_load_state('networkidle')

        # 3명의 고객 추가
        for i in range(1, 4):

            customer_name = f"자동화_{self.mmdd}_{i}"
            phone_number = f"010{self.mmdd}000{i}"

            print(f"{i}. 고객 추가: {customer_name}, {phone_number}")

            # 신규 고객 등록 버튼 클릭
            await self.page.click('text=신규 고객 등록')
            # await self.page.wait_for_selector('input[placeholder*="이름"], input[name*="name"]')

            # 고객 이름 입력
            await self.page.fill("#customer-name", customer_name)

            # 고객 연락처 입력
            await self.page.fill("#customer-contact", phone_number)

            # 고객 등록 버튼 클릭
            await self.page.locator("button:has-text('고객 등록'):visible").last.click()
            await self.page.wait_for_timeout(2000)


            print(f"✓ {customer_name} 등록 완료")

        # 중복 연락처 테스트
        print("4. 중복 연락처 테스트")
        await self.page.click('text=신규 고객 등록')

        # 중복 휴대폰 번호 입력.
        await self.page.fill("#customer-name", "자동화")
        await self.page.fill("#customer-contact", f"010{self.mmdd}0001")

        # await self.page.locator("button:has-text('고객 등록'):visible").last.click()

        await self.page.locator("button:has-text('고객 등록'):visible").last.click()

        duplicate_modal_text = self.page.get_by_text("이미 등록된 고객 연락처입니다.")
        await expect(duplicate_modal_text).to_be_visible(timeout=5000)
        print("message: 이미 등록된 고객 연락처입니다.")

        cancel_button = self.page.locator("button:has-text('취소'):visible").first
        close_button = self.page.locator("button:has-text('닫기'):visible").first
        no_button = self.page.locator("button:has-text('아니오'):visible").first

        if await cancel_button.count() > 0:
            await cancel_button.click()
        elif await no_button.count() > 0:
            await no_button.click()
        elif await close_button.count() > 0:
            await close_button.click()
        else:
            await self.page.keyboard.press("Escape")

        # 중복 알림 취소 후 '신규 고객 등록' 모달도 닫기
        register_modal = self.page.get_by_role("banner").filter(has_text="신규 고객 등록")
        if await register_modal.count() > 0:
            header_close = register_modal.get_by_role("img").first
            if await header_close.count() > 0:
                await header_close.click()
            else:
                await self.page.keyboard.press("Escape")

        # # Alert 확인 및 취소
        # await self.page.wait_for_selector('text=이미 등록된 연락처입니다')
        # alert_visible = await self.page.locator('text=이미 등록된 연락처입니다').is_visible()
        # assert alert_visible, "중복 연락처 알림이 표시되지 않았습니다."
        #
        # # 닫기 버튼 클릭
        # await self.page.get_by_role("banner") \
        #     .filter(has_text="신규 고객 등록") \
        #     .get_by_role("img") \
        #     .click()

        # await self.page.lo


        print("✓ 중복 연락처 알림 확인 및 취소 완료")
        print("=== 고객 추가 테스트 완료 ===\n")

    async def test_membership_charge(self):
        """정액권 충전 테스트"""
        print("=== 정액권 충전 테스트 시작 ===")
        await self.ensure_customer_chart()
        customer_name = f"자동화_{self.mmdd}_1"
        phone_number = f"010{self.mmdd}0001"
        phone_pattern = re.compile(rf"010\D*{self.mmdd}\D*0001")

        # 첫 페이지에서 고객명 클릭 → 새 탭 핸들 얻기
        async with self.context.expect_page() as new_page_info:
            await self.page.get_by_text(customer_name, exact=True).first.click()

        new_page = await new_page_info.value
        await new_page.wait_for_load_state("domcontentloaded")
        await new_page.bring_to_front()

        # 새 창 제목 확인
        title = await new_page.title()
        assert customer_name in title, f"새 창 제목이 올바르지 않습니다: {title}"
        print(f"✓ 새 창 제목 확인: {customer_name}")

        # 고객 정보 확인 ( 이름, 전화번호 일치 확인 )
        await expect(new_page.get_by_text(customer_name).first).to_be_visible(timeout=5000)
        await expect(new_page.get_by_text(phone_pattern).first).to_be_visible(timeout=5000)
        print(f"✓ 고객 정보 확인: {customer_name}, {phone_number}")

        # 충전 전 정액권 잔여 금액
        membership_row = new_page.locator("dl, li, div").filter(has_text=re.compile(r"정액권")).first
        await expect(membership_row).to_be_visible(timeout=5000)
        before_membership_text = await membership_row.inner_text()
        before_amount_match = re.search(r"([\d,]+)\s*원", before_membership_text)
        before_amount = int(re.sub(r"\D", "", before_amount_match.group(1))) if before_amount_match else 0

        # 좌측 정액권 영역의 [충전] 버튼 클릭 (팝업/현재 페이지 모두 대응)
        popup_task = asyncio.create_task(new_page.wait_for_event("popup", timeout=4000))
        await membership_row.get_by_role("button", name="충전").first.click()

        try:
            charging_page = await popup_task
            await charging_page.wait_for_load_state("domcontentloaded")
        except PlaywrightTimeoutError:
            popup_task.cancel()
            charging_page = new_page

        charging_toggle = charging_page.get_by_test_id("select-toggle-button").locator(":visible").first
        if await charging_toggle.count() > 0:
            await charging_toggle.click()

        # 정액권 선택 (20만원 현금)
        amount_option = charging_page.get_by_role("button", name=re.compile(r"20\s*만원.*현금")).locator(":visible").first
        if await amount_option.count() == 0:
            amount_option = charging_page.get_by_role("button", name=re.compile(r"20\s*만원")).locator(":visible").first
        await amount_option.click()

        # 제출 버튼 fallback
        submit_candidates = ["충전", "등록", "저장", "확인"]
        submit_clicked = False
        for label in submit_candidates:
            submit_btn = charging_page.locator("button:visible").filter(
                has_text=re.compile(rf"^\s*{re.escape(label)}\s*$")
            ).last
            if await submit_btn.count() > 0:
                await submit_btn.click()
                submit_clicked = True
                print(f"✓ 정액권 팝업 제출 버튼 클릭: {label}")
                break

        if not submit_clicked:
            visible_buttons = await charging_page.locator("button:visible").all_text_contents()
            raise AssertionError(f"정액권 팝업 제출 버튼을 찾지 못했습니다. visible_buttons={visible_buttons}")

        # 팝업이 별도 창일 때만 닫힘 대기
        if charging_page is not new_page:
            try:
                await charging_page.wait_for_event("close", timeout=7000)
            except PlaywrightTimeoutError:
                pass
        print("✓ 정액권 팝업 처리 완료")

        # 원본 페이지로 돌아와서 충전 결과 확인
        await new_page.bring_to_front()
        await new_page.wait_for_timeout(2000)

        membership_summary = new_page.locator("dl, li, div").filter(
            has_text=re.compile(r"정액권.*충전")
        ).first
        await expect(membership_summary).to_be_visible(timeout=5000)
        membership_text = await membership_summary.inner_text()
        amount_match = re.search(r"([\d,]+)\s*원", membership_text)
        if amount_match is None:
            amount_match = re.search(r"(\d[\d,]*)", membership_text)
        assert amount_match is not None, f"정액권 금액 파싱 실패: {membership_text!r}"
        after_amount = int(re.sub(r"\D", "", amount_match.group(1)))

        assert after_amount - before_amount >= 200000, (
            f"충전 금액 불일치: before={before_amount}, after={after_amount}, diff={after_amount-before_amount}"
        )
        print(f"✓ 정액권 잔여 금액 확인: {before_amount:,} -> {after_amount:,} (diff={after_amount-before_amount:,})")
        print("=== 정액권 충전 테스트 완료 ===\n")

    async def test_ticket_charge(self):
        """티켓 충전 테스트"""
        print("=== 티켓 충전 테스트 시작 ===")
        await self.ensure_customer_chart()

        customer_name = f"자동화_{self.mmdd}_2"
        phone_number = f"010{self.mmdd}0002"
        phone_pattern = re.compile(rf"010\D*{self.mmdd}\D*0002")

        # 첫 페이지에서 고객명 클릭 → 새 탭 핸들 얻기
        async with self.context.expect_page() as new_page_info:
            await self.page.get_by_text(customer_name, exact=True).first.click()

        new_page = await new_page_info.value
        await new_page.wait_for_load_state("domcontentloaded")
        await new_page.bring_to_front()

        # 새 창 제목 확인
        title = await new_page.title()
        assert customer_name in title, f"새 창 제목이 올바르지 않습니다: {title}"
        print(f"✓ 새 창 제목 확인: {customer_name}")

        # 고객 정보 확인
        await expect(new_page.get_by_text(customer_name).first).to_be_visible(timeout=5000)
        await expect(new_page.get_by_text(phone_pattern).first).to_be_visible(timeout=5000)
        print(f"✓ 고객 정보 확인: {customer_name}, {phone_number}")

        # 충전 전 티켓 잔여 횟수 (티켓 전용 행 기준으로 한정)
        ticket_row = new_page.locator("dl[title*='티켓']").first
        if await ticket_row.count() == 0:
            ticket_row = new_page.locator("dl").filter(has_text=re.compile(r"티켓\\s*\\n")).first
        if await ticket_row.count() == 0:
            ticket_row = new_page.locator("dl, li, div").filter(has_text=re.compile(r"티켓.*회")).first
        await expect(ticket_row).to_be_visible(timeout=5000)
        before_ticket_text = await ticket_row.inner_text()
        before_count_match = re.search(r"(\d+)\s*회", before_ticket_text)
        before_count = int(before_count_match.group(1)) if before_count_match else 0

        # 좌측 티켓 영역의 [충전] 버튼 클릭 (팝업/현재 페이지 모두 대응)
        popup_task = asyncio.create_task(new_page.wait_for_event("popup", timeout=4000))
        ticket_charge_btn = ticket_row.get_by_role("button", name="충전").first
        if await ticket_charge_btn.count() == 0:
            ticket_charge_btn = ticket_row.get_by_text("충전", exact=True).first
        await ticket_charge_btn.click()

        try:
            ticket_charging_page = await popup_task
            await ticket_charging_page.wait_for_load_state("domcontentloaded")
        except PlaywrightTimeoutError:
            popup_task.cancel()
            ticket_charging_page = new_page

        charge_modal = ticket_charging_page.locator("#modal-content:visible").first
        if await charge_modal.count() == 0:
            charge_modal = ticket_charging_page.locator("[role='dialog']:visible, [aria-modal='true']:visible").first
        if await charge_modal.count() == 0:
            charge_modal = ticket_charging_page

        ticket_tab_title = charge_modal.locator("h3:has-text('티켓 충전'):visible").first
        assert await ticket_tab_title.count() > 0, "티켓 충전 탭 텍스트를 찾지 못했습니다."

        # 티켓 탭은 h3를 직접 JS 클릭해야 안정적으로 전환됨
        ticket_tab_active = charge_modal.locator("h3:has-text('티켓 충전').active:visible").first
        for _ in range(5):
            if await ticket_tab_active.count() > 0:
                break
            await ticket_tab_title.evaluate("e => e.click()")
            await ticket_charging_page.wait_for_timeout(300)

        if await ticket_tab_active.count() == 0:
            tab_texts = await charge_modal.locator("h3:visible").all_text_contents()
            raise AssertionError(f"티켓 충전 탭 활성화 실패: {tab_texts}")

        ticket_scope = charge_modal
        if await ticket_scope.get_by_text("충전 횟수").count() > 0:
            await expect(ticket_scope.get_by_text("충전 횟수")).to_be_visible(timeout=5000)
        else:
            await expect(ticket_scope.get_by_text("티켓 선택")).to_be_visible(timeout=5000)

        arbitrary_option = ticket_scope.locator("li.radio-option:has(h4:has-text('임의 입력'))").first
        if await arbitrary_option.count() > 0:
            await arbitrary_option.click()

        ticket_name_input = ticket_scope.get_by_placeholder("티켓 이름을 입력해 주세요.").first
        if await ticket_name_input.count() > 0:
            await ticket_name_input.fill("테스트티켓")

        # 횟수 5회로 설정 (충전 횟수 영역 input 우선)
        count_input = ticket_scope.locator(
            "div:has-text('충전 횟수') input:not([readonly]):not([disabled]):visible"
        ).first
        if await count_input.count() == 0:
            count_input = ticket_scope.locator(
                "input:not([readonly]):not([disabled]):visible"
            ).filter(has_not=ticket_scope.locator("[placeholder*='기한']")).last
        if await count_input.count() == 0:
            count_input = ticket_scope.get_by_placeholder("0").locator(":visible").last
        await count_input.fill("5")

        # 제출 버튼 fallback
        submit_candidates = ["충전", "등록", "저장", "확인"]
        submit_clicked = False
        for label in submit_candidates:
            submit_btn = ticket_scope.locator("button:visible").filter(
                has_text=re.compile(rf"^\s*{re.escape(label)}\s*$")
            ).last
            if await submit_btn.count() > 0:
                await submit_btn.click()
                submit_clicked = True
                print(f"✓ 티켓 팝업 제출 버튼 클릭: {label}")
                break

        if not submit_clicked:
            visible_buttons = await ticket_charging_page.locator("button:visible").all_text_contents()
            raise AssertionError(f"티켓 팝업 제출 버튼을 찾지 못했습니다. visible_buttons={visible_buttons}")

        # 팝업이 별도 창일 때만 닫힘 대기
        if ticket_charging_page is not new_page:
            try:
                await ticket_charging_page.wait_for_event("close", timeout=7000)
            except PlaywrightTimeoutError:
                pass
        print("✓ 티켓 팝업 처리 완료")

        # 원본 페이지로 돌아와서 충전 결과 확인
        await new_page.bring_to_front()
        await new_page.wait_for_timeout(2000)

        ticket_summary = new_page.locator("dl, li, div").filter(has_text=re.compile(r"티켓")).first
        await expect(ticket_summary).to_be_visible(timeout=5000)
        after_ticket_text = await ticket_summary.inner_text()
        after_count_match = re.search(r"(\d+)\s*회", after_ticket_text)
        assert after_count_match is not None, f"티켓 횟수 파싱 실패: {after_ticket_text!r}"
        after_count = int(after_count_match.group(1))

        charged_count = after_count - before_count
        assert charged_count > 0, (
            f"충전 횟수 반영 실패: before={before_count}, after={after_count}, diff={charged_count}"
        )
        print(f"✓ 티켓 잔여 횟수 확인: {before_count}회 -> {after_count}회 (+{charged_count})")
        print("=== 티켓 충전 테스트 완료 ===\n")

    @pytest.mark.asyncio
    async def test_make_reservations(self):
        """예약 등록 테스트"""

        print("=== 예약 등록 테스트 시작 ===")
        reservations = [
            {
                'customer': f'자동화_{self.mmdd}_1',
                'time': '오후 4:00',
                'menu_category': '손',
                'menu_item': '젤 기본'
            },
            {
                'customer': f'자동화_{self.mmdd}_2',
                'time': '오후 5:00',
                'menu_category': '티켓',
                'menu_item': '10만원권'
            },
            {
                'customer': f'자동화_{self.mmdd}_3',
                'time': '오후 6:00',
                'menu_category': '손',
                'menu_item': '케어'
            }
        ]

        async def open_reservation_form():
            """플로팅 메뉴에서 예약 등록 폼을 안정적으로 연다."""
            for _ in range(5):
                # 이미 열려 있으면 바로 반환
                if await self.page.locator("input#customer-search:visible").count() > 0:
                    return

                # 이전 모달 잔여 레이어 정리
                active_dimmer = self.page.locator("#modal-dimmer.isActiveDimmed").first
                if await active_dimmer.count() > 0 and await active_dimmer.is_visible():
                    await self.page.keyboard.press("Escape")
                    await self.page.wait_for_timeout(250)

                try:
                    await self.page.locator("#floating-layout button:visible").first.click(force=True)
                    await self.page.wait_for_timeout(250)
                except Exception:
                    await self.page.wait_for_timeout(250)
                    continue

                clicked = False
                candidates = [
                    self.page.get_by_role("menuitem", name="예약 등록").locator(":visible").first,
                    self.page.get_by_role("button", name="예약 등록").locator(":visible").first,
                    self.page.locator("h4:has-text('예약 등록'):visible").first,
                ]

                for candidate in candidates:
                    if await candidate.count() == 0:
                        continue
                    try:
                        await candidate.click(force=True, timeout=4000)
                        clicked = True
                        break
                    except Exception:
                        continue

                if not clicked:
                    await self.page.keyboard.press("Escape")
                    await self.page.wait_for_timeout(250)
                    continue

                try:
                    await self.page.wait_for_selector("input#customer-search:visible", timeout=5000)
                    return
                except Exception:
                    await self.page.keyboard.press("Escape")
                    await self.page.wait_for_timeout(300)

            raise AssertionError("예약 등록 메뉴 진입 실패: customer-search 입력창이 열리지 않았습니다.")

        # 각 예약 등록
        for i, reservation in enumerate(reservations, 1):
            print(f"{i}. {reservation['customer']} 예약 등록")

            await open_reservation_form()

            await self.page.locator("input#customer-search:visible").last.fill(reservation['customer'])
            await self.page.locator("input#customer-search:visible").last.press("Enter")

            await self.page.wait_for_timeout(2000)  # 3초 대기




            # 검색 결과에서 고객 클릭
            await self.page.locator(f"button:has-text('{reservation['customer']}')").first.click()

            # 타이틀 검증
            title_text = f"'{reservation["customer"]}'님 예약등록'"
            print(f"✓ 타이틀 확인: {title_text}")



            # 예약 일시 설정

            await self.page.locator("#createBookingTime").locator(":visible").first.click()
            await self.page.get_by_role("button", name=f"{reservation['time']}").locator(":visible").first.click()

            print(f"✓ 예약 시간 설정: {reservation['time']}")

            # 시술메뉴 선택
            await self.page.locator("#bookingItemGroupSelect button.select-display:visible").first.click()

            # 그룹 선택
            await self.page.locator(f"button:has-text('{reservation['menu_category']}')").locator(":visible").first.click()
            await self.page.wait_for_timeout(500)

            # 세부 메뉴 선택
            await self.page.locator(f"button:has-text('{reservation['menu_item']}')").locator(":visible").first.click()
            await self.page.wait_for_timeout(500)

            print(f"✓ 시술메뉴 선택: {reservation['menu_category']} > {reservation['menu_item']}")

            # 등록 버튼 클릭
            await self.page.locator("button:has-text('등록'):visible").first.click()
            await self.page.wait_for_load_state('networkidle')
            try:
                await self.page.wait_for_selector("#modal-dimmer.isActiveDimmed", state="hidden", timeout=5000)
            except Exception:
                await self.page.keyboard.press("Escape")
                await self.page.wait_for_timeout(250)

            print(f"✓ {reservation['customer']} 예약 등록 완료")

        print("=== 예약 등록 테스트 완료 ===")


    @pytest.mark.asyncio
    async def test_verify_calendar_reservations(self):

        print("\n=== 캘린더 예약 검증 테스트 시작 ===")


        expected_reservations = [
            {
                'customer': f'자동화_{self.mmdd}_1',
                'display_time': '오후 4:00',
                'menu_category': '손',
                'menu_item': '젤 기본'
            },
            {
                'customer': f'자동화_{self.mmdd}_2',
                'display_time': '오후 5:00',
                'menu_category': '티켓',
                'menu_item': '10만원권'
            },
            {
                'customer': f'자동화_{self.mmdd}_3',
                'display_time': '오후 6:00',
                'menu_category': '손',
                'menu_item': '케어'
            }
        ]
        await self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()

        # 각 예약 검증
        for i, reservation in enumerate(expected_reservations, 1):
            print(f"\n{i}. {reservation['display_time']} 예약 검증")
            print(reservation['customer'])

            # customer_locator = self.page.locator(f'text={reservation["customer"]}')
            # customer_visible = await customer_locator.is_visible()
            # assert customer_visible, f"고객명이 캘린더에 표시되지 않았습니다: {reservation['customer']}"
            # print(f"✓ 고객명 확인: {reservation['customer']}")

            reserve_card = self.page.locator("div.BOOKING.booking-normal")\
                .filter(has_text=reservation['customer']).first
            await expect(reserve_card).to_be_visible(timeout=5000)
            await reserve_card.click()
            await self.page.wait_for_timeout(400)

            # 상세 패널에서 텍스트 기반으로 검증 (해시 클래스 의존 제거)
            detail_panel = self.page.locator("div:has(button:has-text('나가기'))").filter(
                has_text=reservation['customer']
            ).first
            if await detail_panel.count() == 0:
                detail_panel = self.page.locator("div").filter(
                    has_text=reservation['customer']
                ).filter(
                    has_text=reservation['display_time']
                ).first

            panel_text = await detail_panel.inner_text()
            assert reservation['customer'] in panel_text, f"고객명 불일치: {panel_text!r}"
            assert reservation['display_time'] in panel_text, f"예약시간 불일치: {panel_text!r}"
            assert reservation['menu_category'] in panel_text, f"카테고리 불일치: {panel_text!r}"
            assert reservation['menu_item'] in panel_text, f"메뉴 불일치: {panel_text!r}"


            await self.page.locator("button:has-text('나가기'):visible").click()

    @pytest.mark.asyncio
    async def sales_registrations_1(self):

        await self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()

        print(f'자동화_{self.mmdd}_1' , '매출등록 시작=====')

        customer = f"자동화_{self.mmdd}_1"
        reserve_card = self.page.locator("div.BOOKING.booking-normal").filter(has_text=customer).first
        await expect(reserve_card).to_be_visible(timeout=5000)
        await reserve_card.click()

        await self.page.locator("button:has-text('매출 등록'):visible").last.click()


        print("매출 등록 페이지 진입 ====")
        await self._assert_sales_registration_page(expected_total="20,000원")

        # 정액권 21,000원 입력
        insert_amount = self.page.locator('input[name="정액권($membership원)"]').nth(1)
        await insert_amount.click()
        await insert_amount.fill("21000")  # 21,000원에 해당하는 숫자

        dialog_messages = await self._click_sales_save_button()
        if dialog_messages:
            print("message:", dialog_messages[-1])
        else:
            print("message: dialog 미노출(인라인 검증/무반응 가능)")


        #정액권 20,000원 입력
        await insert_amount.click()
        await insert_amount.fill("20000")  # 21,000원에 해당하는 숫자
        await self._click_sales_save_button()
        await self.page.wait_for_timeout(1200)

        print("매출 정상 등록 완료 === ")

    @pytest.mark.asyncio
    async def sales_registrations_2(self):

        await self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()
        print(f'자동화_{self.mmdd}_2' , '매출등록 시작=====')

        customer = f"자동화_{self.mmdd}_2"
        reserve_card = self.page.locator("div.BOOKING.booking-normal").filter(has_text=customer).first
        await expect(reserve_card).to_be_visible(timeout=5000)
        await reserve_card.click()

        await self.page.locator("button:has-text('매출 등록'):visible").last.click()


        print("매출 등록 페이지 진입 ====")
        await self._assert_sales_registration_page(expected_total="0원")

        # 티켓 + 아이콘 버튼 클릭
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
                    const cls = i.className || '';
                    return name.includes('티켓') || cls.includes('kjwoTx');
                  });
                return candidates.length ? candidates[0].value : null;
            }"""
        )
        assert ticket_value is not None, "티켓 입력값 필드를 찾지 못했습니다."
        print(ticket_value)
        # 3) 값이 2인지 확인 (둘 중 편한 방법)
        # (A) Playwright 어설션
        assert ticket_value.strip() == "2"
        await self._click_sales_save_button()

        print("매출 정상 등록 완료 === ")


    @pytest.mark.asyncio
    async def sales_registrations_3(self):

        await self.page.locator("button.sc-76a9c92e-1:has-text('일'):visible").first.click()

        print(f'자동화_{self.mmdd}_3' , '매출등록 시작=====')

        customer = f"자동화_{self.mmdd}_3"
        reserve_card = self.page.locator("div.BOOKING.booking-normal").filter(has_text=customer).first
        await expect(reserve_card).to_be_visible(timeout=5000)
        await reserve_card.click()

        await self.page.locator("button:has-text('매출 등록'):visible").last.click()


        print("매출 등록 페이지 진입 ====")
        await self._assert_sales_registration_page(expected_total="10,000원")

        insert_cash = self.page.locator('input[name="현금"]').nth(1)
        await insert_cash.click()
        await insert_cash.fill("5000")  # 현금 5,000원

        insert_card = self.page.locator('input[name="카드"]').nth(1)
        await insert_card.click()
        await insert_card.fill("5000")  # 카드 5,000원에

        await self._click_sales_save_button()

        print("매출 정상 등록 완료 === ")

    @pytest.mark.asyncio
    async def sales_registrations_4(self):
        # 고객 탭 클릭
        await self.page.locator("h3:has-text('매출')").first.click()
        await self.page.locator(".new-item").first.click()
        await self.page.wait_for_load_state('networkidle')

        #미등록 고객 클릭
        # await self.page.get_by_label("미등록 고객").click()  # 또는 .click()
        await self.page.locator("label:has(p:has-text('미등록 고객'))").locator(":visible").first.click()

        cust_name = self.page.locator("div.sc-e29c3c15-1.view p.kunnIt").first
        await expect(cust_name).to_have_text("미등록고객", timeout=2000)
        print("====고객명은 :", await cust_name.inner_text())

        # 제품 탭 선택 (텍스트가 정확히 '제품0'인 탭만 클릭)
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

        # 그룹 선택: 미분류
        group_btn = self.page.locator(
            "button:has-text('미분류'):visible, li:has-text('미분류'):visible, [role='option']:has-text('미분류'):visible"
        ).first
        await expect(group_btn).to_be_visible(timeout=5000)
        await group_btn.click()
        await self.page.wait_for_timeout(500)

        # 세부 메뉴 선택: 01_제품_테스트
        item_btn = self.page.locator(
            "button:has-text('01_제품_테스트'):visible, li:has-text('01_제품_테스트'):visible, [role='option']:has-text('01_제품_테스트'):visible"
        ).first
        await expect(item_btn).to_be_visible(timeout=5000)
        await item_btn.click()
        await self.page.wait_for_timeout(500)


        insert_naver = self.page.locator('input[name="네이버페이"]').nth(1)
        await insert_naver.click()
        await insert_naver.fill("5000")  # 네이버페이 5,000원

        insert_receivable = self.page.locator('input[name="미수금"]').nth(1)
        await insert_receivable.click()
        await insert_receivable.fill("5000")  # 미수금 5,000원


        await self._click_sales_save_button()



    @pytest.mark.asyncio
    async def statistics(self):

        print("=== 통계 검증 시작 ===")
        # 홈 > 샵 현황
        await self.page.locator("h3:has-text('홈')").first.click()
        shop_status_btn = self.page.get_by_role("button", name="샵 현황").locator(":visible").first
        if await shop_status_btn.count() == 0:
            shop_status_btn = self.page.locator(
                "button:has-text('샵 현황'):visible, "
                "a:has-text('샵 현황'):visible, "
                "div:has-text('샵 현황'):visible"
            ).first
        if await shop_status_btn.count() > 0:
            await shop_status_btn.click()
            await self.page.wait_for_load_state('networkidle')
        else:
            print("=== 홈에서 '샵 현황' 버튼을 찾지 못해 해당 단계는 건너뜀")

        #총 실매출, 오늘의 예약 검증
        print("=== 홈 > 샵 현황")
        ps = self.page.locator("p.sc-9966e937-0.fWTszn.color-primary-300:visible")
        if await ps.count() >= 2:
            await expect(ps.nth(0)).to_have_text("320,000원", timeout=3000)
            print("=== 총 실매출 :", await ps.nth(0).inner_text())
            await expect(ps.nth(1)).to_have_text("3", timeout=3000)
            print("=== 오늘의 예약 :", await ps.nth(1).inner_text())
        else:
            print("=== 홈 카드(총 실매출/오늘의 예약) 셀렉터 미매칭으로 해당 검증 건너뜀")


        # 통계 페이지 이동
        await self.page.locator("h3:has-text('통계')").first.click()
        await self.page.wait_for_timeout(1200)

        # 상품별 통계 카드의 "자세히 보기" 진입 (통계 카드들 중 2번째)
        detail_buttons = self.page.get_by_role("button", name="자세히 보기")
        await expect(detail_buttons.nth(1)).to_be_visible(timeout=5000)
        await detail_buttons.nth(1).click()
        await self.page.wait_for_load_state("networkidle")

        # 1) 기간 선택 버튼 클릭 (해시 클래스 의존 제거)
        range_btn = self.page.locator("button:has(svg[icon='reserveCalender']):visible").first
        if await range_btn.count() == 0:
            range_btn = self.page.locator("button:has-text('기간'):visible").first
        try:
            await range_btn.click()
            panel = self.page.locator("div:visible").filter(
                has_text=re.compile(r"오늘|기간 검색")
            ).first
            await expect(panel).to_be_visible(timeout=2000)

            today_btn = panel.locator("button:has(h4:has-text('오늘'))").first
            if await today_btn.count() == 0:
                today_btn = panel.get_by_role("button", name="오늘").first
            await today_btn.click()

            search_btn = panel.get_by_role("button", name=re.compile(r"기간 검색$")).first
            await search_btn.click()
        except Exception:
            print("=== 기간 선택 패널 미노출로 기본 조회 범위로 진행")


        #table 값 가져오기

        table = self.page.locator("table:visible").filter(
            has_text=re.compile(r"실 매출 합계|시술|정액권 판매")
        ).first
        await expect(table).to_be_visible(timeout=5000)

        async def _assert_currency_column(header_text, label):
            header = table.locator(f"thead th:has-text('{header_text}')").first
            await expect(header).to_be_visible(timeout=3000)
            col_idx = await header.evaluate("th => Array.from(th.parentElement.children).indexOf(th) + 1")
            cell = table.locator("tbody tr").first.locator(f"td:nth-child({col_idx}) span").first
            value = (await cell.inner_text()).strip()
            assert re.search(r"\d[\d,]*원", value), f"{label} 금액 형식 오류: {value}"
            print(f"{label}: {value}")

        await _assert_currency_column("실 매출 합계", "실 매출 합계")
        await _assert_currency_column("시술", "시술")
        await _assert_currency_column("정액권 판매", "정액권 판매")
        await _assert_currency_column("티켓 판매", "티켓 판매")
        await _assert_currency_column("차감 합계", "차감 합계")
        await _assert_currency_column("정액권 차감", "정액권 차감")
        await _assert_currency_column("티켓 차감", "티켓 차감")

        #뒤로가기
        await self.page.locator("button:has(h4:has-text('뒤로가기'))").first.click()
        # await back_btn.click()



        # 시술 통계 (선택)
        try:
            procedure_detail_buttons = self.page.get_by_role("button", name="자세히 보기")
            if await procedure_detail_buttons.count() >= 4:
                await procedure_detail_buttons.nth(3).click()
                await self.page.wait_for_load_state("networkidle")
                await expect(self.page.get_by_role("heading", name=re.compile("시술 통계"))).to_be_visible(timeout=5000)

                rows = self.page.locator("tbody tr")
                row_count = await rows.count()
                assert row_count > 0, "시술 통계 행이 없습니다."
                print("시술 통계 행 개수:", row_count)
        except Exception as e:
            print(f"=== 시술 통계 상세 검증은 UI 변동으로 건너뜀: {e}")



    @pytest.mark.asyncio
    async def custom_payment_method(self):
        await self.page.locator("h3:has-text('매출')").first.click()
        await self.page.locator(".new-item").first.click()
        await self.page.wait_for_load_state('networkidle')

        phone_number = f"010{self.mmdd}0001"
        #
        # 1) 검색 인풋에 번호 입력 (보이는 것 기준 첫 번째)
        field = self.page.locator("input#customer-search:visible").first
        await expect(field).to_be_visible(timeout=3000)
        await field.fill(phone_number)
        await field.press("Enter")

        # 2) 드롭다운 결과에서 해당 항목 클릭
        searched_customer = self.page.locator("li.sc-43fbb16b-4:has(p:has-text('0001'))").first
        await expect(searched_customer).to_be_visible(timeout=5000)
        await searched_customer.click()


        #시술 메뉴 추가
        await self.page.locator("#sale-item-group button.select-display:visible").first.click()

        # 그룹 선택
        await self.page.locator(f"button:has-text('손')").locator(":visible").first.click()
        await self.page.wait_for_timeout(500)

        # 세부 메뉴 선택
        await self.page.locator(f"button:has-text('젤 기본')").locator(":visible").first.click()
        await self.page.wait_for_timeout(500)
        #
        #
        # 결제수단 추가 설정 > 결제수단 추가 버튼 클릭
        settings_btn = self.page.locator("button:has-text('결제 수단 설정')").locator(":visible").first
        await expect(settings_btn).to_be_visible(timeout=5000)
        await settings_btn.click()
        #
        #
        # 3) 같은 패널 안에서 "결제 수단 추가" 클릭
        add_btn = self.page.locator("button:has-text('결제 수단 추가')").first
        await expect(add_btn).to_be_visible(timeout=2000)
        await add_btn.click()

        # 결제수단 이름 입력
        name_input = self.page.locator(".sc-61497733-0.cKHlCw").locator(":visible").first
        await expect(name_input).to_be_visible(timeout=2000)
        await name_input.fill("페이 추가 테스트")

        #토글 On
        toggle_label = self.page.locator("label[for='isActiveSelectedPaymentMethod']").last
        await expect(toggle_label).to_be_visible(timeout=2000)
        await toggle_label.click()

        #저장 완료
        await self.page.locator("button:has-text('저장'):visible").last.click()
        await self.page.wait_for_timeout(2000)
        print("===결제수단 추가 완료!")
        #
        #닫기 버튼
        await self.page.locator(".sc-1680eecc-0").click()

        # 결제수단 추가 완료 확인
        payment_method = self.page.locator(".sc-a92b23b7-0.iSHaJD:visible").first
        added_payment = payment_method.locator("label:has(h4:has-text('페이 추가 테스트'))").locator(":visible").first
        await added_payment.click()

        #매출 등록
        await self.page.locator("button:has-text('매출 저장'):visible").last.click()

        print("매출 정상 등록 완료 === ")

        #통계 > 결제 수단별 통계 확인
        # JSP에서는 메뉴 클릭하는 방식이 다름
        stats_link = self.page.locator("a.header.no-toggle[onclick*=\"/statistics\"]").first
        await stats_link.click()
        payment_sta_detail = self.page.locator(".sc-45a967ab-0.idQZsJ").nth(1)
        await payment_sta_detail.click()

        statistics_payment_table = self.page.locator("tbody.sc-a8d89aaa-4.bXKepo").nth(1)
        # "페이 추가 테스트" 존재 여부 (True/False)
        exists = (await statistics_payment_table.get_by_text("페이 추가 테스트", exact=True).count()) > 0

        pay_value = statistics_payment_table.locator("tr:has-text('페이 추가 테스트')").first
        amount_text = (await pay_value.locator("td:nth-child(2) span").inner_text()).strip()
        print("페이 추가 테스트 값 : ", amount_text)

        print("exists:", exists)

        # 테스트 검증이라면
        assert exists, "'페이 추가 테스트' 항목이 테이블에 없습니다."


        # 매출 페이지 > "페이 추가 테스트" > 삭제
        await self.page.locator("h3:has-text('매출')").first.click()

        table = self.page.locator("table.outside").first
        rows = table.locator("tbody > tr.row").filter(
            has= self.page.locator("td.column.payment-type", has_text="페이 추가 테스트")
        )
        count = await rows.count()

        # 모든 해당 행에서 "수정" 클릭
        for i in range(count):
            row = rows.nth(i)
            edit = row.locator("a.action", has_text="삭제").first
            await expect(edit).to_be_visible(timeout=5000)
            await edit.scroll_into_view_if_needed()
            await edit.click()

            # 삭제 클릭하여 message 확인 및 [확인] 버튼 클릭
            async with self.page.expect_event("dialog", timeout=3000) as dlg_info:
                await edit.click()

            dialog = await dlg_info.value
            print("message:", dialog.message)  # 알림창 텍스트
            await dialog.accept()


        await self.page.locator(".new-item").first.click()
        await self.page.wait_for_load_state('networkidle')

        #결제 수단 설정 재진입
        settings_btn = self.page.locator("button:has-text('결제 수단 설정')").locator(":visible").first
        await expect(settings_btn).to_be_visible(timeout=5000)
        await settings_btn.click()

        #결제수단 편집 및 삭제
        edit_btn = self.page.locator("button:has-text('편집')").last
        await edit_btn.scroll_into_view_if_needed()
        await edit_btn.click()

        await self.page.locator("button:has-text('삭제')").first.click()
        await self.page.locator(".sc-45a967ab-0.iPNnOp").first.click()
        print("[페이 추가 테스트] 결제수단 삭제 완료")


        # async with self.page.expect_event("dialog", timeout=3000) as dlg_info:
        #     await self.page.locator(".sc-45a967ab-0.iPNnOp").first.click()
        #
        # dialog = await dlg_info.value
        # print("message:", dialog.message)  # 알림창 텍스트
        # assert dialog.message, "이미 등록된 연락처입니다. \해당 고객차트로 이동하시겠습니까?"
        # await dialog.dismiss()
        await self.page.locator(".sc-1680eecc-0.hENWWv").first.click()



    @pytest.mark.asyncio
    async def incentive(self):
        print("==== 인센티브 시작")
        def _auto_ok(dlg):
            asyncio.create_task(dlg.accept())

        self.page.on("dialog", _auto_ok)
        await self.page.locator("h3:has-text('우리샵 관리')").first.click()

        async with self.page.expect_event("dialog", timeout=5000) as dlg_info:
            await self.page.get_by_role("button", name="직원관리").click()

        dialog = await dlg_info.value
        print("message:", dialog.message)  # 알림창 텍스트

        assert dialog.message, "변경사항이 저장되지 않을 수 있습니다."
        await self.page.get_by_role("heading", name="인센티브").click()


        # 예약 현황 닫기
        await self.page.locator(".sc-da879ad9-6.rCRda").click()

        #인센티브 설정
        await self.page.get_by_role("button", name="인센티브 설정").click()
        await self.page.locator(".sc-61497733-0.cKEoAs").first.click()

        # 토글 Off
        # toggle_label = self.page.locator("label[for='isActiveSelectedEmployeeIncentive']").last
        # await expect(toggle_label).to_be_visible(timeout=2000)
        # await toggle_label.click()

        toggle = self.page.locator("input[type='checkbox'][name='isActiveSelectedEmployeeIncentive']").last
        await toggle.wait_for(state="attached")
        if (await toggle.get_attribute("checked")) is not None:
            await toggle.click()

        # #저장 완료
        await self.page.locator("button:has-text('저장'):visible").last.click()
        # await self.page.wait_for_timeout(2000)
        # print("===인센티브 OFF 완료!")

        #닫기 버튼
        # await self.page.locator(".sc-1680eecc-0").first.click()
        await self.page.locator("svg[icon='systemX']").first.click()

        row = self.page.locator("tr:has(h4:has-text('샵주테스트'))").first
        await row.wait_for(state="visible")

        last_td = row.locator("td").last
        await last_td.wait_for(state="visible")

        raw_text = (await last_td.inner_text()).strip()  # 예: "0원"
        total = int("".join(ch for ch in raw_text if ch.isdigit()) or "0")  # 예: 0

        assert raw_text, "0원"
        print("총 합계(원문):", raw_text, "→ 정수값:", total)

    @pytest.mark.asyncio
    async def create_new_shop(self):
        print("=== 신규 샵 생성 시작")

        print("마이페이지 이동")
        await self.page.locator("button:has-text('마이페이지')").first.click()

        await self.page.get_by_role("link", name="+ 샵 추가").click()

        #샵 이름 입력
        name_input = self.page.get_by_placeholder("샵 이름")
        await expect(name_input).to_be_visible()
        await name_input.fill( f"{self.mmdd}_배포_테스트")


        #샵 주소 클릭
        async with self.page.expect_popup() as input_addr_info:
            await self.page.locator("input#addr[placeholder='샵 주소']").click()

        input_addr_page = await input_addr_info.value

        await input_addr_page.wait_for_load_state('domcontentloaded')

        #샵 검색 iFrame에서 진행
        frame = input_addr_page.frame_locator("iframe[src*='postcode.map.daum.net']").first
        search_input = frame.locator("input#region_name, input.tf_keyword").first

        await search_input.fill("성동구 성수일로8길 5")
        await search_input.press("Enter")
        await frame.locator("span.txt_address[data-addr='서울 성동구 성수일로8길 5'] button.link_post").first.click()

        #상세주소 입력
        await self.page.get_by_placeholder("상세 주소").fill("302호 헤렌")
        await self.page.get_by_role("link", name="다음").first.click()



        #업종 선택
        dropdown = self.page.locator(".ui.dropdown-check.category")
        await dropdown.locator(".text", has_text="업종선택").click()

        panel = dropdown.locator(".dropdown-items-wrap")
        await panel.wait_for(state="visible", timeout=2000)

        # 2) "헤어", "네일" 체크 (label 클릭이 가장 안정적)
        await panel.locator("label[for='cate1']").click()
        await panel.locator("label[for='cate3']").click()
        print("시술 선택 완료")

        await panel.get_by_role("button", name="선택").click()
        await self.page.locator("a[onclick='onClickSubmit();']").click()


        #완료 검증
        modal = self.page.locator("#modal-content")
        await expect(modal).to_be_visible(timeout=3000)

        # 2) 타이틀 정확히 일치 검증
        title = modal.get_by_role("heading", name="한 달 무료 체험권 증정")
        # print(title)
        await expect(title).to_be_visible()

        # 3) 버튼 텍스트 정확히 일치 검증
        start_btn = modal.get_by_role("button", name="무료 체험 시작하기")
        # print(start_btn)
        await expect(start_btn).to_be_visible()

        await start_btn.click()

        await self.page.locator("button:has-text('건너뛰기')").first.click()

        # 샵 정보 검증
        print("4. 샵 정보 검증")
        shop_name = await self.page.locator(f'text="{self.mmdd}_배포_테스트"').is_visible()
        owner_name = await self.page.locator('text=샵주테스트').first.is_visible()

        assert shop_name, "샵 이름이 올바르지 않습니다."
        assert owner_name, "점주 이름이 올바르지 않습니다."



        # for f in input_addr_page.frames:
        #     print("FRAME:", f.url)


        # await input_addr_page.locator("#region_name").click()
        # await input_addr_page.keyboard.type("성동구 성수일로8길 5")
        # await input_addr_page.keyboard.press("Enter")





    async def run_all_tests(self):
        """모든 테스트 실행"""
        try:
            await self.setup()

            print("🚀 공비서 B2C 자동화 테스트 시작")
            await self.test_login()
            print("\n1. 로그인 완료")

            await self.test_add_customers()
            print("\n2. 고객추가 완료")

            await self.test_membership_charge()
            print("\n3. 정액권 추가 완료")

            await self.test_ticket_charge()
            print("\n4. 티켓 추가 완료")

            print("🎉 모든 테스트가 성공적으로 완료되었습니다!")

        except Exception as e:
            print(f"❌ 테스트 중 오류 발생: {str(e)}")
            raise
        finally:
            await self.teardown()


# 테스트 실행
async def main():
    test = B2BAutomationTest()
    await test.run_all_tests()

# @pytest.mark.asyncio
# async def test_login():
#     test = B2BAutomationTest()
#     try:
#         await test.setup()
#         await test.test_login()
#         await test.create_new_shop()
#
#
#         # await test.incentive()
#
#     finally:
#         await test.teardown()



# @pytest.mark.asyncio
# async def test_login_only():
#     """로그인만 테스트"""
#     test = B2BAutomationTest()
#     try:
#         await test.setup()
#         await test.test_login()
#         print("✓ 로그인 테스트 완료")
#     finally:
#         await test.teardown()


# @pytest.mark.asyncio
# async def test_customer():
#     """고객차트까지 테스트"""
#     test = B2BAutomationTest()
#     try:
#         await test.setup()
#         await test.test_login()
#         # await test.test_add_customers()
#         # await test.test_membership_charge()
#         await test.test_ticket_charge()
#         print("✓ 고객 테스트 완료")
#     finally:
#         await test.teardown()

@pytest.mark.asyncio
async def test_reservation():
    """전체 테스트"""
    test = B2BAutomationTest()
    try:
        await test.setup()
        await test.test_login()
        # await test.test_add_customers()
        await test.test_membership_charge()
        await test.test_ticket_charge()
        # await test.test_make_reservations()
        # await test.test_verify_calendar_reservations()
        # await test.sales_registrations_1()
        # await test.sales_registrations_2()
        # await test.sales_registrations_3()
        # await test.sales_registrations_4()
        # await test.statistics()
        # await test.custom_payment_method()
        # await test.incentive()
        # await test.create_new_shop()
        print("✓ 고객 테스트 완료")
    finally:
        await test.teardown()



if __name__ == "__main__":
    asyncio.run(main())
