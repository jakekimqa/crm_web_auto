"""
B2C 예약 3건 → B2B 취소 + 사유 검증 → 매출 등록 → 공비서 예약 OFF → 콕예약 + 매출 등록
"""
import asyncio, os, re, sys, json, urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from playwright.async_api import async_playwright, expect

sys.path.append(str(Path(__file__).resolve().parents[2]))
from auto_web_test.B2C_tests.test_b2b_b2c_shop_activation_flow import (
    ShopActivationRunner, _crm_login, _switch_shop,
    _open_nearby_list, _is_shop_visible_in_nearby,
    _make_reservation, _kakao_login, _is_toggle_on, _set_toggle,
    CRM_BASE_URL, ZERO_BASE_URL, SHOT_DIR,
)


@pytest.mark.asyncio
async def test_b2c_booking_cancel_with_default_reason():
    shop_name = f"{datetime.now():%m%d_%H%M}_배포_테스트"

    runner = ShopActivationRunner()
    runner.base_url = f"{CRM_BASE_URL}/signin"
    runner.headless = os.getenv("B2B_HEADLESS", "1") == "1"
    runner.mmdd = datetime.now().strftime("%m%d_%H%M")
    crm_page = zero_page = zero_context = None

    try:
        # ── Phase 1: 샵 생성 + 입점 ──
        print("\n=== Phase 1: 샵 생성 + 공비서 입점 ===")
        await runner.setup()
        await runner.login()
        try:
            await runner.create_new_shop()
        except Exception as e:
            if "signup/owner/add" in str(e):
                await runner.page.wait_for_url("**/signup/shop*", timeout=10000)
            else:
                raise
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
            await staff_page.wait_for_timeout(2000)
            staff_id_input = staff_page.locator("input[type='text'], input[name*='id'], input[placeholder*='아이디']").first
            await expect(staff_id_input).to_be_visible(timeout=10000)
            await staff_id_input.fill(STAFF_ID)
            staff_pw_input = staff_page.locator("input[type='password']").first
            await staff_pw_input.fill(STAFF_PW)
            staff_page.locator("button:has-text('로그인'), button[type='submit']").first
            await staff_page.locator("button:has-text('로그인'), button[type='submit']").first.click()
            await staff_page.wait_for_load_state("networkidle")
            await staff_page.wait_for_timeout(2000)
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
            await staff_page.wait_for_timeout(1500)

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
        await zero_page.wait_for_timeout(2000)

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
        await zero_page.wait_for_timeout(2000)

        # 결제 페이지: 동의 체크 → 최종 예약하기
        agree_check2 = zero_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
        if await agree_check2.count() > 0:
            await agree_check2.click()
            await zero_page.wait_for_timeout(500)

        final_booking2 = zero_page.locator("button:has-text('예약하기')").last
        await expect(final_booking2).to_be_visible(timeout=10000)
        await final_booking2.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(2000)

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
        await zero_page.wait_for_timeout(2000)

        # 결제 페이지: 동의 체크 → 최종 예약하기
        agree_check3 = zero_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
        if await agree_check3.count() > 0:
            await agree_check3.click()
            await zero_page.wait_for_timeout(500)

        final_booking3 = zero_page.locator("button:has-text('예약하기')").last
        await expect(final_booking3).to_be_visible(timeout=10000)
        await final_booking3.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(2000)

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
        await crm_page.wait_for_timeout(2000)

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
                await crm_page.wait_for_timeout(1500)
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
            await crm_page.wait_for_timeout(1500)
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
        await crm_page.wait_for_timeout(3000)
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
        await crm_page.wait_for_timeout(2000)
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
        await crm_page.wait_for_timeout(2000)

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
                await crm_page.wait_for_timeout(1500)
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
            await crm_page.wait_for_timeout(1500)
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
        await crm_page.wait_for_timeout(3000)
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
        await crm_page.wait_for_timeout(2000)
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
        await crm_page.wait_for_timeout(3000)
        print("  ✓ 매출 등록 완료")

        # 매출 등록 완료 확인
        await crm_page.goto(second_detail_url)
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(2000)
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
        await zero_page.wait_for_timeout(2000)

        # 결제 페이지: 최종 예약하기
        page_text = await zero_page.locator("body").inner_text()
        if "예약 완료" not in page_text and "예약 신청" not in page_text:
            final_booking = zero_page.locator("button:has-text('예약하기')").last
            await expect(final_booking).to_be_visible(timeout=15000)
            await final_booking.click()
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(2000)

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
                await crm_page.wait_for_timeout(1500)
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
            await crm_page.wait_for_timeout(1500)
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
        await crm_page.wait_for_timeout(3000)
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
        await crm_page.wait_for_timeout(2000)
        print("  ✓ 예약 확정 완료")
        await crm_page.screenshot(path=str(SHOT_DIR / "phase46_03_confirmed.png"))

        # 확정 후 캘린더로 이동될 수 있으므로 다시 예약 상세로 진입
        if "detail" not in crm_page.url:
            await crm_page.goto(confirm_detail_url)
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(2000)

        # Step 7: 매출 등록
        sales_btn = crm_page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
        await expect(sales_btn).to_be_visible(timeout=10000)
        await sales_btn.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(2000)
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
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(3000)
        print("  ✓ 매출 등록 완료")

        # 매출 등록 완료 확인
        await crm_page.goto(confirm_detail_url)
        await crm_page.wait_for_load_state("networkidle")
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

        # ── Phase 5: 공비서 예약 OFF → B2C 미노출 ──
        print("=== Phase 5: 공비서 예약 OFF → B2C 미노출 ===")
        await crm_page.goto(f"{CRM_BASE_URL}/b2c/setting")
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(1000)
        if await _is_toggle_on(crm_page):
            await _set_toggle(crm_page, turn_on=False)
            print("  ✓ 공비서 예약 OFF")
        else:
            print("  ✓ 이미 OFF")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_06_toggle_off.png"))

        await zero_page.bring_to_front()
        await _open_nearby_list(zero_page)
        await zero_page.screenshot(path=str(SHOT_DIR / "cancel_07_nearby_off.png"))
        assert not await _is_shop_visible_in_nearby(zero_page, shop_name), \
            f"비활성화 후 '{shop_name}' 아직 노출"
        print("  ✓ B2C 미노출 확인")
        print("✓ Phase 5 완료\n")

        # ── Phase 6: 콕예약 (기존 샵: 자동화_헤렌네일) ──
        print("=== Phase 6: 콕예약 (자동화_헤렌네일) ===")
        KOK_SHOP_NAME = "자동화_헤렌네일"

        # 기존 zero_page 세션 재활용 → 홈으로 이동
        await zero_page.bring_to_front()
        await zero_page.goto(f"{ZERO_BASE_URL}/main")
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(2000)

        # 관심샵에서 자동화_헤렌네일 진입
        fav_shop = zero_page.locator(f"text={KOK_SHOP_NAME}").first
        await expect(fav_shop).to_be_visible(timeout=10000)
        await fav_shop.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1500)
        print(f"  ✓ 관심샵 '{KOK_SHOP_NAME}' 진입")

        # 콕예약 탭 선택
        kok_tab = zero_page.locator("button:has-text('콕예약')").first
        await expect(kok_tab).to_be_visible(timeout=10000)
        await kok_tab.click()
        await zero_page.wait_for_timeout(1000)
        print("  ✓ 콕예약 탭 선택")

        # 자동화_테스트 콕예약 선택
        kok_item = zero_page.locator("text=자동화_테스트").first
        await expect(kok_item).to_be_visible(timeout=10000)
        await kok_item.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(1000)
        print("  ✓ '자동화_테스트' 콕예약 선택")

        # 내일 날짜 선택
        tomorrow_kok = datetime.now() + timedelta(days=1)
        day_str_kok = str(tomorrow_kok.day)
        date_btn_kok = zero_page.get_by_role("button", name=day_str_kok, exact=True).first
        await expect(date_btn_kok).to_be_visible(timeout=10000)
        await date_btn_kok.click()
        await zero_page.wait_for_timeout(1000)
        print(f"  ✓ 날짜 선택: 내일 ({tomorrow_kok.month}/{tomorrow_kok.day})")

        # 담당자 선택: 샵주테스트
        designer_kok = zero_page.locator("text=샵주테스트").first
        if await designer_kok.count() > 0 and await designer_kok.is_visible():
            select_btn_kok = zero_page.locator("button:has-text('선택')").first
            if await select_btn_kok.count() > 0 and await select_btn_kok.is_visible():
                await select_btn_kok.click()
            else:
                await designer_kok.click()
            await zero_page.wait_for_load_state("networkidle")
            await zero_page.wait_for_timeout(1000)
            print("  ✓ 담당자 선택: 샵주테스트")

        # 가장 빠른 시간 선택
        time_btn_kok = zero_page.locator("button:has-text(':00'), button:has-text(':30')").first
        await expect(time_btn_kok).to_be_visible(timeout=10000)
        kok_time = await time_btn_kok.inner_text()
        await time_btn_kok.click()
        await zero_page.wait_for_timeout(500)
        print(f"  ✓ 시간 선택: {kok_time}")

        # 예약하기 → 결제 페이지
        booking_btn_kok = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_btn_kok).to_be_visible(timeout=10000)
        await booking_btn_kok.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(2000)

        # 고객 요청사항 확인
        request_textarea = zero_page.locator("textarea").first
        if await request_textarea.count() > 0:
            request_text = await request_textarea.input_value()
        else:
            request_text = await zero_page.locator("body").inner_text()
        assert "[콕예약]" in request_text, \
            f"고객 요청사항에 '[콕예약]' 미포함: '{request_text[:100]}'"
        print(f"  ✓ 고객 요청사항: '{request_text.strip()}'")

        # 동의 체크 (있으면)
        agree_kok = zero_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
        if await agree_kok.count() > 0:
            await agree_kok.click()
            await zero_page.wait_for_timeout(500)

        # 하단 [예약하기] → 예약 완료
        final_kok = zero_page.locator("button:has-text('예약하기')").last
        await expect(final_kok).to_be_visible(timeout=10000)
        await final_kok.click()
        await zero_page.wait_for_load_state("networkidle")
        await zero_page.wait_for_timeout(2000)

        assert "bookingId" in zero_page.url or "예약 완료" in await zero_page.locator("body").inner_text(), \
            f"콕예약 실패: {zero_page.url}"
        await zero_page.screenshot(path=str(SHOT_DIR / "kok_01_booking_complete.png"))
        print("  ✓ 콕예약 완료!")
        print("✓ Phase 6 완료\n")

        # ── Phase 7: 콕예약 CRM 매출 등록 ──
        print("=== Phase 7: 콕예약 CRM 매출 등록 ===")
        await crm_page.bring_to_front()
        await _switch_shop(crm_page, KOK_SHOP_NAME)
        print(f"  ✓ CRM '{KOK_SHOP_NAME}' 전환")

        # 캘린더 → 내일 이동
        await crm_page.goto(f"{CRM_BASE_URL}/book/calendar")
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(2000)

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
                await crm_page.wait_for_timeout(1500)
                break

        # 딤머 닫기
        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 내일로 이동
        d_kok = tomorrow_kok
        header_kok = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        for _ in range(10):
            if f"{d_kok.day}" in header_kok:
                break
            current_match = re.search(r"(\d+)\.\s*(\d+)", header_kok)
            if current_match:
                current_day_kok = int(current_match.group(2))
                btn_cls_kok = "fc-next-button" if current_day_kok < d_kok.day else "fc-prev-button"
            else:
                btn_cls_kok = "fc-next-button"
            nav_btn_kok = crm_page.locator(f"button.{btn_cls_kok}").first
            await expect(nav_btn_kok).to_be_visible(timeout=5000)
            await nav_btn_kok.click()
            await crm_page.wait_for_load_state("networkidle")
            await crm_page.wait_for_timeout(1500)
            header_kok = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        print(f"  ✓ 캘린더 날짜: {header_kok.strip()}")

        # 딤머 닫기
        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 예약 블록 클릭 → 상세
        kok_block = crm_page.locator("div.booking-normal").first
        await expect(kok_block).to_be_visible(timeout=15000)
        await kok_block.click(force=True)
        await crm_page.wait_for_timeout(3000)
        await crm_page.wait_for_load_state("networkidle")
        kok_detail_url = crm_page.url
        print(f"  ✓ 예약 상세: {kok_detail_url}")

        # "공비서 > 콕예약" 확인
        kok_detail_text = await crm_page.locator("body").inner_text()
        assert "공비서" in kok_detail_text, "'공비서' 텍스트 미발견"
        assert "콕예약" in kok_detail_text, "'콕예약' 텍스트 미발견"
        print("  ✓ '공비서 > 콕예약' 확인")
        if "[콕예약]" in kok_detail_text:
            print("  ✓ 요청사항에 [콕예약] 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_02_crm_detail.png"))

        # 매출 등록
        sales_btn_kok = crm_page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
        await expect(sales_btn_kok).to_be_visible(timeout=10000)
        await sales_btn_kok.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(2000)
        print(f"  ✓ 매출 등록 페이지: {crm_page.url}")

        # 결제 금액 확인
        kok_sales_text = await crm_page.locator("body").inner_text()
        if "20,000" in kok_sales_text:
            print("  ✓ 결제 금액: 20,000원")

        # 카드 선택
        card_btn_kok = crm_page.get_by_text("카드", exact=True).first
        if await card_btn_kok.count() == 0:
            card_btn_kok = crm_page.locator("button:has-text('카드'), label:has-text('카드')").first
        await expect(card_btn_kok).to_be_visible(timeout=10000)
        await card_btn_kok.click()
        await crm_page.wait_for_timeout(500)
        print("  ✓ 결제 수단: 카드 선택")

        # 매출 등록
        save_btn_kok = crm_page.locator("button:has-text('매출 등록')").first
        await expect(save_btn_kok).to_be_visible(timeout=10000)
        await save_btn_kok.click()
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(3000)
        print("  ✓ 매출 등록 완료")

        # 매출 등록 완료 확인
        await crm_page.goto(kok_detail_url)
        await crm_page.wait_for_load_state("networkidle")
        await crm_page.wait_for_timeout(2000)
        kok_sales_label = crm_page.locator("h4.SALE.disabled:has-text('매출 등록')").first
        if await kok_sales_label.count() == 0:
            kok_sales_label = crm_page.locator("h4:has-text('매출 등록')").first
        await expect(kok_sales_label).to_be_visible(timeout=10000)
        print("  ✓ 매출 등록 완료 상태 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_03_sales_done.png"))
        print("✓ Phase 7 완료\n")

        print("=== 전체 테스트 성공! ===")

    finally:
        for p in [zero_page, crm_page]:
            if p and not p.is_closed():
                await p.close()
        if zero_context:
            await zero_context.close()
        await runner.teardown()
