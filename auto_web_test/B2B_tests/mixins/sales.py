"""매출등록: 1~5건, 사진 업로드, 커스텀 결제수단"""

import asyncio
import os
import re

from playwright.async_api import expect


class SalesMixin:
    async def _upload_sales_photos(self, photo_paths):
        """매출 메모/사진 > 사진 탭 → 0/10 아이콘 클릭 → 사진 모달 → 사진 추가 반복 → 저장"""
        photo_tab = self.page.locator("h4:has-text('사진')").first
        await photo_tab.click()
        await self.page.wait_for_timeout(500)

        # 사진 아이콘(0/10) 클릭 → 사진 모달 열기
        photo_icon = self.page.locator("div:has(> svg[icon='systemImage'])").first
        await photo_icon.click()
        await self.page.wait_for_timeout(500)

        # 사진 추가 버튼 클릭 → file chooser (multiple 지원)
        add_btn = self.page.locator("button:has-text('사진 추가'):visible").first
        async with self.page.expect_file_chooser() as fc_info:
            await add_btn.click()
        file_chooser = await fc_info.value
        await file_chooser.set_files(photo_paths)
        await self.page.wait_for_timeout(3000)
        print(f"  ✓ 사진 {len(photo_paths)}장 일괄 업로드")

        # 저장 버튼 클릭
        save_btn = self.page.locator("button:has-text('저장'):visible").first
        await expect(save_btn).to_be_enabled(timeout=30000)
        await save_btn.click()
        await self.page.wait_for_timeout(1000)

        print(f"  ✓ 사진 {len(photo_paths)}장 업로드 완료")

    async def verify_sales_photos(self, customer_name, expected_count):
        """캘린더 → 예약 카드 클릭 → 최근 매출 메모 → 썸네일 이미지 개수 확인"""
        await self.ensure_calendar_page()
        base = self.base_url.replace("/signin", "")
        if "/book/calendar" not in self.page.url:
            await self.page.goto(f"{base}/book/calendar", wait_until="networkidle")
        await self._move_calendar_to_today()
        await self.page.locator("button:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        # 예약 카드 찾기
        reserve_card = None
        for _ in range(8):
            reserve_card = self.page.locator("div.BOOKING.booking-normal").filter(has_text=customer_name).first
            if await reserve_card.count() == 0:
                reserve_card = self.page.get_by_text(customer_name, exact=True).first
            if await reserve_card.count() > 0 and await reserve_card.is_visible():
                break
            await self.page.mouse.wheel(0, 400)
            await self.page.wait_for_timeout(250)
        await expect(reserve_card).to_be_visible(timeout=5000)
        await reserve_card.click()
        await self.page.wait_for_timeout(1000)

        # 최근 매출 메모 클릭
        memo_btn = self.page.locator("p:has-text('최근 매출 메모')").first
        await expect(memo_btn).to_be_visible(timeout=5000)
        await memo_btn.click()
        await self.page.wait_for_timeout(1000)

        # 썸네일 이미지 개수 확인 (로딩 대기 포함)
        panel = self.page.locator("#booking-item-total-history")
        await expect(panel).to_be_visible(timeout=5000)

        # 이미지 로딩 대기 (최대 15초)
        for _ in range(30):
            photo_count = await panel.locator("img[alt^='최근 매출 메모 썸네일 이미지']").count()
            if photo_count >= expected_count:
                break
            await self.page.wait_for_timeout(500)

        # 이미지 완전 로딩 대기 (최대 20초)
        for _ in range(40):
            broken_count = await panel.evaluate(
                """(el) => {
                    const imgs = el.querySelectorAll("img[alt^='최근 매출 메모 썸네일 이미지']");
                    return [...imgs].filter(img => !img.complete || img.naturalWidth === 0).length;
                }"""
            )
            if broken_count == 0:
                break
            await self.page.wait_for_timeout(500)

        # 깨진 이미지 확인
        broken_count = await panel.evaluate(
            """(el) => {
                const imgs = el.querySelectorAll("img[alt^='최근 매출 메모 썸네일 이미지']");
                return [...imgs].filter(img => !img.complete || img.naturalWidth === 0).length;
            }"""
        )

        print(f"  ✓ {customer_name} 사진 개수: {photo_count}장 (깨진 이미지: {broken_count}장)")
        assert photo_count == expected_count, (
            f"{customer_name} 사진 개수 불일치: 기대 {expected_count}장, 실제 {photo_count}장"
        )
        assert broken_count == 0, f"{customer_name} 깨진 이미지 {broken_count}장 발견"

    async def delete_sales_photos(self, customer_name, delete_count):
        """캘린더 → 예약 카드 → 매출 수정 → 사진 삭제 → 저장"""
        await self.ensure_calendar_page()
        base = self.base_url.replace("/signin", "")
        if "/book/calendar" not in self.page.url:
            await self.page.goto(f"{base}/book/calendar", wait_until="networkidle")
        await self._move_calendar_to_today()
        await self.page.locator("button:has-text('일'):visible").first.click()
        await self.page.wait_for_timeout(500)

        # 예약 카드 찾기
        reserve_card = None
        for _ in range(8):
            reserve_card = self.page.locator("div.BOOKING.booking-normal").filter(has_text=customer_name).first
            if await reserve_card.count() == 0:
                reserve_card = self.page.get_by_text(customer_name, exact=True).first
            if await reserve_card.count() > 0 and await reserve_card.is_visible():
                break
            await self.page.mouse.wheel(0, 400)
            await self.page.wait_for_timeout(250)
        await expect(reserve_card).to_be_visible(timeout=5000)
        await reserve_card.click()
        await self.page.wait_for_timeout(1000)

        # 매출 수정 버튼 클릭
        edit_btn = self.page.locator("button:has-text('매출 수정'):visible").first
        await expect(edit_btn).to_be_visible(timeout=5000)
        await edit_btn.click()
        await self.page.wait_for_timeout(1000)

        # 사진 탭 클릭
        photo_tab = self.page.locator("h4:has-text('사진')").first
        await photo_tab.click()
        await self.page.wait_for_timeout(500)

        # 사진 아이콘 클릭 → 사진 모달 열기
        photo_icon = self.page.locator("div:has(> svg[icon='systemImage'])").first
        await photo_icon.click()
        await self.page.wait_for_timeout(500)

        # 이미지 삭제 반복
        for i in range(delete_count):
            delete_btn = self.page.locator("button[aria-label*='이미지 삭제']").first
            await expect(delete_btn).to_be_visible(timeout=3000)
            await delete_btn.click()
            await self.page.wait_for_timeout(500)
        print(f"  ✓ 사진 {delete_count}장 삭제")

        # 사진 모달 저장
        modal_save = self.page.locator(
            "#modal-content button:has-text('저장'), [role='dialog'] button:has-text('저장')"
        ).first
        await expect(modal_save).to_be_visible(timeout=5000)
        await modal_save.click()
        await self.page.wait_for_timeout(1000)

        # dimmer 남아있으면 ESC로 닫기
        dimmer = self.page.locator("div[class*='dimmer']:visible, div[class*='overlay']:visible").first
        if await dimmer.count() > 0:
            await self.page.keyboard.press("Escape")
            await self.page.wait_for_timeout(500)

        # 매출 저장
        save_btn = self.page.locator("button:has-text('매출 저장'):visible").first
        await expect(save_btn).to_be_visible(timeout=5000)

        dialog_messages = []

        def _auto_accept(dlg):
            dialog_messages.append(dlg.message)
            import asyncio as _asyncio
            _asyncio.create_task(dlg.accept())

        self.page.on("dialog", _auto_accept)
        try:
            await save_btn.click()
            await self.page.wait_for_timeout(2000)
        finally:
            self.page.remove_listener("dialog", _auto_accept)

        if dialog_messages:
            assert any("수정" in m for m in dialog_messages), (
                f"매출 수정 완료 alert 미확인: {dialog_messages}"
            )
        print(f"  ✓ {customer_name} 사진 삭제 후 매출 저장 완료")

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
                    if (!text.includes('매출') || !text.includes('등록')) return false;
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
            raise AssertionError("매출 등록 버튼을 찾지 못했습니다.")
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
        if "/book/calendar" not in self.page.url:
            base = self.base_url.replace("/signin", "")
            await self.page.goto(f"{base}/book/calendar", wait_until="networkidle")
        await self._move_calendar_to_today()
        await self.page.locator("button:has-text('일'):visible").first.click()
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

        # 사진 업로드 (0.5~4.9MB, 10장)
        asset_dir = os.path.join(os.path.dirname(__file__), "..", "..", "test_assets")
        photo_paths = [
            os.path.abspath(os.path.join(asset_dir, f"test_photo_{s}.jpg"))
            for s in ["0_5MB", "1_0MB", "1_5MB", "2_0MB", "2_5MB",
                       "3_0MB", "3_5MB", "4_0MB", "4_5MB", "4_9MB"]
        ]
        await self._upload_sales_photos(photo_paths)

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

        # 사진 업로드 (0.5~4.9MB, 10장)
        asset_dir = os.path.join(os.path.dirname(__file__), "..", "..", "test_assets")
        photo_paths = [
            os.path.abspath(os.path.join(asset_dir, f"test_photo_{s}.jpg"))
            for s in ["0_5MB", "1_0MB", "1_5MB", "2_0MB", "2_5MB",
                       "3_0MB", "3_5MB", "4_0MB", "4_5MB", "4_9MB"]
        ]
        await self._upload_sales_photos(photo_paths)

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
        cust_name = self.page.locator("p:has-text('미등록고객'):visible").first
        await expect(cust_name).to_be_visible(timeout=2000)

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

        result_item = self.page.locator(
            f"li:has-text('{customer}'):visible"
        ).first
        await expect(result_item).to_be_visible(timeout=5000)
        await result_item.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(1000)

        # 시술 메뉴 선택: 손 > 케어
        service_select = self.page.locator(
            "button.select-display:visible, div.select-display:visible"
        ).filter(
            has_text=re.compile(r"시술 메뉴를 선택해 주세요|시술.*선택")
        ).first
        await expect(service_select).to_be_visible(timeout=10000)
        await service_select.click()
        await self.page.wait_for_timeout(500)

        group_btn = self.page.locator("button:visible").filter(has_text=re.compile(r"^손$")).first
        await expect(group_btn).to_be_visible(timeout=5000)
        await group_btn.click()
        await self.page.wait_for_timeout(500)

        item_btn = self.page.locator("button:visible").filter(has_text=re.compile(r"^케어$")).first
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

        # 사진 업로드 (10MB x 10장)
        asset_dir = os.path.join(os.path.dirname(__file__), "..", "..", "test_assets")
        photo_paths = [
            os.path.abspath(os.path.join(asset_dir, f"test_photo_10MB_{i}.jpg"))
            for i in range(1, 11)
        ]
        await self._upload_sales_photos(photo_paths)

        await self._click_sales_save_button()
        print(f"✓ 매출 등록 5 완료 (패밀리 공유 정액권 {amount}원, 10MB 사진 10장)")

    async def custom_payment_method(self, customer_name=None):
        """커스텀 결제수단 추가 → 매출 등록 → 통계 검증 → 매출 삭제 → 결제수단 삭제"""
        print("\n=== 커스텀 결제수단 테스트 시작 ===")
        customer = customer_name or f"자동화_{self.mmdd}_1"
        payment_name = "페이 추가 테스트"

        # ── 1. 매출 페이지 → 신규 매출 등록 ──
        await self.focus_main_page()
        await self.page.locator("h3:has-text('매출')").first.click()
        await self.page.wait_for_load_state("networkidle")
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

        await self.page.wait_for_timeout(1000)
        name_input = self.page.locator("input[placeholder*='결제 수단 이름']").first
        await expect(name_input).to_be_visible(timeout=5000)
        await name_input.click()
        await name_input.type(payment_name, delay=30)
        print(f"  ✓ 결제수단 이름: {payment_name}")

        toggle = self.page.locator("label[for='isActiveSelectedPaymentMethod']").last
        await expect(toggle).to_be_visible(timeout=3000)
        await toggle.click()
        await self.page.wait_for_timeout(500)

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

        # 결제 수단 설정 모달 닫기
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

        await self.page.locator("button:has-text('매출 등록'):visible").last.click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(2000)
        print("  ✓ 매출 등록 완료")

        # ── 6. 통계 → 결제수단별 통계에서 확인 ──
        await self._open_statistics_page()
        await self._open_stat_detail("결제 수단별 통계")
        await self._apply_today_filter()

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

        sales_rows = self.page.locator("tr, li").filter(has_text=payment_name)
        row_count = await sales_rows.count()
        print(f"  '{payment_name}' 매출 행: {row_count}건")

        for i in range(row_count):
            row = sales_rows.first
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

        edit_btn = self.page.locator("button:has-text('편집')").last
        await edit_btn.scroll_into_view_if_needed()
        await edit_btn.click()
        await self.page.wait_for_timeout(500)

        delete_btn = self.page.locator("button:has-text('삭제')").first
        await expect(delete_btn).to_be_visible(timeout=3000)
        await delete_btn.click()
        await self.page.wait_for_timeout(1000)

        confirm_btn = self.page.locator("button:has-text('삭제'), button:has-text('확인')").last
        if await confirm_btn.count() > 0 and await confirm_btn.is_visible():
            await confirm_btn.click()
            await self.page.wait_for_timeout(1000)

        print(f"  ✓ '{payment_name}' 결제수단 삭제 완료")

        close_btn2 = self.page.locator("button:has(svg[icon='systemX']):visible, button[aria-label='close']:visible").first
        if await close_btn2.count() > 0:
            await close_btn2.click()
        else:
            await self.page.keyboard.press("Escape")
        await self.page.wait_for_timeout(500)

        print("=== 커스텀 결제수단 테스트 완료 ===\n")
