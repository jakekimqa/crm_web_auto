"""
정액권 충전 후 패밀리 추가 테스트 (자동화_헤렌네일 샵)
- 첫 번째 고객 상세 진입
- 패밀리 탭 클릭
- 패밀리 추가하기 → 세 번째 고객 추가
- 멤버 영역에 1번, 3번 고객 노출 확인
"""
import os, re, sys
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright, expect

sys.path.append(str(Path(__file__).resolve().parents[2]))
from auto_web_test.B2B_tests.test_b2b_v2 import B2BAutomationV2

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module")
async def runner():
    r = B2BAutomationV2()
    r.base_url = os.getenv("B2B_BASE_URL", "https://crm-dev5.gongbiz.kr/signin")
    r.headless = os.getenv("B2B_HEADLESS", "1") == "1"
    await r.setup()
    await r.login()
    yield r
    await r.teardown()


@pytest_asyncio.fixture(autouse=True)
async def clean_state(runner):
    base = runner.base_url.replace("/signin", "")
    await runner.page.goto(f"{base}/book/calendar")
    await runner.page.wait_for_load_state("networkidle")
    yield


async def test_family_share(runner):
    mmdd = runner.mmdd
    customer_1 = f"자동화_{mmdd}_1"
    customer_3 = f"자동화_{mmdd}_3"

    # 고객 상세 진입
    print(f"\n=== 고객 상세 진입: {customer_1} ===")
    page = runner.page

    # 고객차트 열기
    await runner._open_customer_chart()
    await runner._dismiss_active_dimmer()
    await page.wait_for_timeout(1000)

    # 디버깅: 고객 행 구조 확인
    row = page.locator(f"tr:has-text('{customer_1}')").first
    await expect(row).to_be_visible(timeout=5000)
    row_html = await row.evaluate("el => el.innerHTML")
    print(f"  ROW innerHTML (first 500): {row_html[:500]}")

    # 행 내 a 태그 찾기
    link = row.locator("a").first
    link_count = await row.locator("a").count()
    print(f"  링크 개수: {link_count}")
    if link_count > 0:
        href = await link.get_attribute("href")
        target = await link.get_attribute("target")
        print(f"  첫 번째 링크: href={href}, target={target}")

    # 클릭하여 새 탭 열기 시도
    click_target = link if link_count > 0 else row
    try:
        async with runner.context.expect_page(timeout=10000) as new_page_info:
            await click_target.click()
        detail_page = await new_page_info.value
        await detail_page.wait_for_load_state("domcontentloaded")
        await detail_page.bring_to_front()
    except Exception as e:
        print(f"  새 탭 열기 실패: {e}")
        # URL 변경 확인
        await page.wait_for_timeout(2000)
        print(f"  현재 URL: {page.url}")
        print(f"  페이지 수: {len(runner.context.pages)}")
        detail_page = page

    print(f"  detail_page URL: {detail_page.url}")
    print(f"  페이지 수: {len(runner.context.pages)}")
    await detail_page.screenshot(path="qa_artifacts/screenshots/family_00_detail.png")

    # 패밀리 탭 클릭
    print("\n=== 패밀리 탭 클릭 ===")
    family_tab = detail_page.locator("button[role='tab']").filter(has_text="패밀리").first
    if await family_tab.count() == 0:
        family_tab = detail_page.locator("button:has-text('패밀리')").first
    await expect(family_tab).to_be_visible(timeout=10000)
    await family_tab.click()
    await detail_page.wait_for_timeout(1000)
    print("  ✓ 패밀리 탭 클릭 완료")
    await detail_page.screenshot(path="qa_artifacts/screenshots/family_01_tab.png")

    # 패밀리 추가하기 버튼
    print("\n=== 패밀리 추가하기 ===")
    add_family_btn = detail_page.get_by_role("button", name="패밀리 추가하기").first
    if await add_family_btn.count() == 0:
        add_family_btn = detail_page.locator("button:has-text('패밀리 추가하기')").first
    await expect(add_family_btn).to_be_visible(timeout=10000)
    await add_family_btn.click()
    await detail_page.wait_for_timeout(1000)
    print("  ✓ 패밀리 추가하기 클릭")

    # 패밀리 추가 모달
    await detail_page.wait_for_timeout(500)
    await detail_page.screenshot(path="qa_artifacts/screenshots/family_02_modal.png")

    # 고객 검색: placeholder "고객 이름, 연락처, 메모"
    search_input = detail_page.get_by_placeholder("고객 이름, 연락처, 메모").first
    await expect(search_input).to_be_visible(timeout=5000)

    # 전화번호로 검색 시도 (이름 검색이 안 될 경우 대비)
    phone_3 = f"0{mmdd}0003"  # 01003150003
    for keyword in [customer_3, phone_3]:
        await search_input.fill("")
        await search_input.type(keyword, delay=50)
        await detail_page.wait_for_timeout(2000)
        await detail_page.screenshot(path=f"qa_artifacts/screenshots/family_03_search_{keyword[:6]}.png")

        # 검색 결과에서 고객 선택 (입력란 아래 드롭다운)
        # "신규 고객 등록"이 아닌 결과 찾기
        results = detail_page.locator("[class*='search'] li, [class*='dropdown'] li, [class*='list'] li, [class*='option']").filter(
            has_text=re.compile(r"자동화.*3|0003")
        )
        if await results.count() > 0:
            await results.first.click()
            await detail_page.wait_for_timeout(500)
            print(f"  ✓ {customer_3} 선택 (검색어: {keyword})")
            break

        # get_by_text로도 시도 (드롭다운 항목)
        option = detail_page.get_by_text(customer_3, exact=False).first
        # "신규 고객 등록" 제외
        if await option.count() > 0:
            text = await option.inner_text()
            if "신규" not in text and "등록" not in text:
                await option.click()
                await detail_page.wait_for_timeout(500)
                print(f"  ✓ {customer_3} 선택 (검색어: {keyword})")
                break
    else:
        # 검색 실패 시 디버깅
        body = await detail_page.locator("body").inner_text()
        print(f"  검색 실패. 모달 텍스트:\n{body[:500]}")
        pytest.fail(f"패밀리 모달에서 {customer_3}을 찾지 못했습니다")

    await detail_page.screenshot(path="qa_artifacts/screenshots/family_04_selected.png")

    # 모달 내 추가 버튼 클릭 (배경의 "패밀리 추가하기"가 아닌 모달 submit 버튼)
    modal = detail_page.locator("#modal-content:visible, [role='dialog']:visible").first
    if await modal.count() > 0:
        add_btn = modal.get_by_role("button", name="추가", exact=True).first
    else:
        add_btn = detail_page.get_by_role("button", name="추가", exact=True).first
    await expect(add_btn).to_be_visible(timeout=5000)
    await add_btn.click(force=True)
    await detail_page.wait_for_timeout(2000)
    print("  ✓ 패밀리 추가 완료")

    # 멤버 영역 확인: customer_1, customer_3 노출
    print("\n=== 멤버 확인 ===")
    await detail_page.wait_for_timeout(1000)
    await detail_page.screenshot(path="qa_artifacts/screenshots/family_05_members.png")

    body_text = await detail_page.locator("body").inner_text()
    assert customer_1 in body_text, f"멤버에 {customer_1}이 보이지 않습니다"
    print(f"  ✓ 멤버 확인: {customer_1}")
    assert customer_3 in body_text, f"멤버에 {customer_3}이 보이지 않습니다"
    print(f"  ✓ 멤버 확인: {customer_3}")

    print("\n=== 패밀리 추가 테스트 성공! ===")

    # 상세 페이지 닫기 + 메인 페이지 복귀
    if detail_page is not runner.page and not detail_page.is_closed():
        await detail_page.close()
        await runner.focus_main_page()
