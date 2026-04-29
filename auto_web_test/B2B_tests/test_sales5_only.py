"""매출등록 5 단독 테스트: 패밀리 공유 정액권 매출등록
사전조건: 매출등록 1~4 완료 상태, 고객_3이 고객_1의 패밀리 멤버 + 정액권 충전 완료
"""
import os
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from pathlib import Path

headless_backup = os.environ.get("B2B_HEADLESS")
load_dotenv(Path(__file__).parent.parent / ".env.dev", override=True)
if headless_backup is not None:
    os.environ["B2B_HEADLESS"] = headless_backup

from auto_web_test.B2B_tests.test_b2b_v2 import B2BAutomationV2

pytestmark = pytest.mark.asyncio(loop_scope="module")


@pytest_asyncio.fixture(scope="module")
async def runner():
    r = B2BAutomationV2()
    await r.setup()
    await r.login()
    yield r
    await r.teardown()


async def test_sales_registration_5(runner):
    """매출 탭 → 새 항목 → 고객_3 → 손>케어 → 정액권 전액"""
    base = runner.base_url.replace("/signin", "")
    await runner.page.goto(f"{base}/book/calendar", wait_until="networkidle")
    await runner.page.locator("h3:has-text('매출')").first.click()
    await runner.page.wait_for_timeout(500)
    await runner.sales_registrations_5()
