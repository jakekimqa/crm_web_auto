"""정액권/티켓 충전, 패밀리 공유"""

import asyncio
import re

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import expect


class MembershipMixin:
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

        # 정액권 선택 드롭다운 열기
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

        # 페이지 reload하여 최신 금액 반영
        await detail_page.reload(wait_until="networkidle")

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
            # 패밀리 추가하기 버튼
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
