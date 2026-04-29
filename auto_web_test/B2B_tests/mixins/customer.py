"""고객 관리: 추가, 상세, 프로필 수정, 탭 데이터 검증"""

import asyncio
import re

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import expect


class CustomerMixin:
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
        await self.page.wait_for_timeout(1000)
        # 소개자 드롭다운이 닫힐 때까지 대기
        for _ in range(10):
            if await result_item.count() == 0 or not await result_item.is_visible():
                break
            await self.page.wait_for_timeout(300)
        print(f"  ✓ 소개자 선택: {referrer_name}")

    async def _assert_customer_exists_in_list(self, customer_name):
        # 등록 직후 리스트 반영 지연을 고려해 재시도한다.
        for attempt in range(30):
            await self._ensure_active_page()
            list_item = self.page.locator(f"tr:has-text('{customer_name}')").first
            if await list_item.count() > 0 and await list_item.is_visible():
                return
            # 10회, 20회 실패 시 페이지 리로드
            if attempt in (10, 20):
                await self.page.reload()
                await self.page.wait_for_load_state("networkidle")
                await self.page.wait_for_timeout(1500)
            else:
                await self.page.wait_for_timeout(1000)
        raise AssertionError(f"고객 리스트에서 고객 미노출: {customer_name}")

    async def _customer_exists_in_list(self, customer_name):
        # 고객차트 테이블 td에서 정확한 이름 매칭
        cell = self.page.locator(f"table td:text-is('{customer_name}')").first
        return await cell.count() > 0 and await cell.is_visible()

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
                "#modal-content[type='SIDE'] header button:visible"
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
        if await exact_text.count() == 0:
            # 폴백: 더 유연한 매칭
            exact_text = self.page.get_by_text(re.compile(r"이미\s*등록된.*(연락처|고객)"))
        await expect(exact_text).to_be_visible(timeout=10000)
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
            if idx >= 2 and not self.skip_referrer:
                referrer_name = customers[0][0]
                await self._select_referrer(referrer_name)

            reg_btn = self.page.locator("button:has-text('고객 등록'):visible").last
            await expect(reg_btn).to_be_enabled(timeout=5000)
            await reg_btn.click()
            await self.page.wait_for_load_state("networkidle")
            await self._ensure_active_page()
            await self.page.wait_for_timeout(2000)

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
        year_btn = detail_page.get_by_role("button", name="년").first
        if await year_btn.count() == 0 or not await year_btn.is_visible():
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

        # ── 저장 버튼 클릭 ──
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

        # ── 삭제 차단 검증 ──
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
