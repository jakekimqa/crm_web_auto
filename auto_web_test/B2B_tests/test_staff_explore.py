"""직원 관리 페이지 탐색용 임시 테스트"""
import os
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from pathlib import Path
from playwright.async_api import expect

load_dotenv(Path(__file__).parent.parent / ".env.dev", override=True)
os.environ["B2B_BASE_URL"] = "https://crm-dev5.gongbiz.kr/signin"
os.environ["B2B_HEADLESS"] = "1"

from auto_web_test.B2B_tests.test_b2b_v2 import B2BAutomationV2

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module")
async def runner():
    r = B2BAutomationV2()
    await r.setup()
    await r.login()
    yield r
    await r.teardown()


async def test_explore_staff_page(runner):
    """사이드 메뉴에서 우리샵 관리 > 직원관리 탐색"""
    base = runner.base_url.replace("/signin", "")
    await runner.page.goto(f"{base}/book/calendar")
    await runner.page.wait_for_load_state("networkidle")

    # 우리샵 관리 메뉴 클릭
    await runner.page.locator("text=우리샵 관리").first.click()
    await runner.page.wait_for_timeout(500)

    # 직원관리 클릭
    await runner.page.locator("text=직원관리").first.click()
    await runner.page.wait_for_load_state("networkidle")
    await runner.page.wait_for_timeout(1000)

    current_url = runner.page.url
    print(f"현재 URL: {current_url}")
    await runner.page.screenshot(path="qa_artifacts/screenshots/staff_02_list.png", full_page=True)
    print("✓ 직원관리 페이지 스크린샷 저장")

    # 직원 목록 확인
    body_text = await runner.page.locator("body").text_content()
    print(f"페이지 텍스트 (앞부분): {body_text[:2000]}")
