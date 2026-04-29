"""콕예약 대량 등록 (데이터 생성용)"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from playwright.async_api import async_playwright, expect

CRM_BASE_URL = os.getenv("CRM_BASE_URL", "https://crm-dev5.gongbiz.kr")
SHOT_DIR = Path("qa_artifacts/screenshots/kok_generate")
SHOT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR = Path("qa_artifacts/kok_images")
IMG_DIR.mkdir(parents=True, exist_ok=True)

# 업종별 배경색
CATEGORY_COLORS = {
    "네일": ["#FFB6C1", "#FF69B4", "#FF1493"],  # 핑크 계열
    "헤어": ["#87CEEB", "#4682B4", "#1E90FF"],  # 블루 계열
}
_color_idx = {"네일": 0, "헤어": 0}


def generate_image(name, category):
    """시술명 + 업종별 색상으로 PNG 이미지 생성"""
    colors = CATEGORY_COLORS.get(category, ["#D3D3D3"])
    idx = _color_idx.get(category, 0) % len(colors)
    _color_idx[category] = idx + 1
    bg_color = colors[idx]

    img = Image.new("RGB", (800, 600), bg_color)
    draw = ImageDraw.Draw(img)

    # 시술명 텍스트 (기본 폰트)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 48)
        font_sm = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 28)
    except Exception:
        font = ImageFont.load_default()
        font_sm = font

    # 중앙 텍스트
    draw.text((400, 250), name, fill="white", font=font, anchor="mm")
    draw.text((400, 320), f"[{category}]", fill="white", font=font_sm, anchor="mm")
    draw.text((400, 380), "QA 테스트용 이미지", fill="#FFFFFFAA", font=font_sm, anchor="mm")

    path = IMG_DIR / f"{name.replace(' ', '_')}.png"
    img.save(str(path))
    return path

# ── 등록할 콕예약 데이터 (원하는 만큼 추가/수정 가능) ──
KOK_DATA = [
    {
        "name": "젤네일 풀세트",
        "category": "네일",
        "hour": 1, "minute": 30,
        "base_price": "55000",
        "member_price": "48000",
        "description": "젤 제거 + 케어 + 젤 원컬러 풀세트",
        "keywords": ["젤네일", "풀세트"],
    },
    {
        "name": "속눈썹 연장 내추럴",
        "category": "헤어",
        "hour": 1, "minute": 0,
        "base_price": "70000",
        "member_price": "63000",
        "description": "자연스러운 C컬 80가닥 속눈썹 연장",
        "keywords": ["속눈썹", "내추럴"],
    },
    {
        "name": "두피 스케일링 기본",
        "category": "헤어",
        "hour": 0, "minute": 40,
        "base_price": "35000",
        "member_price": "",
        "description": "두피 진단 + 스케일링 + 앰플 도포 기본 코스",
        "keywords": ["두피", "스케일링"],
    },
    {
        "name": "아트네일 시즌 한정",
        "category": "네일",
        "hour": 2, "minute": 0,
        "base_price": "90000",
        "member_price": "82000",
        "description": "시즌 트렌드 아트 10본 + 파츠 포함",
        "keywords": ["아트네일", "시즌"],
    },
    {
        "name": "왁싱 브라질리언",
        "category": "네일",
        "hour": 0, "minute": 30,
        "base_price": "45000",
        "member_price": "40000",
        "description": "브라질리언 왁싱 (남녀 공용)",
        "keywords": ["왁싱", "브라질리언"],
    },
    {
        "name": "페이셜 수분관리 프리미엄",
        "category": "헤어",
        "hour": 1, "minute": 30,
        "base_price": "120000",
        "member_price": "105000",
        "description": "클렌징 + 필링 + 수분팩 + LED + 마무리 크림 프리미엄 코스",
        "keywords": ["페이셜", "수분관리"],
    },
]


async def register_one(page, data, idx):
    """콕예약 1건 등록"""
    print(f"\n--- [{idx+1}/{len(KOK_DATA)}] {data['name']} 등록 시작 ---")

    # 등록 화면 진입
    register_btn = page.locator("button:has-text('콕예약 등록'), a:has-text('콕예약 등록')").first
    await expect(register_btn).to_be_visible(timeout=5000)
    await register_btn.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)

    # 콕예약 이름
    name_input = page.locator(
        "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
        "input[placeholder*='이름']"
    ).first
    await expect(name_input).to_be_visible(timeout=5000)
    await name_input.fill(data["name"])
    print(f"  ✓ 이름: {data['name']}")

    # 사진 업로드 (시술별 개별 이미지 생성)
    img_path = generate_image(data["name"], data["category"])
    file_input = page.locator("input[type='file']").first
    if await file_input.count() > 0:
        await file_input.set_input_files(str(img_path))
        await page.wait_for_timeout(2000)
        print(f"  ✓ 사진 업로드: {img_path.name}")

    # 시술 업종 선택 (필수: 헤어/네일)
    cat_btn = page.locator(
        f"div.sc-f80ce2ce-0 button:has-text('{data['category']}'), "
        f"button:has-text('{data['category']}'):visible"
    ).first
    await expect(cat_btn).to_be_visible(timeout=5000)
    await cat_btn.click()
    await page.wait_for_timeout(500)
    print(f"  ✓ 업종: {data['category']}")

    # 시술 시간 설정
    select_buttons = page.locator("button[data-testid='select-toggle-button']")
    select_count = await select_buttons.count()
    if select_count >= 2:
        # 시간 선택
        if data["hour"] != 1:  # 기본값 1시간이 아니면 변경
            await select_buttons.nth(0).click()
            await page.wait_for_timeout(700)
            hour_option = page.locator(
                f"ul:visible li:has-text('{data['hour']}'), "
                f"div[role='option']:has-text('{data['hour']}'):visible"
            ).first
            if await hour_option.count() > 0:
                await hour_option.click()
                await page.wait_for_timeout(500)

        # 분 선택
        if data["minute"] != 0:  # 기본값 0분이 아니면 변경
            await select_buttons.nth(1).click()
            await page.wait_for_timeout(700)
            min_option = page.locator(
                f"ul:visible li:has-text('{data['minute']}'), "
                f"div[role='option']:has-text('{data['minute']}'):visible"
            ).first
            if await min_option.count() > 0:
                await min_option.click()
                await page.wait_for_timeout(500)
    print(f"  ✓ 시술 시간: {data['hour']}시간 {data['minute']}분")

    # 기본 가격
    base_price = page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
    if await base_price.count() > 0:
        await base_price.fill(data["base_price"])
        print(f"  ✓ 기본 가격: {int(data['base_price']):,}원")

    # 회원 가격
    if data.get("member_price"):
        member_price = page.locator("input[placeholder*='할인가를 입력'], input[placeholder*='회원']").first
        if await member_price.count() > 0:
            await member_price.fill(data["member_price"])
            print(f"  ✓ 회원 가격: {int(data['member_price']):,}원")
    else:
        print("  ✓ 회원 가격: 미입력")

    # 시술 설명
    desc_input = page.locator("textarea, input[placeholder*='설명'], input[placeholder*='내용']").first
    if await desc_input.count() > 0:
        await desc_input.fill(data["description"])
        print(f"  ✓ 설명: {data['description']}")

    # 키워드 (첫 번째 빈 필드에 입력 → Enter → 반복)
    for kw in data.get("keywords", []):
        kw_field = page.locator("input[placeholder*='키워드']").last
        try:
            await expect(kw_field).to_be_visible(timeout=3000)
            await kw_field.fill(kw)
            await kw_field.press("Enter")
            await page.wait_for_timeout(700)
        except Exception:
            print(f"  ⚠ 키워드 '{kw}' 입력 실패, 스킵")
    if data.get("keywords"):
        print(f"  ✓ 키워드: {', '.join(data['keywords'])}")

    await page.screenshot(path=str(SHOT_DIR / f"kok_{idx+1:02d}_before_save.png"))

    # 저장
    await page.evaluate("""() => {
        window.scrollTo(0, 0);
        const btn = document.querySelector('button[type="submit"]')
            || [...document.querySelectorAll('button')].find(b => b.textContent.trim() === '저장');
        if (btn && !btn.disabled) btn.click();
    }""")
    await page.wait_for_timeout(3000)

    # 저장 후 목록 복귀 대기 (최대 15초, 안 되면 URL로 직접 이동)
    try:
        await page.wait_for_selector("text=콕예약 관리", timeout=15000)
    except Exception:
        await page.screenshot(path=str(SHOT_DIR / f"kok_{idx+1:02d}_save_stuck.png"))
        print(f"  ⚠ 저장 후 목록 복귀 안됨, URL로 직접 이동")
        base = CRM_BASE_URL.rstrip("/")
        await page.goto(f"{base}/online-reservation/kok")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(2000)

    await page.screenshot(path=str(SHOT_DIR / f"kok_{idx+1:02d}_after_save.png"))

    # 목록에서 확인
    await page.wait_for_timeout(1500)
    list_text = await page.locator("body").inner_text()
    if data["name"] in list_text:
        print(f"  ✓ 저장 완료 & 목록 확인")
    else:
        print(f"  ⚠ 저장은 됐으나 목록에서 '{data['name']}' 미확인 (스킵)")


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True, slow_mo=0)
    ctx = await browser.new_context(viewport={"width": 1920, "height": 1080})
    page = await ctx.new_page()

    # ── 로그인 ──
    await page.goto(f"{CRM_BASE_URL}/signin")
    await page.fill('input[name="id"], input[type="text"]', "autoqatest1")
    await page.fill('input[name="password"], input[type="password"]', "gong2023@@")
    await page.click('button[type="submit"]')
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)
    print("✓ 로그인 완료")

    # ── 샵 선택 ──
    shop_name = "0411_1135_배포_테스트"
    shop_row = page.locator(f"tr.item:has-text('{shop_name}')").first
    await expect(shop_row).to_be_visible(timeout=10000)
    move_btn = shop_row.locator("a:has-text('샵으로 이동'), span:has-text('샵으로 이동')").first
    await expect(move_btn).to_be_visible(timeout=5000)
    await move_btn.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)
    print(f"✓ 샵 진입: {shop_name}")

    # ── 콕예약 관리 진입 ──
    online_menu = page.locator(
        "h3:has-text('온라인 예약'):visible, a:has-text('온라인 예약'):visible, "
        "button:has-text('온라인 예약'):visible, span:has-text('온라인 예약'):visible"
    ).first
    await expect(online_menu).to_be_visible(timeout=10000)
    await online_menu.click()
    await page.wait_for_timeout(700)

    kok_menu = page.locator(
        "a:has-text('콕예약 관리'):visible, span:has-text('콕예약 관리'):visible, "
        "h4:has-text('콕예약 관리'):visible, li:has-text('콕예약 관리'):visible"
    ).first
    await expect(kok_menu).to_be_visible(timeout=5000)
    await kok_menu.click()
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1500)
    print("✓ 콕예약 관리 진입")

    # ── 콕예약 순차 등록 ──
    print(f"\n=== 콕예약 {len(KOK_DATA)}건 등록 시작 ===")
    for idx, data in enumerate(KOK_DATA):
        await register_one(page, data, idx)

    print(f"\n=== 콕예약 {len(KOK_DATA)}건 등록 완료 ===")

    await page.wait_for_timeout(2000)
    await ctx.close()
    await browser.close()
    await pw.stop()


asyncio.run(main())
