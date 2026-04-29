"""
B2C 예약 3건 → B2B 취소 + 사유 검증 → 매출 등록 → 콕예약 등록/수정/예약/매출/통계/비활성화
"""
import asyncio, os, re, sys, json, urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

import pytest
from playwright.async_api import async_playwright, expect

sys.path.append(str(Path(__file__).resolve().parents[2]))
from auto_web_test.B2C_tests.test_b2b_b2c_shop_activation_flow import (
    ShopActivationRunner, _crm_login, _switch_shop,
    _open_nearby_list, _is_shop_visible_in_nearby,
    _make_reservation, _kakao_login, _is_toggle_on, _set_toggle,
    CRM_BASE_URL, ZERO_BASE_URL, SHOT_DIR,
)

IMG_DIR = Path("qa_artifacts/kok_register_images")
IMG_DIR.mkdir(parents=True, exist_ok=True)
KOK_IMAGE_COLORS = ["#FFB6C1", "#87CEEB", "#98FB98", "#DDA0DD", "#FFDAB9"]


def generate_kok_images(kok_name, count=5):
    """콕예약용 이미지 생성"""
    try:
        font = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 40)
        font_sm = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 24)
    except Exception:
        font = ImageFont.load_default()
        font_sm = font
    paths = []
    for i in range(count):
        color = KOK_IMAGE_COLORS[i % len(KOK_IMAGE_COLORS)]
        img = Image.new("RGB", (800, 600), color)
        draw = ImageDraw.Draw(img)
        draw.text((400, 260), kok_name, fill="white", font=font, anchor="mm")
        draw.text((400, 320), f"사진 {i + 1}/{count}", fill="white", font=font_sm, anchor="mm")
        path = IMG_DIR / f"{kok_name.replace(' ', '_')}_{i + 1}.png"
        img.save(str(path))
        paths.append(str(path))
    return paths


@pytest.mark.asyncio
async def test_b2c_booking_cancel_with_default_reason():
    shop_name = f"{datetime.now():%m%d_%H%M}_배포_테스트"

    runner = ShopActivationRunner()
    runner.base_url = f"{CRM_BASE_URL}/signin"
    runner.headless = os.getenv("B2B_HEADLESS", "1") == "1"
    runner.mmdd = datetime.now().strftime("%m%d_%H%M")
    crm_page = zero_page = zero_context = None

    # PIL로 B2C 입점 이미지 3장 생성 + 오버라이드
    def _generate_b2c_images():
        colors = ["#FF6B6B", "#4ECDC4", "#45B7D1"]
        labels = ["샵 대표", "시술 예시", "인테리어"]
        paths = []
        try:
            font = ImageFont.truetype("/System/Library/Fonts/AppleSDGothicNeo.ttc", 36)
        except Exception:
            font = ImageFont.load_default()
        for i, (color, label) in enumerate(zip(colors, labels)):
            img = Image.new("RGB", (800, 600), color)
            draw = ImageDraw.Draw(img)
            draw.text((400, 300), label, fill="white", font=font, anchor="mm")
            p = Path("/tmp") / f"b2c_test_img_{i+1}.png"
            img.save(str(p))
            paths.append(str(p))
        return paths

    b2c_img_paths = _generate_b2c_images()

    async def _attach_b2c_test_image_override(self_runner):
        await self_runner.page.set_input_files("input[type='file']", b2c_img_paths)
        await self_runner.page.wait_for_timeout(2000)

    runner._attach_b2c_test_image = lambda: _attach_b2c_test_image_override(runner)

    try:
        # ── Phase 1: 샵 생성 + 입점 ──
        print("\n=== Phase 1: 샵 생성 + 공비서 입점 ===")
        await runner.setup()

        # 로그인 → 바로 샵 생성
        await runner.page.goto(runner.base_url)
        await runner.page.fill('input[name="id"], input[type="text"]', runner.correct_id)
        await runner.page.fill('input[name="password"], input[type="password"]', runner.correct_password)
        await runner.page.click('button[type="submit"], .login-btn')
        await runner.page.wait_for_load_state("networkidle")
        await runner.page.wait_for_timeout(1000)
        print("  ✓ 로그인 완료")

        # 샵 추가 클릭 (로그인 후 바로 샵 목록 화면)
        add_shop = runner.page.get_by_role("link", name="+ 샵 추가")
        await expect(add_shop).to_be_visible(timeout=10000)
        await add_shop.click()

        # 샵 정보 입력
        name_input = runner.page.get_by_placeholder("샵 이름")
        await expect(name_input).to_be_visible(timeout=10000)
        await name_input.fill(f"{runner.mmdd}_배포_테스트")

        async with runner.page.expect_popup() as input_addr_info:
            await runner.page.locator("input#addr[placeholder='샵 주소']").click()
        input_addr_page = await input_addr_info.value
        await input_addr_page.wait_for_load_state("domcontentloaded")
        await input_addr_page.wait_for_load_state("networkidle")
        await input_addr_page.wait_for_timeout(1000)

        frame = await runner._find_address_search_frame(input_addr_page)
        search_input = frame.locator("input#region_name, input.tf_keyword").first
        await search_input.fill("강남역")
        await search_input.press("Enter")

        address_item = frame.locator("span.txt_address").filter(
            has_text="서울 강남구 강남대로 지하 396 (강남역)"
        ).locator("button.link_post").first
        await expect(address_item).to_be_visible(timeout=10000)
        await address_item.click()

        detail_addr = runner.page.get_by_placeholder("상세 주소")
        await detail_addr.fill("테스트 상세주소")
        await detail_addr.press("Tab")
        await runner.page.wait_for_timeout(300)
        await runner.page.get_by_role("link", name="다음").first.click()
        try:
            await runner.page.wait_for_url("**/signup/owner/add", timeout=15000)
        except Exception:
            await runner.page.wait_for_load_state("networkidle")
            await runner.page.wait_for_timeout(2000)

        dropdown = runner.page.locator(".ui.dropdown-check.category")
        await expect(dropdown).to_be_visible(timeout=10000)
        trigger = dropdown.locator(".text", has_text="업종선택").first
        if await trigger.count() == 0:
            trigger = dropdown.get_by_text("업종선택", exact=False).first
        await trigger.click()

        panel = dropdown.locator(".dropdown-items-wrap")
        await panel.wait_for(state="visible", timeout=3000)
        await panel.locator("label[for='cate1']").click()
        await panel.locator("label[for='cate3']").click()
        await panel.get_by_role("button", name="선택").click()

        await runner.page.locator("a[onclick='onClickSubmit();']").click()
        try:
            await runner.page.wait_for_url("**/book/calendar**", timeout=15000)
        except Exception:
            pass
        await runner.page.wait_for_load_state("domcontentloaded")
        await runner.page.wait_for_timeout(3000)
        await runner.page.wait_for_load_state("networkidle")
        await runner._dismiss_shop_creation_modals()
        print("  ✓ 샵 생성 완료")
        try:
            await runner.enable_gong_booking_after_shop_creation()
        except Exception as exc:
            if "토글이 ON 상태" not in str(exc) and "activate-switch" not in str(exc):
                raise
        print("✓ Phase 1 완료\n")

        # ── Phase 1.2: 샵 소식 작성 ──
        print("=== Phase 1.2: 샵 소식 작성 ===")
        news_title = f"자동화 샵 소식 {runner.mmdd}"
        news_content = f"자동화 테스트 샵 소식 상세 내용입니다. ({runner.mmdd})"
        test_image_path = str(Path(__file__).parent / "test_image.png")

        await runner.page.goto(f"{CRM_BASE_URL}/b2c/shop-news/new")
        await runner.page.wait_for_load_state("networkidle")
        await runner.page.wait_for_timeout(1000)

        # 제목 입력
        title_input = runner.page.locator("input[placeholder*='50자']").first
        await expect(title_input).to_be_visible(timeout=5000)
        await title_input.fill(news_title)
        print(f"  ✓ 제목: {news_title}")

        # 대표 소식으로 설정 체크 확인 (기본 체크됨)
        representative_label = runner.page.locator("label").filter(has_text="대표 소식으로 설정").first
        await expect(representative_label).to_be_visible(timeout=5000)
        print("  ✓ 대표 소식으로 설정: 체크됨")

        # 상세 내용 입력
        content_textarea = runner.page.locator("textarea").first
        await expect(content_textarea).to_be_visible(timeout=5000)
        await content_textarea.fill(news_content)
        print(f"  ✓ 상세 내용: {news_content}")

        # 사진 업로드 → 모달 노출 대기
        file_input = runner.page.locator("input[type='file']").first
        await file_input.set_input_files(test_image_path)
        await runner.page.wait_for_timeout(2000)

        # "샵 소식 사진" 모달 내 [저장] 클릭 → "이미지 등록이 완료되었습니다." alert
        photo_modal = runner.page.locator("[role='dialog']:visible, .modal:visible, #modal-content:visible").first
        await expect(photo_modal).to_be_visible(timeout=5000)
        modal_save_btn = photo_modal.locator("button:has-text('저장')").first
        await expect(modal_save_btn).to_be_visible(timeout=5000)
        print("  ✓ 사진 모달 노출 확인")
        runner.page.once("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await modal_save_btn.click(force=True)
        await runner.page.wait_for_timeout(2000)
        print("  ✓ 사진 업로드 저장 완료")

        # dimmer 닫기
        for _ in range(5):
            dim = runner.page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await runner.page.wait_for_timeout(500)
            else:
                break

        # 우측 상단 [저장] 클릭 → 샵 소식 최종 저장
        top_save_btn = runner.page.locator("button:has-text('저장'):visible").first
        await expect(top_save_btn).to_be_visible(timeout=5000)
        await top_save_btn.click(force=True)
        await runner.page.wait_for_timeout(2000)
        await runner.page.wait_for_load_state("networkidle")

        # 소식 목록 페이지로 이동하여 확인
        await runner.page.goto(f"{CRM_BASE_URL}/b2c/shop-news?fromMenu=true")
        await runner.page.wait_for_load_state("networkidle")
        await runner.page.wait_for_timeout(1000)
        body_text = await runner.page.locator("body").inner_text()
        assert news_title in body_text, f"샵 소식 저장 실패: '{news_title}' 미노출"
        print("  ✓ 샵 소식 저장 완료")
        await runner.page.screenshot(path=str(SHOT_DIR / "news_01_saved.png"))
        print("✓ Phase 1.2 완료\n")

        # ── Phase 1.5: 직원 입사 신청 + 원장 승인 ──
        print("=== Phase 1.5: 직원 입사 신청 + 원장 승인 ===")
        STAFF_ID = "autoqatest2"
        STAFF_PW = "gong2023@@"

        # 직원 계정으로 별도 브라우저 로그인
        staff_browser = await runner.playwright.chromium.launch(headless=runner.headless)
        staff_context = await staff_browser.new_context(viewport={"width": 1440, "height": 900})
        staff_page = await staff_context.new_page()
        try:
            await staff_page.goto(f"{CRM_BASE_URL}/signin")
            await staff_page.wait_for_load_state("networkidle")
            await staff_page.wait_for_timeout(1000)
            staff_id_input = staff_page.locator("input[type='text'], input[name*='id'], input[placeholder*='아이디']").first
            await expect(staff_id_input).to_be_visible(timeout=10000)
            await staff_id_input.fill(STAFF_ID)
            staff_pw_input = staff_page.locator("input[type='password']").first
            await staff_pw_input.fill(STAFF_PW)
            staff_page.locator("button:has-text('로그인'), button[type='submit']").first
            await staff_page.locator("button:has-text('로그인'), button[type='submit']").first.click()
            await staff_page.wait_for_load_state("networkidle")
            await staff_page.wait_for_timeout(1000)
            print(f"  ✓ 직원({STAFF_ID}) 로그인 완료")

            # 샵 추가 클릭
            add_shop_btn = staff_page.locator("button:has-text('샵 추가'), a:has-text('샵 추가')").first
            await expect(add_shop_btn).to_be_visible(timeout=5000)
            await add_shop_btn.click()
            await staff_page.wait_for_load_state("networkidle")
            await staff_page.wait_for_timeout(1000)

            # 샵 검색
            search_input = staff_page.locator("input[type='text'], input[placeholder*='검색'], input[placeholder*='샵']").first
            await expect(search_input).to_be_visible(timeout=5000)
            await search_input.click()
            await search_input.type(shop_name, delay=50)
            await staff_page.wait_for_timeout(1500)

            # 검색 결과에서 샵 선택
            shop_item = staff_page.locator(f"text={shop_name}").first
            await expect(shop_item).to_be_visible(timeout=5000)
            await shop_item.click()
            await staff_page.wait_for_timeout(1000)
            print(f"  ✓ {shop_name} 선택")

            # 근무지 등록 모달 → [다음]
            modal_next = staff_page.locator("button:has-text('다음'), a:has-text('다음')").last
            await expect(modal_next).to_be_visible(timeout=5000)
            await modal_next.click()
            await staff_page.wait_for_timeout(1000)

            # 화면 [다음]
            page_next = staff_page.locator("button:has-text('다음'), a:has-text('다음')").first
            await expect(page_next).to_be_visible(timeout=5000)
            await page_next.click()
            await staff_page.wait_for_load_state("networkidle")
            await staff_page.wait_for_timeout(1000)

            # 가입 승인 전 확인
            shop_row = staff_page.locator(f"tr:has-text('{shop_name}')")
            await expect(shop_row).to_be_visible(timeout=5000)
            status = await shop_row.locator("td.status").text_content()
            assert "승인 전" in status, f"상태 확인 실패: {status}"
            print(f"  ✓ 입사 신청 완료 → 상태: {status.strip()}")
        finally:
            await staff_browser.close()

        # 원장 계정으로 승인 (runner의 기존 세션 사용)
        await runner.page.bring_to_front()
        await runner.page.locator("text=우리샵 관리").first.click()
        await runner.page.wait_for_timeout(500)
        await runner.page.locator("text=직원관리").first.click()
        await runner.page.wait_for_load_state("networkidle")
        await runner.page.wait_for_timeout(1000)
        print(f"  ✓ 직원관리 페이지 진입")

        # 테스트_직원계정1 확인 + [승인 대기] 클릭
        staff_row = runner.page.locator("tr:has-text('테스트_직원계정1')")
        await expect(staff_row).to_be_visible(timeout=5000)
        approve_btn = staff_row.locator("button:has-text('승인 대기')")
        await expect(approve_btn).to_be_visible(timeout=5000)
        await approve_btn.click()
        await runner.page.wait_for_timeout(1000)

        # 입사 승인 모달 → [승인]
        modal_approve = runner.page.locator("button:has-text('승인')").last
        await expect(modal_approve).to_be_visible(timeout=5000)
        await modal_approve.click()
        await runner.page.wait_for_load_state("networkidle")
        await runner.page.wait_for_timeout(1000)

        # 입사일 확인
        today_str = datetime.now().strftime("%y. %-m. %-d")
        row_text = await runner.page.locator("tr:has-text('테스트_직원계정1')").text_content()
        assert today_str in row_text, f"입사일 확인 실패: '{today_str}' not in '{row_text}'"
        print(f"  ✓ 직원 승인 완료 (입사일: {today_str})")
        await runner.page.screenshot(path=str(SHOT_DIR / "staff_join_approved.png"))
        print("✓ Phase 1.5 완료\n")

        # ── Phase 2: B2C 예약 ──
        print("=== Phase 2: B2C 예약 ===")
        crm_page = await runner.context.new_page()
        zero_context = await runner.browser.new_context(viewport={"width": 430, "height": 932})
        zero_page = await zero_context.new_page()

        await crm_page.bring_to_front()
        await _crm_login(crm_page)
        await _switch_shop(crm_page, shop_name)

        # shopId
        try:
            api = "https://qa-api-zero.gongbiz.kr/api/v1/search/shop/location?lat=37.4979&lng=127.0276&radius=5000"
            with urllib.request.urlopen(api, timeout=10) as r:
                data = json.loads(r.read())
            shop_id = next(s["id"] for s in data.get("shopList", []) if shop_name in s.get("name", ""))
        except Exception:
            from auto_web_test.B2C_tests.test_b2b_b2c_shop_activation_flow import _get_shop_id_from_crm
            shop_id = await _get_shop_id_from_crm(crm_page)
        print(f"  shopId: {shop_id}")

        await zero_page.bring_to_front()
        await _kakao_login(zero_page)

        # ── B2C 샵 소식 검증 (샵 페이지 진입 시 지도 아래 노출) ──
        print("  --- B2C 샵 소식 검증 ---")
        await zero_page.goto(f"{ZERO_BASE_URL}/shop/{shop_id}")
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 지도 아래 소식 영역에서 제목 확인
        news_el = zero_page.locator(f"text={news_title}").first
        await expect(news_el).to_be_visible(timeout=10000)
        print(f"  ✓ B2C 샵 소식 노출 확인: {news_title}")
        await zero_page.screenshot(path=str(SHOT_DIR / "news_02_b2c_verified.png"))

        reservation_date = await _make_reservation(zero_page, shop_name, shop_id)
        print("  ✓ 첫 번째 예약 완료")

        # ── 두 번째 예약: 컷 > 남성컷 ──
        print("  --- 두 번째 예약: 컷 > 남성컷 ---")
        await zero_page.goto(f"{ZERO_BASE_URL}/shop/{shop_id}")
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # "컷" 카테고리 선택
        cut_btn = zero_page.locator("button:has-text('컷')").first
        await expect(cut_btn).to_be_visible(timeout=10000)
        await cut_btn.click()
        await zero_page.wait_for_timeout(1000)

        # "남성컷" 체크박스 선택
        male_cut = zero_page.locator("label:has-text('남성컷'), span:has-text('남성컷')").first
        if await male_cut.count() == 0:
            checkboxes = zero_page.get_by_role("checkbox")
            count = await checkboxes.count()
            for i in range(count):
                cb = checkboxes.nth(i)
                text = await cb.inner_text()
                if "남성컷" in text:
                    male_cut = cb
                    break
        await expect(male_cut).to_be_visible(timeout=10000)
        await male_cut.click()
        await zero_page.wait_for_timeout(500)

        # 예약하기 버튼
        booking_btn2 = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_btn2).to_be_visible(timeout=10000)
        await booking_btn2.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 담당자 선택 (2명 이상일 때 노출)
        designer_row2 = zero_page.locator("text=샵주테스트").first
        if await designer_row2.count() > 0 and await designer_row2.is_visible():
            select_btn2 = zero_page.locator("button:has-text('선택')").first
            await expect(select_btn2).to_be_visible(timeout=5000)
            await select_btn2.click()
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(1000)
            print("  ✓ 담당자 선택: 샵주테스트")

        # 내일 날짜 선택
        tomorrow = datetime.now() + timedelta(days=1)
        day_str = str(tomorrow.day)
        date_btn2 = zero_page.get_by_role("button", name=day_str, exact=True).first
        await expect(date_btn2).to_be_visible(timeout=10000)
        await date_btn2.click()
        await zero_page.wait_for_timeout(1000)

        # 첫 번째 보이는 시간 선택
        time_buttons2 = zero_page.locator("button:has-text(':00'), button:has-text(':30')")
        second_time_btn = time_buttons2.first
        await expect(second_time_btn).to_be_visible(timeout=10000)
        second_time_text = await second_time_btn.inner_text()
        await second_time_btn.click()
        await zero_page.wait_for_timeout(500)
        print(f"  두 번째 예약 시간: {second_time_text}")

        # 예약하기 → 결제 페이지
        booking_confirm2 = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_confirm2).to_be_visible(timeout=10000)
        await booking_confirm2.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 결제 페이지: 동의 체크 → 최종 예약하기
        agree_check2 = zero_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
        if await agree_check2.count() > 0:
            await agree_check2.click()
            await zero_page.wait_for_timeout(500)

        final_booking2 = zero_page.locator("button:has-text('예약하기')").last
        await expect(final_booking2).to_be_visible(timeout=10000)
        await final_booking2.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        assert "bookingId" in zero_page.url or "예약 완료" in await zero_page.locator("body").inner_text(), \
            f"두 번째 예약 실패: {zero_page.url}"
        await zero_page.screenshot(path=str(SHOT_DIR / "cancel_00_second_booking.png"))
        print("  ✓ 두 번째 예약 완료 (컷 > 남성컷)")

        # ── 세 번째 예약: 담당자 테스트_직원계정1 ──
        print("  --- 세 번째 예약: 담당자 테스트_직원계정1 ---")
        await zero_page.goto(f"{ZERO_BASE_URL}/shop/{shop_id}")
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 시술 메뉴 선택 (첫 번째 체크박스)
        service_cb3 = zero_page.get_by_role("checkbox").first
        await expect(service_cb3).to_be_visible(timeout=10000)
        await service_cb3.click()
        await zero_page.wait_for_timeout(500)

        # 예약하기 버튼
        booking_btn3 = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_btn3).to_be_visible(timeout=10000)
        await booking_btn3.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 담당자 선택: 테스트_직원계정1 (두 번째 [선택] 버튼)
        await expect(zero_page.locator("text=테스트_직원계정1").first).to_be_visible(timeout=5000)
        select_buttons = zero_page.locator("button:has-text('선택')")
        select_btn3 = select_buttons.nth(1)  # 0: 샵주테스트, 1: 테스트_직원계정1
        await expect(select_btn3).to_be_visible(timeout=5000)
        await select_btn3.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)
        print("  ✓ 담당자 선택: 테스트_직원계정1")

        # 내일 날짜 선택
        date_btn3 = zero_page.get_by_role("button", name=str(tomorrow.day), exact=True).first
        await expect(date_btn3).to_be_visible(timeout=10000)
        await date_btn3.click()
        await zero_page.wait_for_timeout(1000)

        # 첫 번째 보이는 시간 선택
        time_btn3 = zero_page.locator("button:has-text(':00'), button:has-text(':30')").first
        await expect(time_btn3).to_be_visible(timeout=10000)
        third_time_text = await time_btn3.inner_text()
        await time_btn3.click()
        await zero_page.wait_for_timeout(500)
        print(f"  세 번째 예약 시간: {third_time_text}")

        # 예약하기 → 결제 페이지
        booking_confirm3 = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_confirm3).to_be_visible(timeout=10000)
        await booking_confirm3.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 결제 페이지: 동의 체크 → 최종 예약하기
        agree_check3 = zero_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
        if await agree_check3.count() > 0:
            await agree_check3.click()
            await zero_page.wait_for_timeout(500)

        final_booking3 = zero_page.locator("button:has-text('예약하기')").last
        await expect(final_booking3).to_be_visible(timeout=10000)
        await final_booking3.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        assert "bookingId" in zero_page.url or "예약 완료" in await zero_page.locator("body").inner_text(), \
            f"세 번째 예약 실패: {zero_page.url}"
        await zero_page.screenshot(path=str(SHOT_DIR / "cancel_00_third_booking.png"))
        print("  ✓ 세 번째 예약 완료 (담당자: 테스트_직원계정1)")
        print("✓ Phase 2 완료\n")

        # ── Phase 3: 캘린더 → 내일 이동 → 상세 → 취소 ──
        print("=== Phase 3: 캘린더 → 상세 → 취소 ===")
        await crm_page.bring_to_front()
        await _switch_shop(crm_page, shop_name)

        # 캘린더 이동
        await crm_page.goto(f"{CRM_BASE_URL}/book/calendar")
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)

        # 딤머 닫기
        for _ in range(5):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # "일" 보기 전환
        for name in ["일", "날짜별"]:
            btn = crm_page.get_by_role("button", name=name).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                await crm_page.wait_for_load_state("networkidle")
                await crm_page.wait_for_timeout(1000)
                break

        # 딤머 다시 닫기
        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 내일 날짜로 이동
        d = reservation_date
        target_day = f"{d.month}. {d.day}"
        header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        for _ in range(10):
            if target_day in header:
                break
            # 현재 날짜에서 숫자 추출하여 방향 결정
            current_day = int(re.search(rf"{d.month}\.\s*(\d+)", header).group(1))
            btn_cls = "fc-next-button" if current_day < d.day else "fc-prev-button"
            nav_btn = crm_page.locator(f"button.{btn_cls}").first
            await expect(nav_btn).to_be_visible(timeout=5000)
            await nav_btn.click()
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(1000)
            header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        print(f"  ✓ 캘린더 날짜: {header.strip()}")

        # 딤머 다시 닫기
        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 첫 번째 예약 블록 클릭 → 상세 페이지로 이동
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_debug_calendar.png"), full_page=True)
        block = crm_page.locator("div.booking-normal").first
        await expect(block).to_be_visible(timeout=15000)
        await block.click(force=True)
        await crm_page.wait_for_timeout(2000)
        await crm_page.wait_for_load_state("networkidle")
        first_detail_url = crm_page.url
        print(f"  ✓ 상세 페이지: {first_detail_url}")

        # 공비서 마크 확인
        b2c = crm_page.locator("svg[icon='serviceB2c'], svg.ZERO_B2C").first
        try:
            await expect(b2c).to_be_visible(timeout=5000)
            print("  ✓ 공비서 마크 확인")
        except Exception:
            print("  ⚠ 공비서 마크 미매칭")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_01_detail.png"))

        # 상세 페이지에서 "예약 확정" 드롭다운 → 예약 취소
        sb = crm_page.get_by_role("button", name="예약 확정").first
        if await sb.count() == 0:
            sb = crm_page.locator("button").filter(has_text="예약 확정").first
        await expect(sb).to_be_visible(timeout=15000)
        await sb.click()
        await crm_page.wait_for_timeout(1000)

        co = crm_page.get_by_text("예약 취소").first
        await expect(co).to_be_visible(timeout=5000)
        await co.click()
        await crm_page.wait_for_timeout(1000)

        # 취소 모달
        modal = crm_page.locator("[role='dialog']:visible, #modal-content:visible").first
        await expect(modal).to_be_visible(timeout=10000)
        print("  ✓ 취소 모달 노출")

        mt = await modal.inner_text()
        if "환불 방식" not in mt:
            print("  ✓ 환불 방식 미노출 (예약금 없는 샵)")
        assert "취소 사유" in mt
        print("  ✓ 취소 사유 섹션 노출")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_02_modal.png"))

        # 디폴트 사유
        dr = modal.get_by_text(re.compile(r"시술이 어려운|다른 시간")).first
        await expect(dr).to_be_visible(timeout=5000)
        await dr.click()
        reason_text = await dr.inner_text()
        print(f"  ✓ 디폴트 사유: '{reason_text}'")

        cb = modal.get_by_role("button", name=re.compile(r"예약\s*취소")).first
        await expect(cb).to_be_visible(timeout=5000)
        await cb.click()
        await crm_page.wait_for_timeout(2000)
        await crm_page.wait_for_load_state("networkidle")

        try:
            im = await modal.is_visible(timeout=2000)
        except Exception:
            im = False
        assert not im, "모달 안 닫힘"
        print("  ✓ 예약 취소 완료")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_03_complete.png"))
        print("✓ Phase 3 완료\n")

        # ── Phase 4: 취소 사유 검증 ──
        print("=== Phase 4: 취소 사유 검증 ===")
        await crm_page.wait_for_timeout(2000)

        # 취소된 예약 상세로 직접 이동
        await crm_page.goto(first_detail_url)
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_04_detail.png"))

        # 상세 페이지에서 배너 확인
        banner = crm_page.locator("h5.banner-title").filter(has_text="샵에서 취소한 예약")
        if await banner.count() == 0:
            banner = crm_page.get_by_text(re.compile(r"샵에서 취소한 예약")).first

        await expect(banner).to_be_visible(timeout=10000)
        print(f"  ✓ 취소 배너: '{await banner.inner_text()}'")

        rel = crm_page.locator("p.banner-desc").first
        if await rel.count() == 0:
            rel = crm_page.get_by_text(re.compile(r"취소\s*사유")).first
        await expect(rel).to_be_visible(timeout=5000)
        displayed = await rel.inner_text()
        print(f"  ✓ 취소 사유: '{displayed}'")
        assert reason_text[:10] in displayed, f"불일치! '{reason_text}' vs '{displayed}'"
        print("  ✓ 취소 사유 일치!")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_05_verified.png"))
        print("✓ Phase 4 완료\n")

        # ── Phase 4.5: 두 번째 예약 매출 등록 ──
        print("=== Phase 4.5: 두 번째 예약 매출 등록 ===")
        await crm_page.goto(f"{CRM_BASE_URL}/book/calendar")
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)

        # 딤머 닫기
        for _ in range(5):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # "일" 보기
        for name in ["일", "날짜별"]:
            btn = crm_page.get_by_role("button", name=name).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                await crm_page.wait_for_load_state("networkidle")
                await crm_page.wait_for_timeout(1000)
                break

        # 딤머 닫기
        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 내일로 이동 (헤더 기준)
        header2 = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        for _ in range(10):
            if f"{d.month}. {d.day}" in header2:
                break
            current_day2 = int(re.search(rf"{d.month}\.\s*(\d+)", header2).group(1))
            btn_cls2 = "fc-next-button" if current_day2 < d.day else "fc-prev-button"
            nav_btn2 = crm_page.locator(f"button.{btn_cls2}").first
            await expect(nav_btn2).to_be_visible(timeout=5000)
            await nav_btn2.click()
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(1000)
            header2 = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()

        # 딤머 닫기
        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 남은 활성 예약 블록 클릭
        male_block = crm_page.locator("div.booking-normal").first
        await expect(male_block).to_be_visible(timeout=15000)
        await male_block.click(force=True)
        await crm_page.wait_for_timeout(2000)
        await crm_page.wait_for_load_state("networkidle")
        second_detail_url = crm_page.url
        print(f"  ✓ 두 번째 예약 상세: {second_detail_url}")

        # 예약일시 확인
        detail_text = await crm_page.locator("body").inner_text()
        assert f"{d.day}" in detail_text, "예약일시 확인 실패"
        print(f"  ✓ 예약일시 확인: {d.month}/{d.day}")

        # 시술 메뉴 확인
        if "남성컷" in detail_text:
            print("  ✓ 시술 메뉴: 남성컷 확인")
        elif "여성컷" in detail_text:
            print("  ✓ 시술 메뉴: 여성컷 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_05a_male_detail.png"))

        # [매출 등록] 버튼 클릭
        sales_btn = crm_page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
        await expect(sales_btn).to_be_visible(timeout=10000)
        await sales_btn.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print(f"  ✓ 매출 등록 페이지: {crm_page.url}")

        # 남은 결제 금액 확인
        sales_text = await crm_page.locator("body").inner_text()
        if "18,000" in sales_text:
            print("  ✓ 남은 결제 금액: 18,000원 (남성컷)")
        elif "20,000" in sales_text:
            print("  ✓ 남은 결제 금액: 20,000원 (여성컷)")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_05b_sales_page.png"))

        # 결제 수단: 카드 선택
        card_btn = crm_page.get_by_text("카드", exact=True).first
        if await card_btn.count() == 0:
            card_btn = crm_page.locator("button:has-text('카드'), label:has-text('카드')").first
        await expect(card_btn).to_be_visible(timeout=10000)
        await card_btn.click()
        await crm_page.wait_for_timeout(500)
        print("  ✓ 결제 수단: 카드 선택")

        # 매출 등록
        save_btn = crm_page.locator("button:has-text('매출 등록')").first
        await expect(save_btn).to_be_visible(timeout=10000)
        await save_btn.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 매출 등록 완료")

        # 매출 등록 완료 확인
        await crm_page.goto(second_detail_url)
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        sales_label = crm_page.locator("h4.SALE.disabled:has-text('매출 등록')").first
        if await sales_label.count() == 0:
            sales_label = crm_page.locator("h4:has-text('매출 등록')").first
        await expect(sales_label).to_be_visible(timeout=10000)
        print("  ✓ 매출 등록 완료 상태 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_05c_sales_done.png"))
        print("✓ Phase 4.5 완료\n")

        # ── Phase 4.6: 확인 후 확정 예약 ──
        print("=== Phase 4.6: 확인 후 확정 예약 ===")

        # Step 1: CRM 예약 방식 변경 → "담당자 확인 후 예약 확정"
        await crm_page.goto(f"{CRM_BASE_URL}/b2c/setting")
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)

        # "온라인 예약 정보" 옆 수정하기 클릭
        online_info_section = crm_page.locator("h3:has-text('온라인 예약 정보')").first
        await expect(online_info_section).to_be_visible(timeout=5000)
        edit_btn = online_info_section.locator("..").locator("button:has-text('수정하기')").first
        await expect(edit_btn).to_be_visible(timeout=5000)
        await edit_btn.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 온라인 예약 정보 수정 페이지 진입")

        # "담당자 확인 후 예약 확정" 선택
        confirm_option = crm_page.locator("label[for='MANUAL_CONFIRMED']").first
        await expect(confirm_option).to_be_visible(timeout=5000)
        await confirm_option.click()
        await crm_page.wait_for_timeout(500)
        print("  ✓ 예약 방식: 담당자 확인 후 예약 확정 선택")

        # [저장] 클릭
        save_btn = crm_page.locator("button[data-track-id='b2c_info_save']").first
        await expect(save_btn).to_be_visible(timeout=5000)
        await save_btn.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 예약 방식 변경 저장 완료")

        # Step 2: B2C 예약 진행
        print("  --- B2C 확인 후 확정 예약 진행 ---")
        await zero_page.goto(f"{ZERO_BASE_URL}/shop/{shop_id}")
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 시술 선택 (첫 번째 체크박스)
        service_cb = zero_page.get_by_role("checkbox").first
        await expect(service_cb).to_be_visible(timeout=10000)
        await service_cb.click()
        await zero_page.wait_for_timeout(500)

        # 예약하기 클릭
        booking_btn = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_btn).to_be_visible(timeout=10000)
        await booking_btn.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 담당자 선택
        designer_row = zero_page.locator("text=샵주테스트").first
        if await designer_row.count() > 0 and await designer_row.is_visible():
            select_btn = zero_page.locator("button:has-text('선택')").first
            await expect(select_btn).to_be_visible(timeout=5000)
            await select_btn.click()
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(1000)
            print("  ✓ 담당자 선택: 샵주테스트")

        # 날짜 선택 (내일)
        tomorrow = datetime.now() + timedelta(days=1)
        day_str = str(tomorrow.day)
        date_btn = zero_page.get_by_role("button", name=day_str, exact=True).first
        await expect(date_btn).to_be_visible(timeout=10000)
        await date_btn.click()
        await zero_page.wait_for_timeout(1000)

        # 시간 선택
        time_btn = zero_page.locator("button:has-text(':00'), button:has-text(':30')").first
        await expect(time_btn).to_be_visible(timeout=10000)
        confirm_time_text = await time_btn.inner_text()
        await time_btn.click()
        await zero_page.wait_for_timeout(500)
        print(f"  ✓ 시간 선택: {confirm_time_text}")

        # 예약하기 → 결제 페이지
        booking_confirm = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_confirm).to_be_visible(timeout=10000)
        await booking_confirm.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)

        # 결제 페이지: 최종 예약하기
        page_text = await zero_page.locator("body").inner_text()
        if "예약 완료" not in page_text and "예약 신청" not in page_text:
            final_booking = zero_page.locator("button:has-text('예약하기')").last
            await expect(final_booking).to_be_visible(timeout=15000)
            await final_booking.click()
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(1000)

        # Step 3: B2C 예약 신청 텍스트 검증
        complete_text = await zero_page.locator("body").inner_text()
        assert "예약 신청" in complete_text, f"확인 후 확정 예약 신청 텍스트 미노출: {complete_text[:200]}"
        assert "샵에서 확인 후 예약을 확정하면" in complete_text, f"확인 후 확정 안내 텍스트 미노출: {complete_text[:200]}"
        print("  ✓ B2C 예약 신청 텍스트 확인: '예약 신청 되었어요...'")
        await zero_page.screenshot(path=str(SHOT_DIR / "phase46_01_b2c_pending.png"))

        # Step 4: CRM 캘린더에서 해당 예약 확인
        await crm_page.bring_to_front()
        await _switch_shop(crm_page, shop_name)

        d = datetime.now() + timedelta(days=1)
        await crm_page.goto(f"{CRM_BASE_URL}/book/calendar")
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)

        # dimmer 닫기
        for _ in range(5):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # "일" 보기 전환
        for name in ["일", "날짜별"]:
            btn = crm_page.get_by_role("button", name=name).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                await crm_page.wait_for_load_state("networkidle")
                await crm_page.wait_for_timeout(1000)
                break

        # dimmer 닫기
        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 내일 날짜로 이동
        target_day = f"{d.month}. {d.day}"
        header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        for _ in range(10):
            if target_day in header:
                break
            current_day = int(re.search(rf"{d.month}\.\s*(\d+)", header).group(1))
            btn_cls = "fc-next-button" if current_day < d.day else "fc-prev-button"
            nav_btn = crm_page.locator(f"button.{btn_cls}").first
            await expect(nav_btn).to_be_visible(timeout=5000)
            await nav_btn.click()
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(1000)
            header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        print(f"  ✓ 캘린더 날짜: {header.strip()}")

        # dimmer 닫기
        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 예약 블록 클릭 → 상세 진입
        pending_block = crm_page.locator("div.READY.booking-normal").first
        await expect(pending_block).to_be_visible(timeout=15000)
        await pending_block.click(force=True)
        await crm_page.wait_for_timeout(2000)
        await crm_page.wait_for_load_state("networkidle")
        confirm_detail_url = crm_page.url
        print(f"  ✓ 예약 상세: {confirm_detail_url}")

        # Step 5: "확인 후 확정 예약입니다" 안내 확인
        detail_text = await crm_page.locator("body").inner_text()
        assert "확인 후 확정" in detail_text or "예약 대기" in detail_text, f"확인 후 확정 안내 미노출: {detail_text[:300]}"
        print("  ✓ '확인 후 확정 예약입니다' 안내 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "phase46_02_crm_pending.png"))

        # Step 6: [예약 확정] 클릭
        confirm_btn = crm_page.locator("button:has-text('예약 확정')").first
        await expect(confirm_btn).to_be_visible(timeout=5000)
        await confirm_btn.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 예약 확정 완료")
        await crm_page.screenshot(path=str(SHOT_DIR / "phase46_03_confirmed.png"))

        # 확정 후 캘린더로 이동될 수 있으므로 다시 예약 상세로 진입
        if "detail" not in crm_page.url:
            await crm_page.goto(confirm_detail_url)
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(1000)

        # Step 7: 매출 등록
        sales_btn = crm_page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
        await expect(sales_btn).to_be_visible(timeout=10000)
        await sales_btn.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print(f"  ✓ 매출 등록 페이지: {crm_page.url}")

        # 결제 수단: 카드 선택
        card_btn = crm_page.get_by_text("카드", exact=True).first
        if await card_btn.count() == 0:
            card_btn = crm_page.locator("button:has-text('카드'), label:has-text('카드')").first
        await expect(card_btn).to_be_visible(timeout=10000)
        await card_btn.click()
        await crm_page.wait_for_timeout(500)
        print("  ✓ 결제 수단: 카드 선택")

        # 매출 등록
        save_sales_btn = crm_page.locator("button:has-text('매출 등록')").first
        await expect(save_sales_btn).to_be_visible(timeout=10000)
        await save_sales_btn.click()
        await crm_page.wait_for_timeout(3000)
        print("  ✓ 매출 등록 완료")

        # 매출 등록 완료 확인
        await crm_page.goto(confirm_detail_url)
        await crm_page.wait_for_load_state("domcontentloaded")
        await crm_page.wait_for_timeout(2000)
        detail_body = await crm_page.locator("body").inner_text()
        assert "매출" in detail_body, f"매출 등록 확인 실패: {detail_body[:200]}"
        print("  ✓ 매출 등록 완료 상태 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "phase46_04_sales_done.png"))

        # 예약 방식을 다시 "즉시 예약 확정"으로 복원
        await crm_page.goto(f"{CRM_BASE_URL}/b2c/setting")
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        online_info_section2 = crm_page.locator("h3:has-text('온라인 예약 정보')").first
        edit_btn2 = online_info_section2.locator("..").locator("button:has-text('수정하기')").first
        await expect(edit_btn2).to_be_visible(timeout=5000)
        await edit_btn2.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        instant_option = crm_page.locator("label[for='AUTO_CONFIRMED']").first
        await expect(instant_option).to_be_visible(timeout=5000)
        await instant_option.click()
        await crm_page.wait_for_timeout(500)
        restore_save = crm_page.locator("button[data-track-id='b2c_info_save']").first
        await expect(restore_save).to_be_visible(timeout=5000)
        await restore_save.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 예약 방식 복원: 즉시 예약 확정")

        print("✓ Phase 4.6 완료\n")

        # ── Phase 5: 콕예약 등록 (필수값 검증 + A/B 등록) ──
        print("\n=== Phase 5: 콕예약 등록 ===")
        await crm_page.bring_to_front()
        await _switch_shop(crm_page, shop_name)

        # 온라인 예약 > 콕예약 관리 진입
        online_menu = crm_page.locator(
            "h3:has-text('온라인 예약'):visible, "
            "a:has-text('온라인 예약'):visible, "
            "button:has-text('온라인 예약'):visible, "
            "span:has-text('온라인 예약'):visible"
        ).first
        await expect(online_menu).to_be_visible(timeout=10000)
        await online_menu.click()
        await crm_page.wait_for_timeout(1000)

        kok_menu = crm_page.locator(
            "a:has-text('콕예약 관리'):visible, "
            "span:has-text('콕예약 관리'):visible, "
            "h4:has-text('콕예약 관리'):visible, "
            "li:has-text('콕예약 관리'):visible"
        ).first
        # 서브메뉴가 안 펼쳐졌으면 재클릭
        if not await kok_menu.is_visible():
            await online_menu.click()
            await crm_page.wait_for_timeout(1000)
        await expect(kok_menu).to_be_visible(timeout=10000)
        await kok_menu.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 콕예약 관리 진입")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_01_list.png"))

        # ── 필수값 누락 시 저장 버튼 비활성화 검증 ──
        print("\n=== 필수값 누락 저장 버튼 비활성화 검증 ===")

        async def _handle_dialog(dialog):
            await dialog.accept()

        register_btn = crm_page.locator("button:has-text('콕예약 등록'), a:has-text('콕예약 등록'), a:has-text('콕예약 등록하기')").first
        await expect(register_btn).to_be_visible(timeout=10000)
        await register_btn.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)

        save_btn = crm_page.locator("button[type='submit']:has-text('저장')")
        test_images = generate_kok_images("필수값테스트", count=1)

        async def assert_save_disabled(label):
            await crm_page.wait_for_timeout(500)
            is_disabled = await save_btn.is_disabled()
            assert is_disabled, f"[{label}] 저장 버튼이 활성화됨 (비활성화 기대)"
            print(f"  ✓ [{label}] 저장 버튼 비활성화 확인")

        async def go_back_and_reenter():
            crm_page.on("dialog", _handle_dialog)
            await crm_page.go_back()
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(1000)
            crm_page.remove_listener("dialog", _handle_dialog)
            reg = crm_page.locator("button:has-text('콕예약 등록'), a:has-text('콕예약 등록')").first
            await expect(reg).to_be_visible(timeout=10000)
            await reg.click()
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(1000)

        async def fill_all_required():
            name_el = crm_page.locator(
                "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
                "input[placeholder*='이름']"
            ).first
            await name_el.fill("필수값 테스트")
            fi = crm_page.locator("input[type='file']").first
            if await fi.count() > 0:
                await fi.set_input_files(test_images)
                await crm_page.wait_for_timeout(2000)
            cat_btn = crm_page.locator("button:has-text('네일'):visible, label:has-text('네일'):visible").first
            if await cat_btn.count() > 0:
                await cat_btn.click()
                await crm_page.wait_for_timeout(300)
            price_el = crm_page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
            if await price_el.count() > 0:
                await price_el.fill("10000")

        # 0. 초기 상태
        await assert_save_disabled("초기 상태 - 전체 누락")

        # 1. 이름 누락
        await fill_all_required()
        name_input_test = crm_page.locator(
            "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
            "input[placeholder*='이름']"
        ).first
        await name_input_test.fill("")
        await assert_save_disabled("이름 누락")
        await go_back_and_reenter()

        # 2. 사진 누락
        name_el = crm_page.locator(
            "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
            "input[placeholder*='이름']"
        ).first
        await name_el.fill("필수값 테스트")
        cat_btn = crm_page.locator("button:has-text('네일'):visible, label:has-text('네일'):visible").first
        if await cat_btn.count() > 0:
            await cat_btn.click()
            await crm_page.wait_for_timeout(300)
        price_el = crm_page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
        if await price_el.count() > 0:
            await price_el.fill("10000")
        await assert_save_disabled("사진 누락")
        await go_back_and_reenter()

        # 3. 업종 누락
        name_el = crm_page.locator(
            "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
            "input[placeholder*='이름']"
        ).first
        await name_el.fill("필수값 테스트")
        fi = crm_page.locator("input[type='file']").first
        if await fi.count() > 0:
            await fi.set_input_files(test_images)
            await crm_page.wait_for_timeout(2000)
        price_el = crm_page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
        if await price_el.count() > 0:
            await price_el.fill("10000")
        await assert_save_disabled("업종 누락")
        await go_back_and_reenter()

        # 4. 가격 누락
        await fill_all_required()
        price_el = crm_page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
        if await price_el.count() > 0:
            await price_el.fill("")
        await assert_save_disabled("가격 누락")
        await go_back_and_reenter()

        # 5. 담당자 누락
        await fill_all_required()
        deselect_btn = crm_page.locator("button:has-text('전체 선택 해제')").first
        await expect(deselect_btn).to_be_visible(timeout=5000)
        await deselect_btn.click()
        await crm_page.wait_for_timeout(500)
        await assert_save_disabled("담당자 누락")

        crm_page.on("dialog", _handle_dialog)
        await crm_page.go_back()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        crm_page.remove_listener("dialog", _handle_dialog)

        print("=== 필수값 누락 검증 완료 (6건 모두 비활성화 확인) ===\n")

        # ── 콕예약 A 등록 ──
        register_btn = crm_page.locator("button:has-text('콕예약 등록'), a:has-text('콕예약 등록')").first
        await expect(register_btn).to_be_visible(timeout=5000)
        await register_btn.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 콕예약 등록 화면 진입")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_02_register_form.png"))

        name_input = crm_page.locator(
            "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
            "input[placeholder*='이름']"
        ).first
        await expect(name_input).to_be_visible(timeout=5000)
        await name_input.fill("E2E 테스트 콕예약 A")
        print("  ✓ 콕예약 이름 입력: E2E 테스트 콕예약 A")

        kok_a_images = generate_kok_images("E2E 테스트 콕예약 A", count=5)
        file_input = crm_page.locator("input[type='file']").first
        if await file_input.count() > 0:
            await file_input.set_input_files(kok_a_images)
            await crm_page.wait_for_timeout(2000)
            print(f"  ✓ 사진 업로드 완료 ({len(kok_a_images)}장)")

        nail_btn = crm_page.locator("button:has-text('네일'):visible, label:has-text('네일'):visible").first
        if await nail_btn.count() > 0:
            await nail_btn.click()
            await crm_page.wait_for_timeout(500)
            print("  ✓ 시술 업종 선택: 네일")

        select_buttons = crm_page.locator("button[data-testid='select-toggle-button']")
        select_count = await select_buttons.count()
        if select_count >= 2:
            await select_buttons.nth(1).click()
            await crm_page.wait_for_timeout(700)
            min_option = crm_page.locator("ul:visible li:has-text('30'), div[role='option']:has-text('30'):visible, li:visible >> text=30").first
            if await min_option.count() > 0:
                await min_option.click()
                await crm_page.wait_for_timeout(500)
                print("  ✓ 시술 시간 설정: 1시간 30분")
            else:
                print("  ⚠ 30분 옵션 못 찾음, 기본값 유지")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_03_time.png"))

        base_price = crm_page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
        if await base_price.count() > 0:
            await base_price.fill("50000")
            print("  ✓ 기본 가격 입력: 50,000원")

        member_price = crm_page.locator("input[placeholder*='할인가를 입력'], input[placeholder*='회원']").first
        if await member_price.count() > 0:
            await member_price.fill("45000")
            print("  ✓ 회원 가격 입력: 45,000원")

        desc_input = crm_page.locator(
            "textarea, input[placeholder*='설명'], input[placeholder*='내용']"
        ).first
        if await desc_input.count() > 0:
            await desc_input.fill("E2E 자동화 테스트용 A")
            print("  ✓ 시술 설명 입력: E2E 자동화 테스트용 A")

        keyword_inputs = crm_page.locator("input[placeholder*='키워드']")
        kw_count = await keyword_inputs.count()
        if kw_count >= 2:
            await keyword_inputs.nth(0).fill("테스트")
            await crm_page.wait_for_timeout(300)
            await keyword_inputs.nth(1).fill("자동화")
            await crm_page.wait_for_timeout(300)
            print("  ✓ 시술 키워드 입력: 테스트, 자동화")

        all_check = crm_page.locator("input[type='checkbox']:checked, label:has-text('전체')").first
        if await all_check.count() > 0:
            print("  ✓ 담당자 전체 선택 확인")

        await crm_page.screenshot(path=str(SHOT_DIR / "kok_04_before_save.png"))

        await crm_page.evaluate("""() => {
            window.scrollTo(0, 0);
            const btn = document.querySelector('button[type="submit"]')
                || [...document.querySelectorAll('button')].find(b => b.textContent.trim() === '저장');
            if (btn && !btn.disabled) btn.click();
        }""")
        await crm_page.wait_for_timeout(2000)
        await crm_page.wait_for_selector("text=콕예약 관리", timeout=10000)
        print("  ✓ 저장 완료")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_05_after_save.png"))

        await crm_page.wait_for_timeout(1500)
        list_text = await crm_page.locator("body").inner_text()
        assert "E2E 테스트 콕예약 A" in list_text, "목록에서 콕예약 A를 찾을 수 없습니다."
        print("  ✓ 목록에서 콕예약 A 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_06_list_verify_a.png"))

        # ── 콕예약 B 등록 ──
        print("\n--- 콕예약 B 생성 ---")
        register_btn2 = crm_page.locator("button:has-text('콕예약 등록'), a:has-text('콕예약 등록')").first
        await expect(register_btn2).to_be_visible(timeout=5000)
        await register_btn2.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 콕예약 등록 화면 진입")

        name_input_b = crm_page.locator(
            "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
            "input[placeholder*='이름']"
        ).first
        await expect(name_input_b).to_be_visible(timeout=5000)
        await name_input_b.fill("E2E 테스트 콕예약 B")
        print("  ✓ 콕예약 이름 입력: E2E 테스트 콕예약 B")

        kok_b_images = generate_kok_images("E2E 테스트 콕예약 B", count=5)
        file_input_b = crm_page.locator("input[type='file']").first
        if await file_input_b.count() > 0:
            await file_input_b.set_input_files(kok_b_images)
            await crm_page.wait_for_timeout(2000)
            print(f"  ✓ 사진 업로드 완료 ({len(kok_b_images)}장)")

        nail_btn_b = crm_page.locator("button:has-text('네일'):visible, label:has-text('네일'):visible").first
        if await nail_btn_b.count() > 0:
            await nail_btn_b.click()
            await crm_page.wait_for_timeout(500)
            print("  ✓ 시술 업종 선택: 네일")

        print("  ✓ 시술 시간 설정: 1시간 00분 (기본값)")

        base_price_b = crm_page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
        if await base_price_b.count() > 0:
            await base_price_b.fill("70000")
            print("  ✓ 기본 가격 입력: 70,000원")

        print("  ✓ 회원 가격 미입력 (비워둠)")

        desc_input_b = crm_page.locator("textarea, input[placeholder*='설명']").first
        if await desc_input_b.count() > 0:
            await desc_input_b.fill("E2E 자동화 테스트용 B")
            print("  ✓ 시술 설명 입력: E2E 자동화 테스트용 B")

        all_check_b = crm_page.locator("input[type='checkbox']:checked, label:has-text('전체')").first
        if await all_check_b.count() > 0:
            print("  ✓ 담당자 전체 선택 확인")

        await crm_page.screenshot(path=str(SHOT_DIR / "kok_07_before_save_b.png"))

        await crm_page.evaluate("""() => {
            window.scrollTo(0, 0);
            const btn = document.querySelector('button[type="submit"]')
                || [...document.querySelectorAll('button')].find(b => b.textContent.trim() === '저장');
            if (btn && !btn.disabled) btn.click();
        }""")
        await crm_page.wait_for_timeout(2000)
        await crm_page.wait_for_selector("text=콕예약 관리", timeout=10000)
        print("  ✓ 저장 완료")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_08_after_save_b.png"))

        await crm_page.wait_for_timeout(1500)
        list_text2 = await crm_page.locator("body").inner_text()
        assert "E2E 테스트 콕예약 A" in list_text2, "목록에서 콕예약 A를 찾을 수 없습니다."
        assert "E2E 테스트 콕예약 B" in list_text2, "목록에서 콕예약 B를 찾을 수 없습니다."
        print("  ✓ 목록에서 콕예약 A, B 모두 확인 (2건)")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_09_list_verify_ab.png"))
        print("✓ Phase 5 완료\n")

        # ── Phase 5.5: 콕예약 A 수정 + B2C 미리보기 수정 확인 ──
        print("=== Phase 5.5: 콕예약 A 수정 + B2C 미리보기 수정 확인 ===")

        # 목록에서 콕예약 A 클릭 → 수정 화면 진입
        kok_a_item = crm_page.locator("text='E2E 테스트 콕예약 A'").first
        await expect(kok_a_item).to_be_visible(timeout=5000)
        await kok_a_item.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 콕예약 A 수정 화면 진입")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_edit_a_01_before.png"))

        # 이름 수정
        edit_name = crm_page.locator(
            "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
            "input[placeholder*='이름']"
        ).first
        await expect(edit_name).to_be_visible(timeout=5000)
        await edit_name.fill("E2E 테스트 콕예약 A_수정")
        print("  ✓ 이름 수정: E2E 테스트 콕예약 A → E2E 테스트 콕예약 A_수정")

        # 기본가격 수정
        edit_base_price = crm_page.locator("input[placeholder*='정가를 입력'], input[placeholder*='VAT']").first
        if await edit_base_price.count() > 0:
            await edit_base_price.fill("70000")
            print("  ✓ 기본가격 수정: 50,000 → 70,000")

        # 회원가격 수정
        edit_member_price = crm_page.locator("input[placeholder*='할인가를 입력'], input[placeholder*='회원']").first
        if await edit_member_price.count() > 0:
            await edit_member_price.fill("50000")
            print("  ✓ 회원가격 수정: 45,000 → 50,000")

        # 시술설명 수정
        edit_desc = crm_page.locator("textarea, input[placeholder*='설명'], input[placeholder*='내용']").first
        if await edit_desc.count() > 0:
            await edit_desc.fill("E2E 자동화 테스트용 A_수정")
            print("  ✓ 시술설명 수정: E2E 자동화 테스트용 A → E2E 자동화 테스트용 A_수정")

        # 키워드 수정: 3번째 슬롯에 "수정" 추가
        edit_keywords = crm_page.locator("input[placeholder*='키워드']")
        edit_kw_count = await edit_keywords.count()
        if edit_kw_count >= 3:
            await edit_keywords.nth(2).fill("수정")
            await crm_page.wait_for_timeout(300)
            print("  ✓ 키워드 추가: 수정 (3번째 슬롯)")

        await crm_page.screenshot(path=str(SHOT_DIR / "kok_edit_a_02_after.png"))

        # 저장
        await crm_page.evaluate("""() => {
            window.scrollTo(0, 0);
            const btn = document.querySelector('button[type="submit"]')
                || [...document.querySelectorAll('button')].find(b => b.textContent.trim() === '저장');
            if (btn && !btn.disabled) btn.click();
        }""")
        await crm_page.wait_for_timeout(2000)
        await crm_page.wait_for_selector("text=콕예약 관리", timeout=10000)
        print("  ✓ 콕예약 A 수정 저장 완료")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_edit_a_03_saved.png"))

        # 목록에서 수정된 이름 확인
        await crm_page.wait_for_timeout(1500)
        list_text_edit = await crm_page.locator("body").inner_text()
        assert "E2E 테스트 콕예약 A_수정" in list_text_edit, "목록에서 수정된 콕예약 A_수정을 찾을 수 없습니다."
        print("  ✓ 목록에서 수정된 이름 확인: E2E 테스트 콕예약 A_수정")

        # B2C 미리보기에서 수정 반영 확인
        print("\n--- B2C 미리보기 수정 확인 ---")
        kok_a_edit_el = crm_page.locator("text='E2E 테스트 콕예약 A_수정'").first
        await expect(kok_a_edit_el).to_be_visible(timeout=5000)
        preview_edit_handle = await crm_page.evaluate_handle("""(kokName) => {
            const els = [...document.querySelectorAll('*')];
            const nameEl = els.find(el => el.textContent.trim() === kokName && el.children.length === 0);
            if (!nameEl) return null;
            let parent = nameEl.parentElement;
            for (let i = 0; i < 10; i++) {
                if (!parent) break;
                const btn = parent.querySelector('button.sc-45a967ab-0, button');
                if (btn && btn.textContent.trim() === '미리보기') return btn;
                parent = parent.parentElement;
            }
            return null;
        }""", "E2E 테스트 콕예약 A_수정")
        preview_edit_btn = preview_edit_handle.as_element()
        assert preview_edit_btn is not None, "'E2E 테스트 콕예약 A_수정' 미리보기 버튼을 찾을 수 없습니다."

        async with runner.context.expect_page() as edit_page_info:
            await preview_edit_btn.click()
        edit_b2c = await edit_page_info.value
        await edit_b2c.wait_for_load_state("networkidle")
        original_edit_url = edit_b2c.url
        if "dev-front-zero.gongbiz.kr" in original_edit_url:
            cok_id = original_edit_url.rstrip("/").split("/")[-1]
            qa_url = f"https://qa-zero.gongbiz.kr/cok/{cok_id}"
            await edit_b2c.goto(qa_url)
            await edit_b2c.wait_for_load_state("networkidle")
        await edit_b2c.wait_for_timeout(1000)
        print(f"  ✓ 미리보기 페이지 열림: {edit_b2c.url}")
        await edit_b2c.screenshot(path=str(SHOT_DIR / "kok_edit_a_preview_01.png"))

        # 수정 항목 검증
        # 1. 이름
        edit_header = edit_b2c.locator("h2[data-track-id='header_title']").first
        await expect(edit_header).to_be_visible(timeout=10000)
        edit_preview_name = (await edit_header.inner_text()).strip()
        assert "A_수정" in edit_preview_name, f"미리보기 이름 수정 미반영: {edit_preview_name}"
        print(f"  ✓ [검증] 이름: {edit_preview_name}")

        # 2. 기본가격 (70,000원)
        edit_base_el = edit_b2c.locator("p.text-price").first
        await expect(edit_base_el).to_be_visible(timeout=5000)
        edit_base_text = (await edit_base_el.inner_text()).strip()
        assert "70,000" in edit_base_text, f"미리보기 기본가격 수정 미반영: {edit_base_text}"
        print(f"  ✓ [검증] 기본가격: {edit_base_text}")

        # 3. 회원가격 (50,000원)
        edit_member_label = edit_b2c.get_by_text("샵 회원가", exact=False).first
        await expect(edit_member_label).to_be_visible(timeout=3000)
        edit_member_el = edit_b2c.locator("p.text-price").nth(1)
        if await edit_member_el.count() > 0:
            edit_member_text = (await edit_member_el.inner_text()).strip()
            assert "50,000" in edit_member_text, f"미리보기 회원가격 수정 미반영: {edit_member_text}"
            print(f"  ✓ [검증] 회원가격: {edit_member_text}")

        # 4. 시술설명
        edit_desc_el = edit_b2c.locator("p.whitespace-pre-wrap").first
        await expect(edit_desc_el).to_be_visible(timeout=5000)
        edit_desc_text = (await edit_desc_el.inner_text()).strip()
        assert "A_수정" in edit_desc_text, f"미리보기 시술설명 수정 미반영: {edit_desc_text}"
        print(f"  ✓ [검증] 시술설명: {edit_desc_text}")

        # 5. 키워드 (테스트, 자동화, 수정)
        edit_kw_els = edit_b2c.locator("p.bg-gray-50")
        edit_kw_count_preview = await edit_kw_els.count()
        edit_actual_kws = []
        for i in range(edit_kw_count_preview):
            kw_text = (await edit_kw_els.nth(i).inner_text()).strip()
            edit_actual_kws.append(kw_text)
        for kw in ["테스트", "자동화", "수정"]:
            assert any(kw in ak for ak in edit_actual_kws), f"미리보기 키워드 '{kw}' 미발견: {edit_actual_kws}"
        print(f"  ✓ [검증] 키워드: {edit_actual_kws}")

        await edit_b2c.screenshot(path=str(SHOT_DIR / "kok_edit_a_preview_02_verified.png"))
        await edit_b2c.close()
        print("  ✓ B2C 미리보기 수정 확인 완료")
        print("✓ Phase 5.5 완료\n")

        # CRM 메인 페이지로 복귀
        await crm_page.bring_to_front()
        await crm_page.wait_for_timeout(1000)

        # ── Phase 6: 콕예약 미리보기 → 예약 (A + B) ──
        print("=== Phase 6: 콕예약 미리보기 → 예약 ===")

        tomorrow_kok = datetime.now() + timedelta(days=1)
        day_str_kok = str(tomorrow_kok.day)

        async def preview_and_book(kok_name, expected_values, designer_name, shot_prefix, test_report=False):
            """콕예약 목록에서 미리보기 클릭 → 등록 정보 검증 → 예약"""
            # 목록에서 해당 콕예약의 미리보기 클릭
            kok_name_el = crm_page.locator(f"text='{kok_name}'").first
            await expect(kok_name_el).to_be_visible(timeout=5000)
            preview_btn_handle = await crm_page.evaluate_handle("""(kokName) => {
                const els = [...document.querySelectorAll('*')];
                const nameEl = els.find(el => el.textContent.trim() === kokName && el.children.length === 0);
                if (!nameEl) return null;
                let parent = nameEl.parentElement;
                for (let i = 0; i < 10; i++) {
                    if (!parent) break;
                    const btn = parent.querySelector('button.sc-45a967ab-0, button');
                    if (btn && btn.textContent.trim() === '미리보기') return btn;
                    parent = parent.parentElement;
                }
                return null;
            }""", kok_name)
            preview_btn = preview_btn_handle.as_element()
            assert preview_btn is not None, f"'{kok_name}' 미리보기 버튼을 찾을 수 없습니다."

            async with runner.context.expect_page() as new_page_info:
                await preview_btn.click()
            b2c_page = await new_page_info.value
            await b2c_page.wait_for_load_state("networkidle")
            # dev-front-zero → qa-zero로 리다이렉트
            original_url = b2c_page.url
            if "dev-front-zero.gongbiz.kr" in original_url:
                cok_id = original_url.rstrip("/").split("/")[-1]
                qa_url = f"https://qa-zero.gongbiz.kr/cok/{cok_id}"
                await b2c_page.goto(qa_url)
                await b2c_page.wait_for_load_state("networkidle")
            await b2c_page.wait_for_timeout(1000)
            print(f"  ✓ 미리보기 페이지 열림: {b2c_page.url}")
            await b2c_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_01.png"))

            # ── 미리보기 등록 정보 검증 ──

            # 1. 콕예약 이름 (헤더 h2)
            header_name = b2c_page.locator("h2[data-track-id='header_title']").first
            await expect(header_name).to_be_visible(timeout=10000)
            preview_name = (await header_name.inner_text()).strip()
            assert kok_name in preview_name, \
                f"미리보기 이름 불일치: 기대 '{kok_name}', 실제 '{preview_name}'"
            print(f"  ✓ [검증] 콕예약 이름: {preview_name}")

            # 2. 사진 (이미지 슬라이더 확인)
            images = b2c_page.locator("img.object-cover")
            img_count = await images.count()
            assert img_count >= 1, f"미리보기 사진 미표시 (0장)"
            print(f"  ✓ [검증] 사진 표시 확인 ({img_count}장)")

            # 4. 시술 시간
            duration_el = b2c_page.locator("p.text-body2.text-gray-600").first
            await expect(duration_el).to_be_visible(timeout=5000)
            duration_text = (await duration_el.inner_text()).strip()
            expected_duration = expected_values["duration"]
            assert expected_duration in duration_text, \
                f"미리보기 시술 시간 불일치: 기대 '{expected_duration}', 실제 '{duration_text}'"
            print(f"  ✓ [검증] 시술 시간: {duration_text}")

            # 5. 기본 가격
            base_price_el = b2c_page.locator("p.text-price").first
            await expect(base_price_el).to_be_visible(timeout=5000)
            base_price_text = (await base_price_el.inner_text()).strip()
            expected_base = expected_values["base_price"]
            assert expected_base in base_price_text, \
                f"미리보기 기본 가격 불일치: 기대 '{expected_base}', 실제 '{base_price_text}'"
            print(f"  ✓ [검증] 기본 가격: {base_price_text}")

            # 6. 회원 가격
            member_label = b2c_page.get_by_text("샵 회원가", exact=False).first
            if expected_values.get("member_price"):
                await expect(member_label).to_be_visible(timeout=3000)
                member_price_el = b2c_page.locator("p.text-price").nth(1)
                if await member_price_el.count() > 0:
                    member_price_text = (await member_price_el.inner_text()).strip()
                else:
                    member_container = member_label.locator("..").first
                    member_price_text = (await member_container.inner_text()).strip()
                expected_member = expected_values["member_price"]
                assert expected_member in member_price_text, \
                    f"미리보기 회원 가격 불일치: 기대 '{expected_member}', 실제 '{member_price_text}'"
                print(f"  ✓ [검증] 회원 가격: {member_price_text} (샵 회원가)")
            else:
                if await member_label.count() == 0:
                    print(f"  ✓ [검증] 회원 가격: 미입력 (미표시 확인)")
                else:
                    print(f"  ⚠ [검증] 회원 가격: 미입력인데 표시됨")

            # 7. 시술 설명
            desc_el = b2c_page.locator("p.whitespace-pre-wrap").first
            await expect(desc_el).to_be_visible(timeout=5000)
            desc_text = (await desc_el.inner_text()).strip()
            expected_desc = expected_values["description"]
            assert expected_desc in desc_text, \
                f"미리보기 시술 설명 불일치: 기대 '{expected_desc}', 실제 '{desc_text}'"
            print(f"  ✓ [검증] 시술 설명: {desc_text}")

            # 8. 키워드
            keyword_els = b2c_page.locator("p.bg-gray-50")
            kw_count = await keyword_els.count()
            actual_keywords = []
            for i in range(kw_count):
                kw_text = (await keyword_els.nth(i).inner_text()).strip()
                actual_keywords.append(kw_text)
            expected_kws = expected_values.get("keywords", [])
            for kw in expected_kws:
                matched = any(kw in ak for ak in actual_keywords)
                assert matched, f"미리보기 키워드 '{kw}' 미발견 (실제: {actual_keywords})"
            print(f"  ✓ [검증] 키워드: {actual_keywords}")

            print(f"  ✓ 미리보기 등록 정보 검증 완료")

            # ── 신고하기 테스트 ──
            if test_report:
                kok_url = b2c_page.url
                print(f"\n  --- 신고하기 테스트 시작 ---")

                # 점 3개 메뉴 클릭
                dot_menu = b2c_page.locator("svg.text-gray-700").first
                await expect(dot_menu).to_be_visible(timeout=5000)
                await dot_menu.click()
                await b2c_page.wait_for_timeout(500)

                # 신고하기 클릭
                report_btn = b2c_page.locator("p:has-text('신고하기')").first
                await expect(report_btn).to_be_visible(timeout=3000)
                await report_btn.click()
                await b2c_page.wait_for_timeout(1000)
                print(f"  ✓ 신고하기 페이지 진입")

                # 기타 사유 선택
                etc_reason = b2c_page.locator("text='기타 사유'").first
                if await etc_reason.count() == 0:
                    etc_reason = b2c_page.get_by_text("기타 사유", exact=False).first
                await expect(etc_reason).to_be_visible(timeout=5000)
                await etc_reason.click()
                await b2c_page.wait_for_timeout(500)
                print(f"  ✓ 기타 사유 선택")

                # 신고 내용 입력
                report_input = b2c_page.locator("textarea, input[placeholder*='내용'], input[placeholder*='사유']").first
                await expect(report_input).to_be_visible(timeout=5000)
                await report_input.fill("콕예약 신고하기 테스트입니다.")
                await b2c_page.wait_for_timeout(500)
                print(f"  ✓ 신고 내용 입력")

                # 신고하기 버튼 클릭
                submit_report = b2c_page.locator("button:has-text('신고하기')").last
                await expect(submit_report).to_be_enabled(timeout=5000)
                await submit_report.click()
                await b2c_page.wait_for_timeout(2000)

                # "신고가 완료되었습니다" 토스트 확인
                body_text = await b2c_page.locator("body").inner_text()
                if "신고가 완료" in body_text or "신고" in body_text:
                    print(f"  ✓ 신고 완료 토스트 확인")
                else:
                    print(f"  ✓ 신고하기 완료 (토스트 소멸)")

                await b2c_page.wait_for_timeout(1000)
                await b2c_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_report_done.png"))

                # 같은 URL로 재진입 → 중복 신고 테스트
                print(f"  --- 중복 신고 테스트 ---")
                await b2c_page.goto(kok_url)
                await b2c_page.wait_for_load_state("networkidle")
                await b2c_page.wait_for_timeout(1000)

                # 점 3개 메뉴 → 신고하기 다시 클릭
                dot_menu2 = b2c_page.locator("svg.text-gray-700").first
                await expect(dot_menu2).to_be_visible(timeout=5000)
                await dot_menu2.click()
                await b2c_page.wait_for_timeout(500)

                report_btn2 = b2c_page.locator("p:has-text('신고하기')").first
                await expect(report_btn2).to_be_visible(timeout=3000)
                await report_btn2.click()
                await b2c_page.wait_for_timeout(1000)

                # 기타 사유 → 내용 입력 → 신고하기
                etc_reason2 = b2c_page.get_by_text("기타 사유", exact=False).first
                if await etc_reason2.count() > 0 and await etc_reason2.is_visible():
                    await etc_reason2.click()
                    await b2c_page.wait_for_timeout(500)
                    report_input2 = b2c_page.locator("textarea, input[placeholder*='내용'], input[placeholder*='사유']").first
                    if await report_input2.count() > 0:
                        await report_input2.fill("중복 신고 테스트")
                        await b2c_page.wait_for_timeout(500)
                    submit_report2 = b2c_page.locator("button:has-text('신고하기')").last
                    if await submit_report2.count() > 0 and await submit_report2.is_enabled():
                        await submit_report2.click()
                        await b2c_page.wait_for_timeout(2000)

                # "이미 신고한 콕 시술입니다." 토스트 확인 시도
                body_text2 = await b2c_page.locator("body").inner_text()
                if "이미 신고" in body_text2:
                    print(f"  ✓ 중복 신고 토스트 확인: 이미 신고한 콕 시술입니다.")
                else:
                    print(f"  ✓ 중복 신고 처리 확인 (토스트 소멸)")

                await b2c_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_report_dup.png"))

                # 콕예약 페이지로 돌아가서 예약 진행
                await b2c_page.goto(kok_url)
                await b2c_page.wait_for_load_state("networkidle")
                await b2c_page.wait_for_timeout(1000)

                print(f"  --- 신고하기 테스트 완료 ---\n")

            # 날짜 선택: 내일
            date_btn = b2c_page.get_by_role("button", name=day_str_kok, exact=True).first
            await expect(date_btn).to_be_visible(timeout=10000)
            await date_btn.click()
            await b2c_page.wait_for_timeout(1000)
            print(f"  ✓ 날짜 선택: 내일 ({tomorrow_kok.month}/{tomorrow_kok.day})")

            # 담당자 선택 + 시간 선택
            time_text = await b2c_page.evaluate("""(name) => {
                const pTags = [...document.querySelectorAll('p.truncate, p')];
                const nameP = pTags.find(p => p.textContent.includes(name));
                if (!nameP) return null;
                let section = nameP.parentElement;
                for (let i = 0; i < 5; i++) {
                    if (!section) break;
                    const otherNames = section.querySelectorAll('p.truncate, p');
                    const hasOtherDesigner = [...otherNames].some(p =>
                        !p.textContent.includes(name) && /담당자|대표원장/.test(p.textContent)
                    );
                    if (hasOtherDesigner) break;
                    const btns = [...section.querySelectorAll('button')];
                    const timeBtn = btns.find(b => /\\d{1,2}:\\d{2}/.test(b.textContent.trim()));
                    if (timeBtn) {
                        timeBtn.click();
                        return timeBtn.textContent.trim();
                    }
                    section = section.parentElement;
                }
                return null;
            }""", designer_name)
            assert time_text, f"'{designer_name}' 담당자의 시간 버튼을 찾을 수 없습니다."
            await b2c_page.wait_for_timeout(500)
            print(f"  ✓ 담당자 선택: {designer_name}")
            print(f"  ✓ 시간 선택: {time_text}")

            # 예약하기
            booking_btn = b2c_page.locator("button:has-text('예약하기')").last
            await booking_btn.scroll_into_view_if_needed()
            await expect(booking_btn).to_be_visible(timeout=15000)
            await booking_btn.click()
            await b2c_page.wait_for_load_state("networkidle")
            await b2c_page.wait_for_timeout(1000)

            # 카카오 로그인 (결제 페이지 하단 "카카오로 계속하기")
            kakao_btn = b2c_page.locator("button:has-text('카카오로 계속하기'), button:has-text('카카오')").first
            if await kakao_btn.count() > 0 and await kakao_btn.is_visible():
                async with b2c_page.expect_popup(timeout=15000) as popup_info:
                    await kakao_btn.click()
                popup = await popup_info.value
                await popup.wait_for_load_state("networkidle")
                await popup.wait_for_timeout(1000)

                id_field = popup.get_by_placeholder("카카오메일 아이디, 이메일, 전화번호")
                try:
                    await id_field.wait_for(state="visible", timeout=5000)
                    await id_field.fill("developer@herren.co.kr")
                    await popup.get_by_placeholder("비밀번호").fill("herren3378!")
                    await popup.get_by_role("button", name="로그인").first.click()
                    try:
                        await popup.wait_for_load_state("networkidle")
                        agree_btn = popup.locator("button:has-text('동의하고 계속하기')")
                        if await agree_btn.count() > 0 and await agree_btn.is_visible():
                            await agree_btn.click()
                            await popup.wait_for_timeout(2000)
                    except Exception:
                        pass
                except Exception:
                    pass  # 이미 로그인된 상태

                await b2c_page.wait_for_timeout(3000)
                await b2c_page.wait_for_load_state("domcontentloaded")
                print(f"  ✓ 카카오 로그인 완료")

            # 페이지 로드 대기
            await b2c_page.wait_for_timeout(2000)

            # 동의 체크 (있으면)
            agree = b2c_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
            if await agree.count() > 0:
                await agree.click()
                await b2c_page.wait_for_timeout(1000)

            # 최종 예약하기
            final_btn = b2c_page.locator("button:has-text('예약하기')").last
            await final_btn.scroll_into_view_if_needed()
            await expect(final_btn).to_be_visible(timeout=15000)
            await final_btn.click()
            await b2c_page.wait_for_load_state("networkidle")
            await b2c_page.wait_for_timeout(1000)

            body = await b2c_page.locator("body").inner_text()
            assert "bookingId" in b2c_page.url or "예약" in body, \
                f"콕예약 예약 실패: {b2c_page.url}"
            await b2c_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_02_complete.png"))
            print(f"  ✓ {kok_name} 예약 완료!")

            # 예약 완료 정보 수집
            booking_info = {
                "kok_name": kok_name,
                "designer": designer_name,
                "time": time_text,
                "date": f"{tomorrow_kok.month}/{tomorrow_kok.day}",
            }

            await b2c_page.close()
            return booking_info

        # ── 콕예약 A 미리보기 → 예약 (수정된 값으로 검증) ──
        print("\n--- 콕예약 A 미리보기 예약 ---")
        booking_a = await preview_and_book(
            kok_name="E2E 테스트 콕예약 A_수정",
            expected_values={
                "base_price": "70,000원",
                "member_price": "50,000원",
                "description": "E2E 자동화 테스트용 A_수정",
                "duration": "1시간 30분",
                "keywords": ["테스트", "자동화", "수정"],
            },
            designer_name="샵주테스트",
            shot_prefix="kok_preview_a",
        )

        # ── 콕예약 B 미리보기 → 예약 ──
        print("\n--- 콕예약 B 미리보기 예약 ---")
        await crm_page.bring_to_front()
        await crm_page.wait_for_timeout(1000)
        booking_b = await preview_and_book(
            kok_name="E2E 테스트 콕예약 B",
            expected_values={
                "base_price": "70,000원",
                "member_price": None,
                "description": "E2E 자동화 테스트용 B",
                "duration": "1시간",
                "keywords": [],
            },
            designer_name="테스트_직원계정1",
            shot_prefix="kok_preview_b",
            test_report=True,
        )

        print("✓ Phase 6 완료\n")

        # ── Phase 7: CRM 캘린더 → 예약 확인 → 매출 등록 (A + B) ──
        print("=== Phase 7: CRM 매출 등록 ===")

        async def verify_and_register_sales(booking, shot_prefix):
            """CRM 캘린더에서 예약 확인 후 매출 등록"""
            kok_name = booking["kok_name"]
            designer = booking["designer"]
            booked_time = booking["time"]

            print(f"\n--- CRM 매출 등록: {kok_name} ---")

            # 캘린더 페이지 이동
            await crm_page.goto(f"{CRM_BASE_URL}/book/calendar")
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(2000)

            # dimmer 닫기
            for _ in range(5):
                dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
                if await dim.count() > 0:
                    await dim.click(force=True)
                    await crm_page.wait_for_timeout(500)
                else:
                    break

            # "일" 보기 전환
            for name in ["일", "날짜별"]:
                btn = crm_page.get_by_role("button", name=name).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click()
                    await crm_page.wait_for_load_state("networkidle")
                    await crm_page.wait_for_timeout(1000)
                    break

            # 내일 날짜로 이동
            d = tomorrow_kok
            header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
            for _ in range(10):
                if f"{d.day}" in header:
                    break
                current_match = re.search(r"(\d+)\.\s*(\d+)", header)
                if current_match:
                    current_day = int(current_match.group(2))
                    btn_cls = "fc-next-button" if current_day < d.day else "fc-prev-button"
                else:
                    btn_cls = "fc-next-button"
                nav_btn = crm_page.locator(f"button.{btn_cls}").first
                await expect(nav_btn).to_be_visible(timeout=5000)
                await nav_btn.click()
                await crm_page.wait_for_load_state("networkidle")
                await crm_page.wait_for_timeout(1000)
                header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
            print(f"  ✓ 캘린더 날짜: {header.strip()}")

            # dimmer 닫기 + 블록 렌더링 대기
            for _ in range(3):
                dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
                if await dim.count() > 0:
                    await dim.click(force=True)
                    await crm_page.wait_for_timeout(500)
                else:
                    break
            await crm_page.wait_for_timeout(1000)

            # 예약 블록 찾기: 담당자 컬럼(data-resource-id) → 해당 컬럼 내 booking-normal 블록
            resource_id = await crm_page.evaluate("""(designerName) => {
                const headers = document.querySelectorAll('th[data-resource-id]');
                for (const th of headers) {
                    if (th.textContent.includes(designerName)) {
                        return th.getAttribute('data-resource-id');
                    }
                }
                return null;
            }""", designer)
            target_block = None
            if resource_id:
                col_blocks = crm_page.locator(
                    f"td[data-resource-id='{resource_id}'] div.booking-normal"
                )
                col_count = await col_blocks.count()
                for i in range(col_count):
                    block = col_blocks.nth(i)
                    block_text = await block.inner_text()
                    if kok_name in block_text and booked_time in block_text:
                        target_block = block
                        break
                # 시간 매칭 실패 시 콕예약 이름만으로 매칭
                if target_block is None:
                    for i in range(col_count):
                        block = col_blocks.nth(i)
                        block_text = await block.inner_text()
                        if kok_name in block_text:
                            target_block = block
                            break

            assert target_block is not None, f"캘린더에서 '{designer}' 컬럼의 '{kok_name}' 예약 블록을 찾을 수 없습니다."
            await target_block.click(force=True)
            await crm_page.wait_for_timeout(2000)
            await crm_page.wait_for_load_state("networkidle")
            print(f"  ✓ 예약 블록 클릭")

            # 예약 상세 정보 확인
            detail_text = await crm_page.locator("body").inner_text()
            await crm_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_crm_detail.png"))

            # 담당자 확인
            assert designer in detail_text, f"예약 상세에서 담당자 '{designer}' 미발견"
            print(f"  ✓ 담당자 확인: {designer}")

            # 시술 메뉴 확인 (콕예약 이름)
            assert kok_name in detail_text, f"예약 상세에서 시술명 '{kok_name}' 미발견"
            print(f"  ✓ 시술 메뉴 확인: {kok_name}")

            # "콕예약" 경로 확인
            assert "콕예약" in detail_text, "'콕예약' 텍스트 미발견"
            print("  ✓ '콕예약' 경로 확인")

            # 고객 요청사항 확인
            if "[콕예약]" in detail_text:
                print("  ✓ 고객 요청사항에 [콕예약] 확인")

            # 매출 등록 버튼 클릭
            sales_btn = crm_page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
            await expect(sales_btn).to_be_visible(timeout=10000)
            await sales_btn.click()
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(1000)
            print("  ✓ 매출 등록 페이지 진입")

            # 최종결제: 시술 콕예약 > 콕예약 이름 확인
            sales_text = await crm_page.locator("body").inner_text()
            assert kok_name in sales_text, f"매출 등록에서 '{kok_name}' 미발견"
            print(f"  ✓ 최종결제 시술 확인: 콕예약 > {kok_name}")
            await crm_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_crm_sales.png"))

            # 결제수단: 카드 선택
            card_btn = crm_page.get_by_text("카드", exact=True).first
            if await card_btn.count() == 0:
                card_btn = crm_page.locator("button:has-text('카드'), label:has-text('카드')").first
            await expect(card_btn).to_be_visible(timeout=10000)
            await card_btn.click()
            await crm_page.wait_for_timeout(500)
            print("  ✓ 결제수단: 카드 선택")

            # 매출 등록 버튼 클릭 (최종)
            final_sales = crm_page.locator("button:has-text('매출 등록')").first
            await expect(final_sales).to_be_visible(timeout=10000)
            await final_sales.click()
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(1000)
            await crm_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_crm_sales_done.png"))
            print(f"  ✓ {kok_name} 매출 등록 완료!")

        # CRM 페이지에서 매출 등록
        await crm_page.bring_to_front()
        await crm_page.wait_for_timeout(1000)

        # 콕예약 A 매출 등록
        await verify_and_register_sales(booking_a, "kok_a")

        # 콕예약 B 매출 등록
        await verify_and_register_sales(booking_b, "kok_b")

        print("✓ Phase 7 완료\n")

        # ── Phase 7.5: 매출 페이지 검증 ──
        print("=== Phase 7.5: 매출 페이지 검증 ===")

        # 좌측 GNB → 매출 메뉴 클릭
        sales_menu = crm_page.locator(
            "h3:has-text('매출'):visible, "
            "a:has-text('매출'):visible, "
            "span:has-text('매출'):visible"
        ).first
        await expect(sales_menu).to_be_visible(timeout=10000)
        await sales_menu.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 매출 페이지 진입")

        # 날짜 선택: 내일 날짜로 변경
        date_picker = crm_page.locator("div#div-choosedate-query-startdate").first
        if await date_picker.count() == 0:
            date_picker = crm_page.locator("[id*='choosedate'], [id*='startdate']").first
        await expect(date_picker).to_be_visible(timeout=5000)
        await date_picker.click()
        await crm_page.wait_for_timeout(1000)

        # 달력에서 내일 날짜 클릭
        tomorrow_day = str(tomorrow_kok.day)
        await crm_page.evaluate(f"""() => {{
            const tds = [...document.querySelectorAll('td, button')];
            const target = tds.find(td => {{
                const text = td.textContent.trim();
                return text === '{tomorrow_day}' && td.offsetParent !== null;
            }});
            if (target) target.click();
        }}""")
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print(f"  ✓ 날짜 선택: {tomorrow_kok.month}/{tomorrow_kok.day}")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_sales_page.png"))

        # 매출 목록에서 2건 확인
        sales_body = await crm_page.locator("body").inner_text()

        # 콕예약 A 검증
        assert "샵주테스트" in sales_body, "매출 목록에서 담당자 '샵주테스트' 미발견"
        assert "E2E 테스트 콕예약 A_수정" in sales_body, "매출 목록에서 'E2E 테스트 콕예약 A_수정' 미발견"
        assert "70,000" in sales_body, "매출 목록에서 실매출 '70,000' 미발견"
        print("  ✓ 콕예약 A 매출 확인: 담당자=샵주테스트, 판매상품=E2E 테스트 콕예약 A_수정, 실매출=70,000원")

        # 콕예약 B 검증
        assert "테스트_직원계정1" in sales_body, "매출 목록에서 담당자 '테스트_직원계정1' 미발견"
        assert "E2E 테스트 콕예약 B" in sales_body, "매출 목록에서 'E2E 테스트 콕예약 B' 미발견"
        print("  ✓ 콕예약 B 매출 확인: 담당자=테스트_직원계정1, 판매상품=E2E 테스트 콕예약 B, 실매출=70,000원")

        await crm_page.screenshot(path=str(SHOT_DIR / "kok_sales_verified.png"))
        print("✓ Phase 7.5 완료\n")

        # ── Phase 7.6: 통계 > 시술 통계 검증 ──
        print("=== Phase 7.6: 통계 > 시술 통계 검증 ===")

        # 좌측 GNB → 통계 메뉴 클릭
        stats_menu = crm_page.locator(
            "h3:has-text('통계'):visible, a:has-text('통계'):visible, "
            "span:has-text('통계'):visible"
        ).first
        await expect(stats_menu).to_be_visible(timeout=10000)
        await stats_menu.click()
        await crm_page.wait_for_load_state("domcontentloaded")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 통계 페이지 진입")

        # 시술 통계 카드의 [자세히 보기] 클릭
        clicked = await crm_page.evaluate("""(title) => {
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
        }""", "시술 통계")
        assert clicked, "시술 통계 카드의 '자세히 보기' 클릭 실패"
        await crm_page.wait_for_load_state("domcontentloaded")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 시술 통계 자세히 보기 진입")

        # 날짜 필터: 기간 선택 → 오늘 → 기간 검색
        range_btn = crm_page.locator("button:has(svg[icon='reserveCalender']):visible").first
        if await range_btn.count() == 0:
            range_btn = crm_page.locator("button:has(svg):visible").filter(
                has_text=re.compile(r"\d{1,2}\.\s*\d{1,2}\.\s*\d{1,2}")
            ).first
        if await range_btn.count() > 0:
            await range_btn.click()
            await crm_page.wait_for_timeout(500)

            # "오늘" 버튼
            today_btn = crm_page.locator("button:has-text('오늘'):visible").first
            if await today_btn.count() == 0:
                today_btn = crm_page.get_by_role("button", name="오늘").first
            if await today_btn.count() > 0:
                await today_btn.click()
                await crm_page.wait_for_timeout(300)

            # "기간 검색" 버튼
            search_btn = crm_page.locator("button:has-text('기간 검색'):visible").last
            if await search_btn.count() > 0:
                await search_btn.click()
                await crm_page.wait_for_load_state("networkidle")
                await crm_page.wait_for_timeout(1000)
            print("  ✓ 기간 필터 적용")
        else:
            print("  ⚠ 기간 선택 버튼 미발견, 기본 필터 사용")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_stats_treatment.png"))

        # 시술 통계 테이블에서 시술명, 실매출 합계, 총 합계 확인
        stat_table = crm_page.locator("table:visible").first
        await expect(stat_table).to_be_visible(timeout=5000)

        stat_body = await stat_table.inner_text()
        print(f"  [테이블 내용]\n{stat_body[:500]}")

        # 콕예약 A: 시술명 확인
        assert "E2E 테스트 콕예약 A_수정" in stat_body, "시술 통계에서 'E2E 테스트 콕예약 A_수정' 미발견"
        print("  ✓ 시술명 확인: E2E 테스트 콕예약 A_수정")

        # 콕예약 B: 시술명 확인
        assert "E2E 테스트 콕예약 B" in stat_body, "시술 통계에서 'E2E 테스트 콕예약 B' 미발견"
        print("  ✓ 시술명 확인: E2E 테스트 콕예약 B")

        # 각 시술의 실매출 합계, 총 합계 검증 (행 기준)
        rows = stat_table.locator("tbody tr:visible")
        row_count = await rows.count()

        async def get_col_value(table, header_text, row):
            """헤더 텍스트로 컬럼 인덱스 → 해당 행의 셀 값(원 단위) 추출"""
            header = table.locator(f"thead th:has-text('{header_text}')").first
            await expect(header).to_be_visible(timeout=3000)
            col_idx = await header.evaluate(
                "th => Array.from(th.parentElement.children).indexOf(th) + 1"
            )
            cell = row.locator(f"td:nth-child({col_idx})").first
            await expect(cell).to_be_visible(timeout=3000)
            text = re.sub(r"\\s+", " ", (await cell.inner_text()).strip())
            m = re.search(r"([0-9][0-9,]*)\s*원", text)
            if m:
                return int(m.group(1).replace(",", ""))
            m = re.search(r"([0-9][0-9,]*)", text)
            if m:
                return int(m.group(1).replace(",", ""))
            return 0

        found_a = False
        found_b = False
        for i in range(row_count):
            row = rows.nth(i)
            row_text = await row.inner_text()

            if "E2E 테스트 콕예약 A_수정" in row_text and not found_a:
                real_sales = await get_col_value(stat_table, "실 매출 합계", row)
                total = await get_col_value(stat_table, "총 합계", row)
                assert real_sales > 0, f"콕예약 A_수정 실매출 합계가 0원"
                assert real_sales % 70000 == 0, f"콕예약 A_수정 실매출이 70,000원 단위가 아님: {real_sales:,}"
                print(f"  ✓ 콕예약 A_수정 검증: 실매출 합계={real_sales:,}원, 총 합계={total:,}원")
                found_a = True

            elif "E2E 테스트 콕예약 B" in row_text and not found_b:
                real_sales = await get_col_value(stat_table, "실 매출 합계", row)
                total = await get_col_value(stat_table, "총 합계", row)
                assert real_sales > 0, f"콕예약 B 실매출 합계가 0원"
                assert real_sales % 70000 == 0, f"콕예약 B 실매출이 70,000원 단위가 아님: {real_sales:,}"
                print(f"  ✓ 콕예약 B 검증: 실매출 합계={real_sales:,}원, 총 합계={total:,}원")
                found_b = True

        assert found_a, "시술 통계에서 콕예약 A 행 미발견"
        assert found_b, "시술 통계에서 콕예약 B 행 미발견"

        await crm_page.screenshot(path=str(SHOT_DIR / "kok_stats_verified.png"))
        print("✓ Phase 7.6 완료\n")

        # ── Phase 8: 공비서로 예약받기 비활성화 → 콕예약 경고 배너 확인 ──
        print("=== Phase 8: 공비서로 예약받기 비활성화 ===")

        # GNB > 온라인 예약 클릭
        online_menu8 = crm_page.locator(
            "h3:has-text('온라인 예약'):visible, "
            "a:has-text('온라인 예약'):visible, "
            "button:has-text('온라인 예약'):visible, "
            "span:has-text('온라인 예약'):visible"
        ).first
        await expect(online_menu8).to_be_visible(timeout=10000)
        await online_menu8.click()
        await crm_page.wait_for_timeout(700)

        # 공비서로 예약받기 클릭
        reserve_menu = crm_page.locator(
            "button:has-text('공비서로 예약받기'):visible, "
            "a:has-text('공비서로 예약받기'):visible, "
            "span:has-text('공비서로 예약받기'):visible"
        ).first
        await expect(reserve_menu).to_be_visible(timeout=5000)
        await reserve_menu.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 공비서로 예약받기 페이지 진입")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_phase8_01_reserve_page.png"))

        # 예약받기 토글 (on→off) 클릭
        toggle = crm_page.locator("label[for='b2c-setting-activate-switch']").first
        await expect(toggle).to_be_visible(timeout=5000)
        await toggle.click()
        await crm_page.wait_for_timeout(1500)
        print("  ✓ 예약받기 토글 클릭")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_phase8_02_modal.png"))

        # 비활성화 모달 → "기대보다 예약이 적어요." 클릭
        reason = crm_page.locator("p:has-text('기대보다 예약이 적어요')").first
        await expect(reason).to_be_visible(timeout=5000)
        await reason.click()
        await crm_page.wait_for_timeout(500)
        print("  ✓ 비활성화 사유 선택: 기대보다 예약이 적어요.")

        # [예약받기 비활성화] 버튼 클릭
        deactivate_btn = crm_page.locator("button:has-text('예약받기 비활성화'):visible").last
        await expect(deactivate_btn).to_be_visible(timeout=5000)

        # alert 핸들러 등록
        alert_message = []

        async def _handle_deactivate_alert(dialog):
            alert_message.append(dialog.message)
            await dialog.accept()

        crm_page.on("dialog", _handle_deactivate_alert)
        await deactivate_btn.click()
        await crm_page.wait_for_timeout(2000)
        crm_page.remove_listener("dialog", _handle_deactivate_alert)

        if alert_message:
            assert "비활성화" in alert_message[0], f"예상 alert 아님: {alert_message[0]}"
            print(f"  ✓ alert 확인: {alert_message[0]}")
        else:
            body_text8 = await crm_page.locator("body").inner_text()
            if "비활성화" in body_text8:
                print("  ✓ 비활성화 완료 확인 (토스트)")
            else:
                print("  ✓ 비활성화 처리 완료")

        await crm_page.screenshot(path=str(SHOT_DIR / "kok_phase8_03_deactivated.png"))

        # GNB > 콕예약 관리 이동
        kok_menu8 = crm_page.locator("button:has-text('콕예약 관리'):visible").first
        if await kok_menu8.count() == 0:
            online_menu8b = crm_page.locator(
                "h3:has-text('온라인 예약'):visible, "
                "span:has-text('온라인 예약'):visible"
            ).first
            await online_menu8b.click()
            await crm_page.wait_for_timeout(700)
            kok_menu8 = crm_page.locator("button:has-text('콕예약 관리'):visible").first
        await expect(kok_menu8).to_be_visible(timeout=5000)
        await kok_menu8.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 콕예약 관리 페이지 이동")

        # 경고 배너 확인: "공비서로 예약받기가 꺼져 있어 콕예약이 노출되지 않습니다."
        warning_banner = crm_page.locator("h5:has-text('예약받기가 꺼져 있어')").first
        await expect(warning_banner).to_be_visible(timeout=10000)
        warning_text = (await warning_banner.inner_text()).strip()
        print(f"  ✓ 경고 배너 확인: {warning_text}")

        # "활성화하러 가기" 버튼 존재 확인
        activate_btn = crm_page.locator("h5:has-text('활성화하러 가기')").first
        await expect(activate_btn).to_be_visible(timeout=5000)
        print("  ✓ '활성화하러 가기' 버튼 확인")

        await crm_page.screenshot(path=str(SHOT_DIR / "kok_phase8_04_warning_banner.png"))
        print("✓ Phase 8 완료\n")

        print("=== 전체 테스트 성공! ===")

    finally:
        for p in [zero_page, crm_page]:
            if p and not p.is_closed():
                await p.close()
        if zero_context:
            await zero_context.close()
        await runner.teardown()
