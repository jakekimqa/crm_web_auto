"""직원 통계 3/27 오늘 필터 확인"""
import asyncio
import re
from playwright.async_api import async_playwright, expect


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    ctx = await browser.new_context(viewport={"width": 1920, "height": 1080})
    page = await ctx.new_page()

    # 로그인
    await page.goto("https://crm-dev1.gongbiz.kr/signin")
    await page.fill('input[name="id"], input[type="text"]', "autoqatest1")
    await page.fill('input[name="password"], input[type="password"]', "gong2023@@")
    await page.click('button[type="submit"]')
    await page.wait_for_load_state("networkidle")

    row = page.locator("tr:has-text('자동화_헤렌네일')")
    await row.locator("a:has-text('샵으로 이동')").first.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)
    print("✓ 로그인 완료")

    # 통계 > 직원 통계
    stats_menu = page.locator("h3:has-text('통계'):visible").first
    await stats_menu.click()
    await page.wait_for_timeout(1000)

    clicked = await page.evaluate("""() => {
        const norm = (s) => (s || '').replace(/\\s+/g, ' ').trim();
        const visible = (el) => {
            const r = el.getBoundingClientRect();
            const st = window.getComputedStyle(el);
            return r.width > 0 && r.height > 0 && st.display !== 'none' && st.visibility !== 'hidden';
        };
        const titleNodes = [...document.querySelectorAll('h1,h2,h3,h4,div,span,p')]
            .filter((el) => visible(el) && norm(el.innerText) === '직원 통계');
        for (const t of titleNodes) {
            let box = t;
            for (let i = 0; i < 8 && box; i++, box = box.parentElement) {
                const btns = [...box.querySelectorAll('button,a')]
                    .filter((el) => visible(el) && norm(el.innerText).includes('자세히 보기'));
                if (btns.length > 0) { btns[0].click(); return true; }
            }
        }
        return false;
    }""")
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)

    # 오늘 필터 적용 (_apply_today_filter 와 동일 로직)
    range_btn = page.locator("button:has(svg[icon='reserveCalender']):visible").filter(
        has_text=re.compile(r"\d{1,2}\.\s*\d{1,2}\.\s*\d{1,2}")
    ).first
    if await range_btn.count() == 0:
        range_btn = page.locator("button:has(svg[icon='reserveCalender']):visible").first
    await range_btn.click()
    await page.wait_for_timeout(500)

    today_btn = page.locator("button:has(h4:has-text('오늘')):visible, button.sc-c8a80cb6-6:has(h4:has-text('오늘')):visible").first
    if await today_btn.count() == 0:
        today_btn = page.get_by_role("button", name="오늘").locator(":visible").first
    await today_btn.click()
    await page.wait_for_timeout(300)

    search_btn = page.get_by_role("button", name=re.compile(r"기간 검색$")).locator(":visible").first
    if await search_btn.count() == 0:
        search_btn = page.locator("button:has-text('기간 검색'):visible").last
    await search_btn.click()
    await page.wait_for_timeout(1000)
    print("✓ 오늘 필터 적용")

    # 상품 유형별 스크린샷 + 데이터
    await page.screenshot(path="/Users/jakekim/PycharmProjects/pythonProject1/qa_artifacts/screenshots/staff_stats_0327_product.png", full_page=True)
    table = page.locator("table:visible").first
    text = await table.inner_text()
    print(f"\n=== 상품 유형별 (오늘) ===")
    print(text[:3000])

    # 고객 유형별 탭
    customer_tab = page.locator("button:has-text('고객 유형별 통계'):visible").first
    await customer_tab.click()
    await page.wait_for_timeout(1000)

    await page.screenshot(path="/Users/jakekim/PycharmProjects/pythonProject1/qa_artifacts/screenshots/staff_stats_0327_customer_real.png", full_page=True)
    table2 = page.locator("table:visible").first
    text2 = await table2.inner_text()
    print(f"\n=== 고객 유형별 (실 매출 기준, 오늘) ===")
    print(text2[:3000])

    # 총 합계 기준
    total_label = page.locator("label:has-text('총 합계 기준'):visible").first
    await total_label.click()
    await page.wait_for_timeout(1000)

    await page.screenshot(path="/Users/jakekim/PycharmProjects/pythonProject1/qa_artifacts/screenshots/staff_stats_0327_customer_total.png", full_page=True)
    table3 = page.locator("table:visible").first
    text3 = await table3.inner_text()
    print(f"\n=== 고객 유형별 (총 합계 기준, 오늘) ===")
    print(text3[:3000])

    await browser.close()
    await pw.stop()

asyncio.run(main())
