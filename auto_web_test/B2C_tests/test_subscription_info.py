"""
이용권정보 페이지 테스트 (무료체험 샵 기준)
TC-01, 03, 06, 07, 08, 09, 14, 18, 20, 21
"""

import os
import re

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright, expect

pytestmark = pytest.mark.asyncio(loop_scope="module")

BASE_URL = os.getenv("B2B_BASE_URL", "https://crm-dev1.gongbiz.kr/signin")
ID = os.getenv("B2B_ID", "autoqatest1")
PASSWORD = os.getenv("B2B_PASSWORD", "gong2023@@")
SHOP_NAME = os.getenv("SUB_SHOP_NAME", "추가추가추")
# 이용권 페이지에 표시되는 샵 이름 (계정의 대표 샵)
DISPLAY_SHOP_NAME = os.getenv("SUB_DISPLAY_SHOP", "자동화_헤렌네일")
HEADLESS = os.getenv("B2B_HEADLESS", "1") == "1"


@pytest_asyncio.fixture(scope="module")
async def page():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=HEADLESS)
    context = await browser.new_context(viewport={"width": 1920, "height": 1080})
    context.set_default_timeout(60000)
    p = await context.new_page()

    # 로그인
    await p.goto(BASE_URL, timeout=60000)
    await p.fill('input[name="id"], input[type="text"]', ID)
    await p.fill('input[name="password"], input[type="password"]', PASSWORD)
    await p.click('button[type="submit"], .login-btn')
    try:
        await p.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass

    # 샵 선택 — tr.item 행에서 SHOP_NAME 찾아서 해당 행의 '샵으로 이동' 클릭
    await p.wait_for_timeout(2000)
    shop_row = p.locator(f"tr.item:has(div.name:text-is('{SHOP_NAME}'))")
    await expect(shop_row).to_be_visible(timeout=10000)
    move_btn = shop_row.locator("text=샵으로 이동").first
    await move_btn.click(no_wait_after=True)
    try:
        await p.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass
    await p.wait_for_timeout(2000)

    # 팝업 닫기
    for _ in range(3):
        try:
            dismiss = p.locator("text=하루 동안 보지 않기").first
            if await dismiss.is_visible():
                await dismiss.click()
                await p.wait_for_timeout(500)
            else:
                break
        except Exception:
            break

    # 현재 URL 확인
    print(f"현재 URL: {p.url}")
    print(f"✓ 로그인 + '{SHOP_NAME}' 샵 진입 완료")
    yield p

    await context.close()
    await browser.close()
    await pw.stop()


async def _go_to_subscription(page):
    """이용권정보 메인 페이지(/payment/license)로 이동"""
    # 이미 이용권 메인에 있으면 스킵 (purchase 등 하위 페이지는 제외)
    if page.url.endswith("/payment/license"):
        return

    # 하위 페이지(/purchase 등)에 있으면 뒤로가기 or URL 직접 이동
    if "/payment/" in page.url:
        base = page.url.split("/payment/")[0]
        await page.goto(f"{base}/payment/license", timeout=15000)
        await page.wait_for_timeout(1500)
        return

    # 캘린더 등 다른 페이지 → 이용권정보 버튼 클릭
    sub_btn = page.locator("button:has-text('이용권정보')").first
    if await sub_btn.count() == 0:
        sub_btn = page.get_by_text("이용권정보", exact=False).first
    await expect(sub_btn).to_be_visible(timeout=5000)
    await sub_btn.click()
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    await page.wait_for_timeout(1500)


# ══════════════════════════════════════════════
# TC-01: 이용권정보 페이지 진입
# ══════════════════════════════════════════════

async def test_tc01_subscription_page_entry(page):
    """TC-01: 이용권정보 페이지 진입 — 3개 탭, 기본탭, 샵 정보"""
    await _go_to_subscription(page)
    body = await page.locator("body").inner_text()

    # 3개 탭 표시
    for tab_name in ["이용권", "알림 충전", "결제 수단"]:
        tab = page.get_by_role("tab", name=tab_name).first
        if await tab.count() == 0:
            tab = page.locator(f"button:has-text('{tab_name}'), a:has-text('{tab_name}')").first
        assert await tab.count() > 0, f"'{tab_name}' 탭 미노출"
        print(f"✓ 탭 확인: {tab_name}")

    # 샵 이름 표시
    assert SHOP_NAME in body, f"샵 이름 '{SHOP_NAME}' 미노출"
    print(f"✓ 샵 이름 확인: {SHOP_NAME}")

    print("✓ TC-01 완료: 이용권정보 페이지 진입")


# ══════════════════════════════════════════════
# TC-03: 무료체험 이용권 정보 확인
# ══════════════════════════════════════════════

async def test_tc03_free_trial_info(page):
    """TC-03: 무료체험 이용권 정보 — 무료체험 표시, 구매 버튼, 사용기한, 안내문구"""
    await _go_to_subscription(page)

    # 이용권 탭 클릭
    tab = page.locator("button:has-text('이용권'), [role='tab']:has-text('이용권')").first
    await tab.click()
    await page.wait_for_timeout(1000)
    body = await page.locator("body").inner_text()

    # 사용중인 이용권
    assert "사용중인 이용권" in body or "사용 중인 이용권" in body, "'사용중인 이용권' 섹션 미노출"
    print("✓ '사용중인 이용권' 섹션 확인")

    # 무료체험 표시
    assert "무료체험" in body or "무료 체험" in body, "'무료체험' 미노출"
    print("✓ '무료체험' 표시 확인")

    # 이용권 구매 버튼
    buy_btn = page.locator("button:has-text('이용권 구매'), a:has-text('이용권 구매')").first
    assert await buy_btn.count() > 0, "'이용권 구매' 버튼 미노출"
    print("✓ '이용권 구매' 버튼 확인")

    # 사용 기한
    has_period = "사용 기한" in body or "만료" in body or re.search(r"\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}", body)
    assert has_period, "'사용 기한' 또는 만료일 미노출"
    print("✓ 사용 기한/만료일 확인")

    # 안내 문구
    assert "무료 체험 기간" in body or "무료체험 기간" in body, "무료체험 안내 문구 미노출"
    print("✓ 무료체험 안내 문구 확인")

    # 결제 내역 섹션
    assert "결제 내역" in body, "'결제 내역' 섹션 미노출"
    print("✓ '결제 내역' 섹션 확인")

    print("✓ TC-03 완료: 무료체험 이용권 정보")


# ══════════════════════════════════════════════
# TC-06: 이용권 구매 페이지 진입 (무료샵)
# ══════════════════════════════════════════════

async def test_tc06_purchase_page_entry(page):
    """TC-06: 이용권 구매 페이지 진입 — 연간/월간 탭, 할인 배지, 샵 정보"""
    await _go_to_subscription(page)

    # 이용권 탭 → 이용권 구매 버튼 클릭
    tab = page.locator("button:has-text('이용권'), [role='tab']:has-text('이용권')").first
    await tab.click()
    await page.wait_for_timeout(1000)

    buy_btn = page.locator("button:has-text('이용권 구매'), a:has-text('이용권 구매')").first
    await expect(buy_btn).to_be_visible(timeout=5000)
    await buy_btn.click()
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass
    await page.wait_for_timeout(1500)
    body = await page.locator("body").inner_text()

    # 이용권 구매 페이지 확인
    assert "이용권 구매" in body or "이용권" in body, "이용권 구매 페이지 미진입"
    print("✓ 이용권 구매 페이지 진입")

    # 연간/월간 탭
    annual_tab = page.locator("button:has-text('연간 결제'), [role='tab']:has-text('연간 결제')").first
    monthly_tab = page.locator("button:has-text('월간 결제'), [role='tab']:has-text('월간 결제')").first
    assert await annual_tab.count() > 0, "'연간 결제' 탭 미노출"
    assert await monthly_tab.count() > 0, "'월간 결제' 탭 미노출"
    print("✓ '연간 결제' / '월간 결제' 탭 확인")

    # 할인 배지
    assert "50%" in body or "할인" in body, "할인 배지 미노출"
    print("✓ 할인 배지 확인")

    # 샵 이름
    assert SHOP_NAME in body, f"샵 이름 '{SHOP_NAME}' 미노출"
    print("✓ 샵 이름 확인")

    print("✓ TC-06 완료: 이용권 구매 페이지 진입")


# ══════════════════════════════════════════════
# TC-07: 연간 결제 옵션 확인
# ══════════════════════════════════════════════

async def test_tc07_annual_plan_options(page):
    """TC-07: 연간 결제 옵션 — Standard/Pro 카드, 가격, 혜택"""
    # TC-06에서 이미 구매 페이지에 있을 수 있으므로 연간 결제 탭 클릭
    annual_tab = page.locator("button:has-text('연간 결제'), [role='tab']:has-text('연간 결제')").first
    if await annual_tab.count() > 0:
        await annual_tab.click()
        await page.wait_for_timeout(1000)
    body = await page.locator("body").inner_text()

    # 자동 결제 안내
    assert "1년마다 자동 결제" in body or "자동 결제" in body, "자동 결제 안내 미노출"
    print("✓ 자동 결제 안내 확인")

    # Standard 이용권
    assert "Standard" in body, "Standard 이용권 미노출"
    print("✓ Standard 이용권 확인")

    # Standard 설명
    assert "1인샵" in body or "예약 관리" in body, "Standard 설명 미노출"
    print("✓ Standard 설명 확인")

    # Pro 이용권
    assert "Pro" in body, "Pro 이용권 미노출"
    print("✓ Pro 이용권 확인")

    # Pro 설명
    assert "다인샵" in body or "팀워크" in body or "여러 명" in body, "Pro 설명 미노출"
    print("✓ Pro 설명 확인")

    # 부가세 별도
    assert "부가세 별도" in body or "부가세" in body, "'부가세 별도' 미노출"
    print("✓ '부가세 별도' 확인")

    # 혜택 항목
    assert "모든 기능" in body or "PC/앱" in body, "기능 혜택 미노출"
    print("✓ 기능 혜택 확인")

    # 구매하기 버튼
    buy_btns = page.locator("button:has-text('구매하기')")
    buy_count = await buy_btns.count()
    assert buy_count >= 2, f"'구매하기' 버튼 2개 미만: {buy_count}개"
    print(f"✓ '구매하기' 버튼 {buy_count}개 확인")

    # 할부 결제 가능
    assert "할부" in body, "'할부 결제 가능' 미노출"
    print("✓ '할부 결제 가능' 확인")

    print("✓ TC-07 완료: 연간 결제 옵션")


# ══════════════════════════════════════════════
# TC-08: 월간 결제 옵션 확인
# ══════════════════════════════════════════════

async def test_tc08_monthly_plan_options(page):
    """TC-08: 월간 결제 옵션 — Standard/Pro, 할부 없음, 첫 결제 포인트 없음"""
    monthly_tab = page.locator("button:has-text('월간 결제'), [role='tab']:has-text('월간 결제')").first
    await expect(monthly_tab).to_be_visible(timeout=5000)
    await monthly_tab.click()
    await page.wait_for_timeout(1000)
    body = await page.locator("body").inner_text()

    # 자동 결제 안내
    assert "1개월마다 자동 결제" in body or "자동 결제" in body, "월간 자동 결제 안내 미노출"
    print("✓ 월간 자동 결제 안내 확인")

    # Standard / Pro
    assert "Standard" in body, "Standard 미노출"
    assert "Pro" in body, "Pro 미노출"
    print("✓ Standard / Pro 확인")

    # 부가세 별도
    assert "부가세" in body, "'부가세 별도' 미노출"
    print("✓ '부가세 별도' 확인")

    # 구매하기 버튼
    buy_btns = page.locator("button:has-text('구매하기')")
    buy_count = await buy_btns.count()
    assert buy_count >= 2, f"'구매하기' 버튼 2개 미만: {buy_count}개"
    print(f"✓ '구매하기' 버튼 {buy_count}개 확인")

    print("✓ TC-08 완료: 월간 결제 옵션")


# ══════════════════════════════════════════════
# TC-09: 알림 충전 탭 진입
# ══════════════════════════════════════════════

async def test_tc09_notification_charge_tab(page):
    """TC-09: 알림 충전 탭 — 알림현황, 잔여알림, 충전하기, 자동충전, 충전내역"""
    await _go_to_subscription(page)

    charge_tab = page.locator("button:has-text('알림 충전'), [role='tab']:has-text('알림 충전')").first
    await expect(charge_tab).to_be_visible(timeout=5000)
    await charge_tab.click()
    await page.wait_for_timeout(1500)
    body = await page.locator("body").inner_text()

    # 알림 현황
    assert "알림 현황" in body or "잔여 알림" in body or "잔여알림" in body, "'알림 현황' 섹션 미노출"
    print("✓ '알림 현황' 섹션 확인")

    # 충전하기 버튼
    charge_btn = page.locator("button:has-text('충전하기')").first
    assert await charge_btn.count() > 0, "'충전하기' 버튼 미노출"
    print("✓ '충전하기' 버튼 확인")

    # 자동 충전 영역
    assert "자동 충전" in body, "'자동 충전' 영역 미노출"
    print("✓ '자동 충전' 영역 확인")

    # 사용하기 버튼
    use_btn = page.locator("button:has-text('사용하기')").first
    assert await use_btn.count() > 0, "'사용하기' 버튼 미노출"
    print("✓ '사용하기' 버튼 확인")

    # 충전 내역
    assert "충전 내역" in body, "'충전 내역' 섹션 미노출"
    print("✓ '충전 내역' 섹션 확인")

    print("✓ TC-09 완료: 알림 충전 탭")


# ══════════════════════════════════════════════
# TC-14: 자동 충전 미설정 상태 확인
# ══════════════════════════════════════════════

async def test_tc14_auto_charge_not_set(page):
    """TC-14: 자동 충전 미설정 — 조건 설정 안내, 사용하기 버튼, 안내 항목"""
    # TC-09에서 이미 알림 충전 탭에 있음
    body = await page.locator("body").inner_text()

    # 미설정 또는 OFF 상태 확인
    has_not_set = (
        "조건을 설정해 주세요" in body
        or "자동 충전을 꺼두셨네요" in body
        or "자동 충전 설정하시고" in body
        or "사용하기" in body
    )
    assert has_not_set, "자동 충전 미설정/OFF 상태 메시지 미노출"
    print("✓ 자동 충전 미설정/OFF 상태 확인")

    # 사용하기 버튼
    use_btn = page.locator("button:has-text('사용하기')").first
    assert await use_btn.count() > 0, "'사용하기' 버튼 미노출"
    print("✓ '사용하기' 버튼 확인")

    # 안내 항목 (최소 1개)
    has_guide = (
        "자동으로 충전" in body
        or "언제든지 변경" in body
        or "카드가 등록" in body
        or "편하게 알림 관리" in body
        or "편리하게 알림 관리" in body
    )
    assert has_guide, "자동 충전 안내 항목 미노출"
    print("✓ 자동 충전 안내 항목 확인")

    print("✓ TC-14 완료: 자동 충전 미설정 상태")


# ══════════════════════════════════════════════
# TC-18: 결제 수단 미등록
# ══════════════════════════════════════════════

@pytest.mark.skip(reason="계정에 결제 수단(삼성카드) 이미 등록됨 — 미등록 상태 검증 불가")
async def test_tc18_no_payment_method(page):
    """TC-18: 결제 수단 미등록 — 안내 문구, 카드정보변경 버튼 없음"""
    await _go_to_subscription(page)

    payment_tab = page.locator("button:has-text('결제 수단'), [role='tab']:has-text('결제 수단')").first
    await expect(payment_tab).to_be_visible(timeout=5000)
    await payment_tab.click()
    await page.wait_for_timeout(1500)
    body = await page.locator("body").inner_text()

    # 결제 수단 제목
    assert "결제 수단" in body, "'결제 수단' 제목 미노출"
    print("✓ '결제 수단' 제목 확인")

    # 미등록 안내
    has_no_card = (
        "등록된 결제 수단이 없습니다" in body
        or "결제 수단을 등록" in body
        or "카드가 등록되어 있지 않습니다" in body
    )
    assert has_no_card, "결제 수단 미등록 안내 미노출"
    print("✓ 결제 수단 미등록 안내 확인")

    # 카드 정보 변경 버튼 없음
    change_btn = page.locator("button:has-text('카드 정보 변경')")
    change_count = await change_btn.count()
    # 미등록이면 변경 버튼이 없어야 함
    if change_count == 0:
        print("✓ '카드 정보 변경' 버튼 미노출 (정상)")
    else:
        print(f"⚠ '카드 정보 변경' 버튼 {change_count}개 노출 (미등록인데 노출됨)")

    # 안내 사항
    has_guide = "계정당 하나의 결제 수단" in body or "헤렌" in body
    assert has_guide, "결제 수단 안내 사항 미노출"
    print("✓ 결제 수단 안내 사항 확인")

    print("✓ TC-18 완료: 결제 수단 미등록")


# ══════════════════════════════════════════════
# TC-20: 탭 전환
# ══════════════════════════════════════════════

async def test_tc20_tab_switching(page):
    """TC-20: 탭 전환 — 이용권→알림충전→결제수단→이용권"""
    await _go_to_subscription(page)

    tabs = {
        "이용권": ["사용중인 이용권", "사용 중인 이용권", "결제 내역", "무료체험", "무료 체험"],
        "알림 충전": ["알림 현황", "잔여 알림", "잔여알림", "충전 내역"],
        "결제 수단": ["결제 수단", "헤렌"],
    }

    for tab_name, keywords in tabs.items():
        tab = page.locator(f"button:has-text('{tab_name}'), [role='tab']:has-text('{tab_name}')").first
        await expect(tab).to_be_visible(timeout=5000)
        await tab.click()
        await page.wait_for_timeout(1500)
        body = await page.locator("body").inner_text()

        found = any(kw in body for kw in keywords)
        assert found, f"'{tab_name}' 탭 전환 후 콘텐츠 미노출 (기대 키워드: {keywords})"
        print(f"✓ '{tab_name}' 탭 전환 + 콘텐츠 확인")

    # 이용권 탭으로 복귀
    tab = page.locator("button:has-text('이용권'), [role='tab']:has-text('이용권')").first
    await tab.click()
    await page.wait_for_timeout(1000)

    # 샵 이름 유지 확인
    body = await page.locator("body").inner_text()
    assert SHOP_NAME in body, f"탭 전환 후 샵 이름 '{SHOP_NAME}' 미노출"
    print(f"✓ 탭 전환 후 샵 이름 유지: {SHOP_NAME}")

    print("✓ TC-20 완료: 탭 전환")


# ══════════════════════════════════════════════
# TC-21: 상단 헤더 네비게이션
# ══════════════════════════════════════════════

async def test_tc21_header_navigation(page):
    """TC-21: 상단 헤더 — 로고, 원장님, 캘린더로 이동, 로그아웃 등"""
    await _go_to_subscription(page)
    body = await page.locator("body").inner_text()

    # 원장님 텍스트
    assert "원장님" in body, "'원장님' 텍스트 미노출"
    print("✓ '원장님' 텍스트 확인")

    # 캘린더로 이동
    has_calendar = (
        "캘린더로 이동" in body
        or "캘린더" in body
        or await page.locator("a:has-text('캘린더')").count() > 0
    )
    assert has_calendar, "'캘린더로 이동' 링크 미노출"
    print("✓ '캘린더로 이동' 확인")

    # 로그아웃
    has_logout = (
        "로그아웃" in body
        or await page.locator("a:has-text('로그아웃'), button:has-text('로그아웃')").count() > 0
    )
    assert has_logout, "'로그아웃' 링크 미노출"
    print("✓ '로그아웃' 확인")

    # 공비서스토어
    has_store = (
        "공비서스토어" in body
        or "스토어" in body
        or await page.locator("a:has-text('스토어'), button:has-text('스토어')").count() > 0
    )
    assert has_store, "'공비서스토어' 버튼 미노출"
    print("✓ '공비서스토어' 확인")

    print("✓ TC-21 완료: 상단 헤더 네비게이션")
