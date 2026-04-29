"""통계: 샵 현황, 상품별/결제수단별 통계, 발송 이력"""

import re
from datetime import datetime

from playwright.async_api import expect


class StatisticsMixin:
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
                "button:has(svg[icon='reserveCalender']):visible"
            ).first
        await expect(range_btn).to_be_visible(timeout=5000)
        await range_btn.click()
        await self.page.wait_for_timeout(500)

        today_btn = self.page.locator(
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

    async def verify_send_history(self):
        """전송 내역에서 알림톡 발송 기록 검증"""
        print("\n=== 전송 내역 검증 시작 ===")
        await self.focus_main_page()

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

        rows = self.page.locator("tr").filter(has_text=today)
        row_count = await rows.count()
        print(f"  오늘({today}) 전송 내역: {row_count}건")

        found_records = []
        for i in range(row_count):
            row = rows.nth(i)
            cells = row.locator("td")
            if await cells.count() >= 3:
                customer = (await cells.nth(1).inner_text()).strip()
                content = (await cells.nth(2).inner_text()).strip()
                found_records.append((customer, content))

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
