"""매출등록 4→5 테스트: 미등록고객 제품 매출 → 패밀리 공유 정액권 매출등록
사전조건: 고객_3이 고객_1의 패밀리 멤버 + 고객_1 정액권 충전 완료 상태
"""
import os
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from pathlib import Path
from playwright.async_api import expect

# .env.dev 로드 (dev5 URL로 오버라이드)
load_dotenv(Path(__file__).parent.parent / ".env.dev", override=True)
os.environ["B2B_BASE_URL"] = "https://crm-dev5.gongbiz.kr/signin"
os.environ["B2B_HEADLESS"] = "1"  # headless

from auto_web_test.B2B_tests.test_b2b_v2 import B2BAutomationV2

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module")
async def runner():
    r = B2BAutomationV2()
    await r.setup()
    await r.login()
    yield r
    await r.teardown()


async def test_sales_registration_4(runner):
    """매출 탭 → 미등록고객 → 제품 → 네이버페이+미수금"""
    base = runner.base_url.replace("/signin", "")
    await runner.page.goto(f"{base}/book/calendar")
    await runner.page.wait_for_load_state("networkidle")

    await runner.sales_registrations_4()


async def test_sales_registration_5(runner):
    """매출 탭 → 새 항목 → 고객_3 → 손>케어 → 정액권 전액"""
    base = runner.base_url.replace("/signin", "")
    await runner.page.goto(f"{base}/book/calendar")
    await runner.page.wait_for_load_state("networkidle")
    await runner.page.locator("h3:has-text('매출')").first.click()
    await runner.page.wait_for_timeout(500)
    await runner.sales_registrations_5(customer_override="자동화_0315_3")
