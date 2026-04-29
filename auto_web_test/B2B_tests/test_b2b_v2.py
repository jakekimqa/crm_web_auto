"""B2B 자동화 테스트 v2 — Mixin 조합 클래스"""

import pytest

from auto_web_test.B2B_tests.mixins.common import CommonMixin
from auto_web_test.B2B_tests.mixins.customer import CustomerMixin
from auto_web_test.B2B_tests.mixins.membership import MembershipMixin
from auto_web_test.B2B_tests.mixins.reservation import ReservationMixin
from auto_web_test.B2B_tests.mixins.sales import SalesMixin
from auto_web_test.B2B_tests.mixins.statistics import StatisticsMixin


class B2BAutomationV2(
    CommonMixin,
    CustomerMixin,
    MembershipMixin,
    ReservationMixin,
    SalesMixin,
    StatisticsMixin,
):
    """기능별 Mixin을 조합한 B2B 통합 테스트 러너.

    새 기능 추가 시 해당 mixin 파일에 메서드를 추가하면 됩니다:
      - mixins/common.py      — 브라우저, 로그인, 팝업 처리
      - mixins/customer.py    — 고객 추가/상세/프로필 수정
      - mixins/membership.py  — 정액권/티켓 충전, 패밀리
      - mixins/reservation.py — 예약 등록/캘린더/예약 차단
      - mixins/sales.py       — 매출등록 1~5, 사진 업로드, 커스텀 결제수단
      - mixins/statistics.py  — 통계, 샵 현황, 발송 이력
    """
    pass


# ══════════════════════════════════════════════
# 단독 실행용 테스트 (개별 기능 디버깅용)
# ══════════════════════════════════════════════

@pytest.mark.asyncio
async def test_login_and_add_customers_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.add_customers()
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_customer_detail_name_from_list_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.add_customers(verify_duplicates=True)
        target_name = f"자동화_{runner.mmdd}_1"
        detail_page = await runner.open_customer_detail_from_list(target_name)
        await runner.assert_customer_name_visible_top_left(detail_page, target_name)
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_membership_charge_from_customer_detail_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        target_name = f"자동화_{runner.mmdd}_1"
        await runner.membership_charge_and_verify(target_name)
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_ticket_charge_from_customer_detail_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        target_name = f"자동화_{runner.mmdd}_2"
        await runner.ticket_charge_and_verify(target_name)
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_make_reservations_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.make_reservations()
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_verify_calendar_reservations_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.verify_calendar_reservations()
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_sales_registrations_1_to_4_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.sales_registrations_1()
        await runner.sales_registrations_2()
        await runner.sales_registrations_3()
        await runner.sales_registrations_4()
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_verify_shop_status_today_summary_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.verify_shop_status_today_summary()
    finally:
        await runner.teardown()


@pytest.mark.asyncio
async def test_verify_statistics_details_v2():
    runner = B2BAutomationV2()
    try:
        await runner.setup()
        await runner.login()
        await runner.verify_shop_status_and_statistics()
    finally:
        await runner.teardown()
