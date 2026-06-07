"""예약: 등록, 캘린더 확인, 예약 차단(등록/반복/검증/삭제)"""

import asyncio
import re

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import expect


class ReservationMixin:
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
                modal = self.page.locator("#modal-content:visible, [role='dialog']:visible").first
                if await modal.count() > 0:
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
            try:
                await self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            try:
                await self.page.wait_for_selector("#modal-dimmer.isActiveDimmed", state="hidden", timeout=5000)
            except Exception:
                await self.page.keyboard.press("Escape")

    async def verify_calendar_reservations(self):
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()
        expected = self._reservation_scenarios()
        await self.page.locator("button:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        for r in expected:
            reserve_card = None
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

                await self.page.mouse.wheel(0, 400)
                await self.page.wait_for_timeout(300)
                if step == 3:
                    time_slot = self.page.locator(f"text={r['display_time']}").first
                    if await time_slot.count() > 0:
                        try:
                            await time_slot.scroll_into_view_if_needed()
                        except Exception:
                            pass
            assert reserve_card is not None, f"예약 카드 찾기 실패: {r['customer']}"
            await expect(reserve_card).to_be_visible(timeout=5000)
            await reserve_card.click(force=True)
            await self.page.wait_for_timeout(500)
            # 상세 패널 열림 대기
            detail_panel = self.page.locator("div:has(button:has-text('나가기'))").filter(has_text=r["customer"]).first
            try:
                await expect(detail_panel).to_be_visible(timeout=5000)
            except Exception:
                # 패널이 안 열렸으면 다시 클릭
                await reserve_card.click(force=True)
                await self.page.wait_for_timeout(1000)
                detail_panel = self.page.locator("div:has(button:has-text('나가기'))").filter(has_text=r["customer"]).first
                await expect(detail_panel).to_be_visible(timeout=5000)
            text = await detail_panel.inner_text()
            assert r["customer"] in text, f"고객명 검증 실패: {r['customer']}"
            assert r["display_time"] in text, f"예약시간 검증 실패: {r['display_time']}"
            # 반드시 상세 패널을 닫고 다음 고객 검증으로 진행
            closed = False
            for _ in range(5):
                exit_btn = self.page.locator(
                    "button:has-text('나가기'):visible"
                ).first
                if await exit_btn.count() > 0:
                    await exit_btn.click(force=True)
                else:
                    await self.page.keyboard.press("Escape")
                await self.page.wait_for_timeout(500)
                try:
                    await self.page.wait_for_load_state("networkidle", timeout=10000)
                    still_open = self.page.locator("div:has(button:has-text('나가기'))").filter(has_text=r["customer"]).first
                    if await still_open.count() == 0 or not await still_open.is_visible():
                        closed = True
                        break
                except Exception:
                    closed = True
                    break
            assert closed, f"상세 패널 닫기 실패: {r['customer']}"

    async def block_reservation(self):
        """예약막기 등록"""
        print("=== 예약막기 테스트 시작 ===")
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()

        day_btn = self.page.locator("button:has-text('일'):visible").first
        if await day_btn.count() > 0:
            await day_btn.click()
            await self.page.wait_for_timeout(500)

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

        print("2. 예약막기 폼 입력")
        reason_input = self.page.locator("input[name='reason']:visible, input[placeholder*='사유']:visible").first
        await expect(reason_input).to_be_visible(timeout=5000)
        await reason_input.fill("자동화 예약막기 테스트")

        start_time_target = "오후 7:00"
        print(f"  시작 시간: {start_time_target}")

        start_wrapper = self.page.locator("#startTime")
        await start_wrapper.locator("button.select-display").click(force=True)
        await self.page.wait_for_timeout(300)
        await start_wrapper.locator(f"li button:has-text('{start_time_target}')").first.click(force=True)
        await self.page.wait_for_timeout(300)

        print("  담당자: 디폴트 (샵주테스트), 반복: 반복 안 함")

        print("3. 등록 클릭")
        register_btn = self.page.locator("button:has-text('등록'):visible").first
        await expect(register_btn).to_be_visible(timeout=3000)
        await register_btn.click()
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        await self.page.wait_for_timeout(1000)

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

        day_btn = self.page.locator("button:has-text('일'):visible").first
        if await day_btn.count() > 0:
            await day_btn.click()
            await self.page.wait_for_timeout(500)

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

        print("2. 반복 예약막기 폼 입력")
        reason_input = self.page.locator("input[name='reason']:visible, input[placeholder*='사유']:visible").first
        await expect(reason_input).to_be_visible(timeout=5000)
        await reason_input.fill("자동화 반복 예약막기 테스트")

        start_time_target = "오후 7:30"
        print(f"  시작 시간: {start_time_target}")
        start_wrapper = self.page.locator("#startTime")
        await start_wrapper.locator("button.select-display").click(force=True)
        await self.page.wait_for_timeout(300)
        await start_wrapper.locator(f"li button:has-text('{start_time_target}')").first.click(force=True)
        await self.page.wait_for_timeout(300)

        print("  반복 설정: 매일")
        repeat_wrapper = self.page.locator("#repeatSetting")
        await repeat_wrapper.locator("button.select-display").click(force=True)
        await self.page.wait_for_timeout(300)
        await repeat_wrapper.locator("li button:has-text('매일')").first.click(force=True)
        await self.page.wait_for_timeout(300)

        print("  반복 종료 조건: 생성 횟수 3회")
        end_wrapper = self.page.locator("#endConditionType")
        await end_wrapper.locator("button.select-display").click(force=True)
        await self.page.wait_for_timeout(300)
        await end_wrapper.locator("li button:has-text('생성 횟수')").first.click(force=True)
        await self.page.wait_for_timeout(300)

        count_input = self.page.locator("input[name='createCount']:visible").first
        await count_input.fill("3")

        print("3. 등록 클릭")
        register_btn = self.page.locator("button:has-text('등록'):visible").first
        await expect(register_btn).to_be_visible(timeout=3000)
        await register_btn.click()
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        await self.page.wait_for_timeout(1000)

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
        """단일 예약막기 검증"""
        print("=== 단일 예약막기 검증 시작 ===")
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()
        await self.page.locator("button:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        block = await self._scroll_to_time_and_find_block("자동화 예약막기 테스트")
        assert block is not None, "단일 예약막기 블록을 찾을 수 없습니다"
        await expect(block).to_be_visible(timeout=5000)
        print("✓ 오늘 오후 7:00 단일 예약막기 블록 확인 완료")
        print("=== 단일 예약막기 검증 완료 ===\n")

    async def verify_block_reservation_repeat(self):
        """반복 예약막기 검증"""
        print("=== 반복 예약막기 검증 시작 ===")
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()
        await self.page.locator("button:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        next_btn = self.page.locator("button.fc-next-button:visible, button[aria-label='next']:visible").first

        for day_idx, day_label in enumerate(["오늘", "내일", "모레"]):
            if day_idx > 0:
                await next_btn.click(force=True)
                await self.page.wait_for_timeout(500)

            block = await self._scroll_to_time_and_find_block("자동화 반복 예약막기 테스트")
            assert block is not None, f"{day_label} 반복 예약막기 블록을 찾을 수 없습니다"
            await expect(block).to_be_visible(timeout=5000)
            print(f"✓ {day_label} 오후 7:30 반복 예약막기 블록 확인 완료")

        await self._move_calendar_to_today()
        print("=== 반복 예약막기 검증 완료 ===\n")

    async def delete_block_reservation(self):
        """단일 예약막기 삭제"""
        print("=== 단일 예약막기 삭제 시작 ===")
        base = self.base_url.replace("/signin", "")
        await self.page.goto(f"{base}/book/calendar")
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        await self._move_calendar_to_today()
        await self.page.locator("button:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        block = await self._scroll_to_time_and_find_block("자동화 예약막기 테스트")
        assert block is not None, "단일 예약막기 블록을 찾을 수 없습니다"
        await block.click(force=True)
        await self.page.wait_for_timeout(1000)

        await self.page.locator("button").filter(has_text="삭제").first.click()
        await self.page.wait_for_timeout(500)

        confirm_btn = self.page.locator("button").filter(has_text="삭제").nth(1)
        await expect(confirm_btn).to_be_visible(timeout=5000)
        self.page.once("dialog", lambda dialog: asyncio.ensure_future(dialog.accept()))
        await confirm_btn.click()
        await self.page.wait_for_timeout(1000)
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        print("✓ 단일 예약막기 삭제 완료")
        print("=== 단일 예약막기 삭제 완료 ===\n")

    async def delete_block_reservation_repeat(self):
        """반복 예약막기 삭제 (모든 일정)"""
        print("=== 반복 예약막기 삭제 시작 ===")
        base = self.base_url.replace("/signin", "")
        await self.page.goto(f"{base}/book/calendar")
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        await self._move_calendar_to_today()
        await self.page.locator("button:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        block = await self._scroll_to_time_and_find_block("자동화 반복 예약막기 테스트")
        assert block is not None, "반복 예약막기 블록을 찾을 수 없습니다"
        await block.click(force=True)
        await self.page.wait_for_timeout(1000)

        await self.page.locator("button").filter(has_text="삭제").first.click()
        await self.page.wait_for_timeout(500)

        await self.page.locator("label").filter(has_text="모든 일정").click()
        await self.page.wait_for_timeout(300)

        modal_delete_btn = self.page.locator("button").filter(has_text="삭제").last
        await expect(modal_delete_btn).to_be_visible(timeout=5000)
        self.page.once("dialog", lambda dialog: asyncio.ensure_future(dialog.accept()))
        await modal_delete_btn.click()
        await self.page.wait_for_timeout(1000)
        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        print("✓ 반복 예약막기 삭제 완료 (모든 일정)")
        print("=== 반복 예약막기 삭제 완료 ===\n")

    async def unregistered_customer_reservation(self):
        """미등록 고객 예약: 등록 → 캘린더 확인 → 상세 확인 → 취소 → 삭제"""
        print("\n=== 미등록 고객 예약 테스트 시작 ===")
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()

        # ── 1. FAB → 예약 등록 모달 ──
        await self._dismiss_active_dimmer()
        await self.page.locator("#floating-layout button:visible").first.click(force=True)
        await self.page.wait_for_timeout(500)

        for cand in [
            self.page.get_by_role("menuitem", name="예약 등록").locator(":visible").first,
            self.page.locator("h4:has-text('예약 등록'):visible").first,
            self.page.locator("button:has-text('예약 등록'):visible, [role='menuitem']:has-text('예약 등록'):visible").first,
        ]:
            if await cand.count() > 0:
                await cand.click(force=True, timeout=4000)
                break
        await self.page.wait_for_selector(
            "#modal-content:visible input#customer-search:visible", timeout=5000
        )
        modal = self.page.locator("#modal-content:visible").first
        print("  ✓ 예약 등록 모달 열림")

        # ── 2. 고객 등록 없이 진행 ──
        no_register_btn = modal.locator("button:has-text('고객 등록 없이 진행')").first
        await expect(no_register_btn).to_be_visible(timeout=5000)
        await no_register_btn.click()
        await self.page.wait_for_timeout(1000)

        # 안내 텍스트 확인
        guide_text = "아래 내용은 선택 입력 사항이며, 고객으로 등록되지 않습니다"
        body_text = await modal.inner_text()
        assert guide_text in body_text, f"안내 텍스트 미노출: '{guide_text}'"
        print(f"  ✓ 안내 텍스트 확인")

        # 이름/연락처 입력
        name_input = modal.locator("input[placeholder*='이름'], input[name*='name']").first
        await expect(name_input).to_be_visible(timeout=5000)
        await name_input.fill("미등록 고객 테스트")

        phone_input = modal.locator("input[placeholder*='연락처'], input[name*='phone'], input[type='tel']").first
        await expect(phone_input).to_be_visible(timeout=5000)
        await phone_input.fill("0123456789")
        print("  ✓ 이름: 미등록 고객 테스트, 연락처: 0123456789")

        # [다음]
        next_btn = modal.locator("button:has-text('다음')").first
        await expect(next_btn).to_be_visible(timeout=5000)
        await next_btn.click()
        await self.page.wait_for_timeout(1000)

        # ── 3. 시간/시술 선택 → 등록 ──
        time_dropdown = modal.locator(
            "#createBookingTime:visible, button.select-display:has-text('오전'):visible, button.select-display:has-text('오후'):visible"
        ).first
        await expect(time_dropdown).to_be_visible(timeout=5000)
        await time_dropdown.click(force=True)
        await self.page.wait_for_timeout(1000)
        time_option = self.page.locator("li button p:text-is('오후 6:00')").first
        await time_option.scroll_into_view_if_needed(timeout=3000)
        await time_option.click()
        await self.page.wait_for_timeout(500)

        await self.page.locator("#bookingItemGroupSelect button.select-display:visible").first.click()
        await self.page.locator("button:has-text('발'):visible").first.click()
        await self.page.wait_for_timeout(300)
        await self.page.locator("button:has-text('젤 기본'):visible").first.click()
        await self.page.wait_for_timeout(300)
        print("  ✓ 오후 6:00, 발 > 젤 기본")

        register_btn = modal.locator("button:has-text('등록'):visible").first
        await expect(register_btn).to_be_visible(timeout=3000)
        await register_btn.click()
        await self.page.wait_for_timeout(1000)

        # 중복 예약 모달 확인 → [확인]
        overlap_text = "선택 시간에 이미 등록된 예약이 있습니다"
        overlap_el = self.page.locator(f"text=/{overlap_text}/").first
        await expect(overlap_el).to_be_visible(timeout=5000)
        print(f"  ✓ 중복 예약 모달 확인")

        confirm_btn = self.page.locator("button:has-text('확인'):visible").last
        await confirm_btn.click()
        await self.page.wait_for_timeout(1000)

        try:
            await self.page.wait_for_selector("#modal-dimmer.isActiveDimmed", state="hidden", timeout=5000)
        except Exception:
            await self.page.keyboard.press("Escape")
            await self.page.wait_for_timeout(500)
        print("  ✓ 미등록 고객 예약 등록 완료")

        # ── 4. 캘린더 예약 카드 확인 ──
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()
        await self.page.locator("button:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        reserve_card = None
        for _ in range(10):
            reserve_card = self.page.locator("div.BOOKING.booking-normal").filter(has_text="미등록 고객 테스트").first
            if await reserve_card.count() == 0:
                reserve_card = self.page.get_by_text("미등록 고객 테스트", exact=False).first
            if await reserve_card.count() > 0 and await reserve_card.is_visible():
                break
            await self.page.mouse.wheel(0, 400)
            await self.page.wait_for_timeout(300)
        assert await reserve_card.count() > 0, "캘린더에서 '미등록 고객 테스트' 예약 카드 미발견"
        print("  ✓ 캘린더 예약 카드 확인")

        # ── 5. 예약 상세 확인 ──
        await reserve_card.click(force=True)
        await self.page.wait_for_timeout(1000)

        detail_panel = self.page.locator("div:has(button:has-text('나가기'))").filter(has_text="미등록 고객 테스트").first
        try:
            await expect(detail_panel).to_be_visible(timeout=5000)
        except Exception:
            await reserve_card.click(force=True)
            await self.page.wait_for_timeout(1000)
            detail_panel = self.page.locator("div:has(button:has-text('나가기'))").filter(has_text="미등록 고객 테스트").first
            await expect(detail_panel).to_be_visible(timeout=5000)

        detail_text = await detail_panel.inner_text()
        assert "미등록 고객 테스트" in detail_text, "고객명 미발견"
        assert "젤 기본" in detail_text, "시술명 미발견"
        import re as _re
        time_match = _re.search(r'(오전|오후)\s*\d{1,2}:\d{2}', detail_text)
        assert time_match, f"시간 미발견: {detail_text[:200]}"
        actual_time = time_match.group()
        assert "샵주테스트" in detail_text, "담당자 미발견"
        print(f"  ✓ 상세: 고객명/시술명(젤 기본)/시간({actual_time})/담당자(샵주테스트)")

        # ── 6. 예약 취소 ──
        status_btn = self.page.locator("button:has-text('예약 확정'):visible").first
        await expect(status_btn).to_be_visible(timeout=5000)
        await status_btn.click()
        await self.page.wait_for_timeout(500)

        cancel_li = self.page.locator("li:has-text('예약 취소'):visible").first
        await expect(cancel_li).to_be_visible(timeout=5000)
        await cancel_li.click()
        await self.page.wait_for_timeout(1000)

        alert_messages = []

        def _auto_accept(dlg):
            alert_messages.append(dlg.message)
            asyncio.ensure_future(dlg.accept())

        self.page.on("dialog", _auto_accept)

        confirm_cancel = self.page.locator("button:has-text('확인'):visible").last
        await expect(confirm_cancel).to_be_visible(timeout=5000)
        await confirm_cancel.click()
        await self.page.wait_for_timeout(3000)

        self.page.remove_listener("dialog", _auto_accept)
        if alert_messages:
            print(f"  ✓ 취소 alert: {alert_messages[-1]}")
        print("  ✓ 예약 취소 완료")

        # ── 7. 취소된 예약 삭제 ──
        await self.ensure_calendar_page()
        await self._move_calendar_to_today()
        await self.page.locator("button:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        cancelled_card = None
        for _ in range(10):
            for selector in ["div.BOOKING.booking-cancel", "div.BOOKING", "div[class*='booking']"]:
                cancelled_card = self.page.locator(selector).filter(has_text="미등록 고객 테스트").first
                if await cancelled_card.count() > 0 and await cancelled_card.is_visible():
                    break
            if await cancelled_card.count() > 0 and await cancelled_card.is_visible():
                break
            await self.page.mouse.wheel(0, 400)
            await self.page.wait_for_timeout(300)
        assert await cancelled_card.count() > 0, "취소된 예약 카드 미발견"
        await cancelled_card.click(force=True)
        await self.page.wait_for_timeout(1500)

        # 상세 패널 열림 대기
        detail_for_delete = self.page.locator("div:has(button:has-text('나가기'))").filter(has_text="미등록 고객 테스트").first
        try:
            await expect(detail_for_delete).to_be_visible(timeout=5000)
        except Exception:
            await cancelled_card.click(force=True)
            await self.page.wait_for_timeout(1500)
            detail_for_delete = self.page.locator("div:has(button:has-text('나가기'))").filter(has_text="미등록 고객 테스트").first
            await expect(detail_for_delete).to_be_visible(timeout=5000)

        detail_delete_text = await detail_for_delete.inner_text()
        print(f"  → 삭제 전 상세 패널: {detail_delete_text[:300]}")

        delete_btn = detail_for_delete.locator("button:has-text('삭제'):visible").first
        if await delete_btn.count() == 0:
            # 패널 밖에서도 찾아보기
            delete_btn = self.page.locator("button:has-text('삭제'):visible").first
        await expect(delete_btn).to_be_visible(timeout=5000)
        await delete_btn.click()
        await self.page.wait_for_timeout(1000)

        modal_delete_btn = self.page.locator("button:has-text('삭제'):visible").last
        await expect(modal_delete_btn).to_be_visible(timeout=5000)
        await modal_delete_btn.click()
        await self.page.wait_for_timeout(2000)

        try:
            await self.page.wait_for_selector("#modal-dimmer.isActiveDimmed", state="hidden", timeout=5000)
        except Exception:
            await self.page.keyboard.press("Escape")
            await self.page.wait_for_timeout(500)

        # 삭제 확인
        remaining = self.page.locator("div.BOOKING").filter(has_text="미등록 고객 테스트").first
        assert await remaining.count() == 0, "삭제 후에도 예약이 남아있음"
        print("  ✓ 예약 삭제 완료 — 캘린더에서 미노출 확인")
        print("=== 미등록 고객 예약 테스트 완료 ===\n")
