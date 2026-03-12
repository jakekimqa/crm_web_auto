import os
import re
import asyncio
from datetime import datetime

import pytest
import pytest_asyncio
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright, expect

from auto_web_test.B2B_tests.test_b2b_v2 import B2BAutomationV2

# 모든 테스트가 동일한 event loop를 공유하도록 module scope 설정
pytestmark = pytest.mark.asyncio(loop_scope="module")


# ── module-scoped fixture: 브라우저 + 로그인 1회 ──

@pytest_asyncio.fixture(scope="module")
async def runner():
    r = B2BAutomationV2()
    await r.setup()
    await r.login()
    yield r
    await r.teardown()


# ── 각 테스트 시작 시 캘린더 페이지로 초기화 ──

@pytest_asyncio.fixture(autouse=True)
async def clean_state(runner):
    base = runner.base_url.replace("/signin", "")
    await runner.page.goto(f"{base}/book/calendar")
    await runner.page.wait_for_load_state("networkidle")
    yield


# ── 테스트 함수들 (runner fixture 주입) ──

async def test_login_and_add_customers(runner):
    await runner.add_customers()


async def test_customer_detail_name_from_list(runner):
    await runner.add_customers(verify_duplicates=True)
    target_name = f"자동화_{runner.mmdd}_1"
    detail_page = await runner.open_customer_detail_from_list(target_name)
    await runner.assert_customer_name_visible_top_left(detail_page, target_name)


async def test_membership_charge_from_customer_detail(runner):
    target_name = f"자동화_{runner.mmdd}_1"
    await runner.membership_charge_and_verify(target_name)


async def test_ticket_charge_from_customer_detail(runner):
    target_name = f"자동화_{runner.mmdd}_2"
    await runner.ticket_charge_and_verify(target_name)


async def test_make_reservations(runner):
    await runner.make_reservations()


async def test_verify_calendar_reservations(runner):
    await runner.verify_calendar_reservations()


async def test_sales_registrations_1_to_4(runner):
    await runner.sales_registrations_1()
    await runner.sales_registrations_2()
    await runner.sales_registrations_3()
    await runner.sales_registrations_4()


async def test_verify_shop_status_today_summary(runner):
    await runner.verify_shop_status_today_summary()


async def test_verify_statistics_details(runner):
    await runner.verify_shop_status_and_statistics()
