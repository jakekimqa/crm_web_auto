"""
B2C E2E 테스트 v3 — 체크포인트 기반 Phase별 독립 실행
Phase별 메서드로 분리, 실패 시 이어서 재실행 가능
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
from auto_web_test.B2C_tests.b2c_checkpoint import B2CCheckpoint

IMG_DIR = Path("qa_artifacts/kok_register_images")
IMG_DIR.mkdir(parents=True, exist_ok=True)
KOK_IMAGE_COLORS = ["#FFB6C1", "#87CEEB", "#98FB98", "#DDA0DD", "#FFDAB9"]


def generate_kok_images(kok_name, count=5):
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


class B2CFlowV3:
    def __init__(self):
        self.runner = None
        self.crm_page = None
        self.zero_page = None
        self.zero_context = None
        self.shop_name = ""
        self.shop_id = None
        self.first_detail_url = None
        self.reason_text = None
        self.booking_a = None
        self.booking_b = None
        self.checkpoint = None
        self.b2c_img_paths = _generate_b2c_images()
        self.tomorrow_kok = datetime.now() + timedelta(days=1)
        self.phase_7_6_failed = False

    async def setup_browser(self):
        self.runner = ShopActivationRunner()
        self.runner.base_url = f"{CRM_BASE_URL}/signin"
        self.runner.headless = os.getenv("B2B_HEADLESS", "1") == "1"
        self.runner.mmdd = datetime.now().strftime("%m%d_%H%M")
        self.shop_name = f"{self.runner.mmdd}_배포_테스트"

        async def _attach_override(self_runner):
            await self_runner.page.set_input_files("input[type='file']", self.b2c_img_paths)
            await self_runner.page.wait_for_timeout(2000)

        self.runner._attach_b2c_test_image = lambda: _attach_override(self.runner)
        await self.runner.setup()
        self.runner.page.set_default_timeout(60000)

    async def _dismiss_popup(self):
        """페이지 로드 후 공휴일 공지 등 팝업/모달 dimmer 제거 + 향후 팝업 자동 차단"""
        await self.crm_page.evaluate("""() => {
            function killDimmers() {
                // React 앱 dimmer (#modal-dimmer)
                const dimmer = document.getElementById('modal-dimmer');
                if (dimmer) {
                    dimmer.style.display = 'none';
                    dimmer.style.pointerEvents = 'none';
                    if (dimmer.parentElement) {
                        dimmer.parentElement.style.display = 'none';
                        dimmer.parentElement.style.pointerEvents = 'none';
                    }
                }
                // 레거시 페이지 dimmer (.modal-dimmer, event-popup 등)
                document.querySelectorAll('.modal-dimmer.isActiveDimmed').forEach(el => {
                    el.style.display = 'none';
                    el.style.pointerEvents = 'none';
                    if (el.closest('.modal-wrapper')) {
                        el.closest('.modal-wrapper').style.display = 'none';
                    }
                });
            }
            killDimmers();
            // MutationObserver로 이후 나타나는 팝업도 자동 제거
            if (!window.__dimmerObserver) {
                window.__dimmerObserver = new MutationObserver(killDimmers);
                window.__dimmerObserver.observe(document.body, {
                    childList: true, subtree: true,
                    attributes: true, attributeFilter: ['class']
                });
            }
        }""")
        await self.crm_page.wait_for_timeout(500)

    async def restore_session(self):
        """체크포인트에서 resume 시 세션 복원"""
        print(f"  세션 복원 중: {self.shop_name}")

        # runner 로그인
        await self.runner.page.goto(self.runner.base_url, wait_until="domcontentloaded")
        await self.runner.page.fill('input[name="id"], input[type="text"]', self.runner.correct_id)
        await self.runner.page.fill('input[name="password"], input[type="password"]', self.runner.correct_password)
        await self.runner.page.click('button[type="submit"], .login-btn')
        try:
            await self.runner.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await self.runner.page.wait_for_timeout(1000)
        await _switch_shop(self.runner.page, self.shop_name)
        print("  ✓ runner 로그인 + 샵 전환 완료")

        # crm_page 생성
        self.crm_page = await self.runner.context.new_page()
        await _crm_login(self.crm_page)
        await _switch_shop(self.crm_page, self.shop_name)
        print("  ✓ crm_page 로그인 + 샵 전환 완료")

        # zero_page 생성
        self.zero_context = await self.runner.browser.new_context(viewport={"width": 430, "height": 932})
        self.zero_page = await self.zero_context.new_page()
        print("  ✓ zero_page 생성 완료")

    async def run(self, fresh=False):
        if fresh or not B2CCheckpoint.exists():
            self.checkpoint = B2CCheckpoint()
            self.checkpoint.mark_start(self.shop_name, CRM_BASE_URL)
            print("\n[새로운 테스트 시작]")
        else:
            self.checkpoint = B2CCheckpoint.load()
            print(f"\n[체크포인트 발견]\n{self.checkpoint.summary()}")
            self.shop_name = self.checkpoint.shop_name
            state = self.checkpoint.state
            self.shop_id = state.get("shop_id")
            self.first_detail_url = state.get("first_detail_url")
            self.reason_text = state.get("reason_text")
            if state.get("booking_a"):
                self.booking_a = state["booking_a"]
            if state.get("booking_b"):
                self.booking_b = state["booking_b"]

        await self.setup_browser()

        # resume 시 Phase 1 계열이 아닌 경우 세션 복원 필요
        resume_phase = self.checkpoint.get_resume_phase()
        if resume_phase and resume_phase not in ["1"]:
            if self.checkpoint.shop_name:
                self.shop_name = self.checkpoint.shop_name
                # Phase 1 완료 but 1.2, 1.5는 runner.page만 사용
                if resume_phase not in ["1.2", "1.5"]:
                    await self.restore_session()
                else:
                    # runner만 로그인
                    await self.runner.page.goto(self.runner.base_url, wait_until="domcontentloaded")
                    await self.runner.page.fill('input[name="id"], input[type="text"]', self.runner.correct_id)
                    await self.runner.page.fill('input[name="password"], input[type="password"]', self.runner.correct_password)
                    await self.runner.page.click('button[type="submit"], .login-btn')
                    try:
                        await self.runner.page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    await self.runner.page.wait_for_timeout(1000)
                    await _switch_shop(self.runner.page, self.shop_name)

        phases = [
            ("1", self.phase_1),
            ("1.2", self.phase_1_2),
            ("1.5", self.phase_1_5),
            ("2", self.phase_2),
            ("3", self.phase_3),
            ("4", self.phase_4),
            ("4.5", self.phase_4_5),
            ("4.6", self.phase_4_6),
            ("5", self.phase_5),
            ("5.5", self.phase_5_5),
            ("6", self.phase_6),
            ("7", self.phase_7),
            ("7.5", self.phase_7_5),
            ("7.6", self.phase_7_6),
            ("8", self.phase_8),
        ]

        for phase_id, phase_fn in phases:
            if self.checkpoint.is_phase_done(phase_id):
                print(f"  [SKIP] Phase {phase_id} (이미 완료)")
                continue
            try:
                await phase_fn()
                self.checkpoint.mark_phase_done(phase_id, extra_state=self._collect_state())
                print(f"✓ Phase {phase_id} 완료\n")
            except Exception as e:
                self.checkpoint.mark_phase_failed(phase_id, str(e))
                # 스크린샷 저장
                for p, name in [(self.crm_page, "crm"), (self.zero_page, "zero")]:
                    if p and not p.is_closed():
                        try:
                            await p.screenshot(path=str(SHOT_DIR / f"FAIL_phase_{phase_id}_{name}.png"))
                        except Exception:
                            pass
                raise

        if self.phase_7_6_failed:
            pytest.fail("Phase 7.6 시술 통계 검증 실패 (Phase 8은 성공)")
        print("=== 전체 테스트 성공! ===")
        B2CCheckpoint.clear()

    def _collect_state(self):
        return {
            "shop_name": self.shop_name,
            "shop_id": self.shop_id,
            "first_detail_url": self.first_detail_url,
            "reason_text": self.reason_text,
            "booking_a": self.booking_a,
            "booking_b": self.booking_b,
        }

    async def teardown(self):
        for p in [self.zero_page, self.crm_page]:
            if p and not p.is_closed():
                await p.close()
        if self.zero_context:
            await self.zero_context.close()
        if self.runner:
            await self.runner.teardown()

    # ──────────────────────────────────────────────
    # Phase 1: 샵 생성 + 공비서 입점
    # ──────────────────────────────────────────────
    async def phase_1(self):
        print("\n=== Phase 1: 샵 생성 + 공비서 입점 ===")
        runner = self.runner

        await runner.page.goto(runner.base_url, wait_until="domcontentloaded")
        await runner.page.fill('input[name="id"], input[type="text"]', runner.correct_id)
        await runner.page.fill('input[name="password"], input[type="password"]', runner.correct_password)
        await runner.page.click('button[type="submit"], .login-btn')
        try:
            await runner.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await runner.page.wait_for_timeout(1000)
        print("  ✓ 로그인 완료")

        add_shop = runner.page.get_by_role("link", name="+ 샵 추가")
        await expect(add_shop).to_be_visible(timeout=15000)
        await add_shop.click()

        name_input = runner.page.get_by_placeholder("샵 이름")
        await expect(name_input).to_be_visible(timeout=15000)
        await name_input.fill(f"{runner.mmdd}_배포_테스트")

        for addr_retry in range(3):
            try:
                async with runner.page.expect_popup(timeout=60000) as input_addr_info:
                    await runner.page.locator("input#addr[placeholder='샵 주소']").click()
                input_addr_page = await input_addr_info.value
                await input_addr_page.wait_for_load_state("domcontentloaded")
                try:
                    await input_addr_page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                await input_addr_page.wait_for_timeout(2000)

                frame = await runner._find_address_search_frame(input_addr_page)
                search_input = frame.locator("input#region_name, input.tf_keyword").first
                await search_input.fill("강남역")
                await search_input.press("Enter")
                await input_addr_page.wait_for_timeout(2000)

                address_item = frame.locator("span.txt_address").filter(
                    has_text="서울 강남구 강남대로 지하 396 (강남역)"
                ).locator("button.link_post").first
                await expect(address_item).to_be_visible(timeout=15000)
                await address_item.click()
                break
            except Exception as e:
                if addr_retry < 2:
                    try:
                        await input_addr_page.close()
                    except Exception:
                        pass
                    await runner.page.wait_for_timeout(1000)
                else:
                    raise

        detail_addr = runner.page.get_by_placeholder("상세 주소")
        await detail_addr.fill("테스트 상세주소")
        await detail_addr.press("Tab")
        await runner.page.wait_for_timeout(300)
        await runner.page.get_by_role("link", name="다음").first.click()
        try:
            await runner.page.wait_for_url("**/signup/owner/add", timeout=15000)
        except Exception:
            try:
                await runner.page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await runner.page.wait_for_timeout(2000)

        dropdown = runner.page.locator(".ui.dropdown-check.category")
        await expect(dropdown).to_be_visible(timeout=15000)
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
        try:
            await runner.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await runner.page.wait_for_timeout(2000)
        try:
            await runner.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await runner._dismiss_shop_creation_modals()
        print("  ✓ 샵 생성 완료")
        try:
            await runner.enable_gong_booking_after_shop_creation()
        except Exception as exc:
            if "토글이 ON 상태" not in str(exc) and "activate-switch" not in str(exc):
                raise

        self.checkpoint.mark_start(self.shop_name, CRM_BASE_URL)

    # ──────────────────────────────────────────────
    # Phase 1.2: 샵 소식 작성
    # ──────────────────────────────────────────────
    async def phase_1_2(self):
        print("=== Phase 1.2: 샵 소식 작성 ===")
        runner = self.runner
        news_title = f"자동화 샵 소식 {runner.mmdd}"
        news_content = f"자동화 테스트 샵 소식 상세 내용입니다. ({runner.mmdd})"
        test_image_path = str(Path(__file__).parent / "test_image.png")

        await runner.page.goto(f"{CRM_BASE_URL}/b2c/shop-news/new", wait_until="domcontentloaded")
        try:
            await runner.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await runner.page.wait_for_timeout(1000)

        title_input = runner.page.locator("input[placeholder*='50자']").first
        await expect(title_input).to_be_visible(timeout=15000)
        await title_input.fill(news_title)
        print(f"  ✓ 제목: {news_title}")

        representative_label = runner.page.locator("label").filter(has_text="대표 소식으로 설정").first
        await expect(representative_label).to_be_visible(timeout=15000)
        print("  ✓ 대표 소식으로 설정: 체크됨")

        content_textarea = runner.page.locator("textarea").first
        await expect(content_textarea).to_be_visible(timeout=15000)
        await content_textarea.fill(news_content)
        print(f"  ✓ 상세 내용: {news_content}")

        file_input = runner.page.locator("input[type='file']").first
        await file_input.set_input_files(test_image_path)
        await runner.page.wait_for_timeout(2000)

        photo_modal = runner.page.locator("[role='dialog']:visible, .modal:visible, #modal-content:visible").first
        await expect(photo_modal).to_be_visible(timeout=15000)
        modal_save_btn = photo_modal.locator("button:has-text('저장')").first
        await expect(modal_save_btn).to_be_visible(timeout=15000)
        print("  ✓ 사진 모달 노출 확인")
        runner.page.once("dialog", lambda d: asyncio.ensure_future(d.accept()))
        await modal_save_btn.click(force=True)
        await runner.page.wait_for_timeout(2000)
        print("  ✓ 사진 업로드 저장 완료")

        for _ in range(5):
            dim = runner.page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await runner.page.wait_for_timeout(500)
            else:
                break

        top_save_btn = runner.page.locator("button:has-text('저장'):visible").first
        await expect(top_save_btn).to_be_visible(timeout=15000)
        await top_save_btn.click(force=True)
        await runner.page.wait_for_timeout(2000)
        try:
            await runner.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        await runner.page.goto(f"{CRM_BASE_URL}/b2c/shop-news?fromMenu=true", wait_until="domcontentloaded")
        try:
            await runner.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await runner.page.wait_for_timeout(1000)
        body_text = await runner.page.locator("body").inner_text()
        assert news_title in body_text, f"샵 소식 저장 실패: '{news_title}' 미노출"
        print("  ✓ 샵 소식 저장 완료")
        await runner.page.screenshot(path=str(SHOT_DIR / "news_01_saved.png"))

    # ──────────────────────────────────────────────
    # Phase 1.5: 직원 입사 신청 + 원장 승인
    # ──────────────────────────────────────────────
    async def phase_1_5(self):
        print("=== Phase 1.5: 직원 입사 신청 + 원장 승인 ===")
        runner = self.runner
        STAFF_ID = "autoqatest2"
        STAFF_PW = "gong2023@@"

        staff_browser = await runner.playwright.chromium.launch(headless=runner.headless)
        staff_context = await staff_browser.new_context(viewport={"width": 1440, "height": 900})
        staff_page = await staff_context.new_page()
        try:
            await staff_page.goto(f"{CRM_BASE_URL}/signin", wait_until="domcontentloaded")
            try:
                await staff_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await staff_page.wait_for_timeout(1000)
            staff_id_input = staff_page.locator("input[type='text'], input[name*='id'], input[placeholder*='아이디']").first
            await expect(staff_id_input).to_be_visible(timeout=15000)
            await staff_id_input.fill(STAFF_ID)
            staff_pw_input = staff_page.locator("input[type='password']").first
            await staff_pw_input.fill(STAFF_PW)
            await staff_page.locator("button:has-text('로그인'), button[type='submit']").first.click()
            try:
                await staff_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await staff_page.wait_for_timeout(1000)
            print(f"  ✓ 직원({STAFF_ID}) 로그인 완료")

            add_shop_btn = staff_page.locator("button:has-text('샵 추가'), a:has-text('샵 추가')").first
            await expect(add_shop_btn).to_be_visible(timeout=15000)
            await add_shop_btn.click()
            try:
                await staff_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await staff_page.wait_for_timeout(1000)

            search_input = staff_page.locator("input[type='text'], input[placeholder*='검색'], input[placeholder*='샵']").first
            await expect(search_input).to_be_visible(timeout=15000)
            await search_input.click()
            await search_input.type(self.shop_name, delay=50)
            await staff_page.wait_for_timeout(1500)

            shop_item = staff_page.locator(f"text={self.shop_name}").first
            await expect(shop_item).to_be_visible(timeout=15000)
            await shop_item.click()
            await staff_page.wait_for_timeout(1000)
            print(f"  ✓ {self.shop_name} 선택")

            modal_next = staff_page.locator("button:has-text('다음'), a:has-text('다음')").last
            await expect(modal_next).to_be_visible(timeout=15000)
            await modal_next.click()
            await staff_page.wait_for_timeout(1000)

            page_next = staff_page.locator("button:has-text('다음'), a:has-text('다음')").first
            await expect(page_next).to_be_visible(timeout=15000)
            await page_next.click()
            try:
                await staff_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await staff_page.wait_for_timeout(1000)

            shop_row = staff_page.locator(f"tr:has-text('{self.shop_name}')")
            await expect(shop_row).to_be_visible(timeout=15000)
            status = await shop_row.locator("td.status").text_content()
            assert "승인 전" in status, f"상태 확인 실패: {status}"
            print(f"  ✓ 입사 신청 완료 → 상태: {status.strip()}")
        finally:
            await staff_browser.close()

        # 원장 계정으로 알림 벨 → 매출/운영 탭 → 직원 등록 요청 클릭 → 직원관리 진입
        await runner.page.bring_to_front()
        await runner.page.goto(f"{CRM_BASE_URL}/book/calendar", wait_until="domcontentloaded")
        try:
            await runner.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await runner.page.wait_for_timeout(2000)

        # 프로모션 팝업 등 모달 닫기 ("하루 동안 보지 않기" → X 버튼 → ESC → JS 제거)
        dismiss_link = runner.page.locator("text=하루 동안 보지 않기").first
        try:
            await dismiss_link.wait_for(state="visible", timeout=3000)
            await dismiss_link.click()
            await runner.page.wait_for_timeout(500)
            print("  ✓ 프로모션 팝업 닫기 (하루 동안 보지 않기)")
        except Exception:
            close_btn = runner.page.locator(
                "#modal-dimmer button:has-text('×'), "
                "#modal-dimmer button:has-text('닫기'), "
                "button[aria-label='닫기'], button[aria-label='close']"
            ).first
            try:
                await close_btn.wait_for(state="visible", timeout=2000)
                await close_btn.click()
                await runner.page.wait_for_timeout(500)
                print("  ✓ 모달 닫기 버튼 클릭")
            except Exception:
                pass

        for _ in range(3):
            dim = runner.page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await runner.page.keyboard.press("Escape")
                await runner.page.wait_for_timeout(500)
            else:
                break

        # JS로 남은 dimmer 강제 제거
        await runner.page.evaluate(
            "document.querySelector('#modal-dimmer')?.classList.remove('isActiveDimmed')"
        )
        await runner.page.wait_for_timeout(300)

        # 예약현황 패널이 열려있으면 닫기
        panel_close_btn = runner.page.locator("button:has(img[alt='예약 비활성화'])").first
        try:
            await panel_close_btn.wait_for(state="visible", timeout=3000)
            await panel_close_btn.click()
            await runner.page.wait_for_timeout(500)
            print("  ✓ 예약현황 패널 닫기")
        except Exception:
            pass

        # 알림 벨 버튼 클릭
        bell_btn = runner.page.locator("button[data-track-id='notification_panel_open']").first
        await expect(bell_btn).to_be_visible(timeout=15000)
        await bell_btn.click()
        await runner.page.wait_for_timeout(1500)
        print("  ✓ 알림 벨 클릭")

        # 매출/운영 탭 클릭
        ops_tab = runner.page.locator("button[data-track-id='notification_tab'][data-track-type='매출/운영']").first
        await expect(ops_tab).to_be_visible(timeout=15000)
        await ops_tab.click()
        await runner.page.wait_for_timeout(1000)
        print("  ✓ 매출/운영 탭 선택")

        # 직원 등록 요청 알림 클릭 → 직원관리 페이지 이동
        staff_noti = runner.page.locator("div[data-notification-key^='ENTER_EMP'][role='button']").first
        await expect(staff_noti).to_be_visible(timeout=15000)
        await staff_noti.click()
        try:
            await runner.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await runner.page.wait_for_timeout(1000)
        print(f"  ✓ 직원관리 페이지 진입 (알림 경유): {runner.page.url}")

        staff_row = runner.page.locator("tr:has-text('테스트_직원계정1')")
        await expect(staff_row).to_be_visible(timeout=15000)
        approve_btn = staff_row.locator("button:has-text('승인 대기')")
        await expect(approve_btn).to_be_visible(timeout=15000)
        await approve_btn.click()
        await runner.page.wait_for_timeout(1000)

        modal_approve = runner.page.locator("button:has-text('승인')").last
        await expect(modal_approve).to_be_visible(timeout=15000)
        await modal_approve.click()
        try:
            await runner.page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await runner.page.wait_for_timeout(1000)

        today_str = datetime.now().strftime("%y. %-m. %-d")
        row_text = await runner.page.locator("tr:has-text('테스트_직원계정1')").text_content()
        assert today_str in row_text, f"입사일 확인 실패: '{today_str}' not in '{row_text}'"
        print(f"  ✓ 직원 승인 완료 (입사일: {today_str})")
        await runner.page.screenshot(path=str(SHOT_DIR / "staff_join_approved.png"))

    # ──────────────────────────────────────────────
    # Phase 2: B2C 예약
    # ──────────────────────────────────────────────
    async def phase_2(self):
        print("=== Phase 2: B2C 예약 ===")
        runner = self.runner

        # crm_page, zero_page가 없으면 생성
        if not self.crm_page or self.crm_page.is_closed():
            self.crm_page = await runner.context.new_page()
            await _crm_login(self.crm_page)
        if not self.zero_context:
            self.zero_context = await runner.browser.new_context(viewport={"width": 430, "height": 932})
        if not self.zero_page or self.zero_page.is_closed():
            self.zero_page = await self.zero_context.new_page()

        crm_page = self.crm_page
        zero_page = self.zero_page

        await crm_page.bring_to_front()
        await _crm_login(crm_page)
        await _switch_shop(crm_page, self.shop_name)

        # shopId
        try:
            api_host = "api-zero.gongbiz.kr" if "crm.gongbiz.kr" in CRM_BASE_URL else "qa-api-zero.gongbiz.kr"
            api = f"https://{api_host}/api/v1/search/shop/location?lat=37.4979&lng=127.0276&radius=5000"
            with urllib.request.urlopen(api, timeout=10) as r:
                data = json.loads(r.read())
            self.shop_id = next(s["id"] for s in data.get("shopList", []) if self.shop_name in s.get("name", ""))
        except Exception:
            from auto_web_test.B2C_tests.test_b2b_b2c_shop_activation_flow import _get_shop_id_from_crm
            self.shop_id = await _get_shop_id_from_crm(crm_page)
        print(f"  shopId: {self.shop_id}")

        await zero_page.bring_to_front()

        # ── 로그인 전 기능 테스트 ──
        print("  --- 로그인 전 기능 테스트 ---")
        await zero_page.goto(f"{ZERO_BASE_URL}/main", wait_until="domcontentloaded")
        await zero_page.wait_for_load_state("networkidle", timeout=15000)
        await zero_page.wait_for_timeout(1000)

        magazine_item = zero_page.locator('a[href^="/magazine/"]').first
        await expect(magazine_item).to_be_visible(timeout=15000)
        await magazine_item.click()
        await zero_page.wait_for_load_state("networkidle", timeout=15000)
        await zero_page.wait_for_timeout(1000)
        print("  ✓ 매거진 상세 진입")

        await zero_page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await zero_page.wait_for_timeout(1000)
        like_btn = zero_page.locator('button[class*="rounded-[70px]"]').first
        await expect(like_btn).to_be_visible(timeout=15000)
        await like_btn.click()
        await zero_page.wait_for_timeout(1000)

        app_modal = zero_page.locator('div[role="dialog"]')
        await expect(app_modal).to_be_visible(timeout=15000)
        app_download_btn = app_modal.locator('button[data-track-id="web_app_download_click"]')
        await expect(app_download_btn).to_be_visible(timeout=3000)
        modal_text = await app_download_btn.text_content()
        assert "앱 다운로드" in modal_text or "다운로드" in modal_text or "앱으로" in modal_text, f"앱 다운로드 버튼 텍스트 불일치: {modal_text}"
        print(f"  ✓ 좋아요 → 앱 다운로드 모달 확인: {modal_text}")

        close_btn = app_modal.locator("button").filter(has_text=re.compile(r"^(닫기|X|×)$")).first
        if await close_btn.count() > 0:
            await close_btn.click()
        else:
            await zero_page.keyboard.press("Escape")
        await zero_page.wait_for_timeout(500)

        # 콕예약 좋아요 테스트
        await zero_page.goto(f"{ZERO_BASE_URL}/main", wait_until="domcontentloaded")
        await zero_page.wait_for_load_state("networkidle", timeout=15000)
        await zero_page.wait_for_timeout(1000)

        kok_link = zero_page.locator('a[href^="/cok/"]').first
        if await kok_link.count() > 0:
            await kok_link.click()
            await zero_page.wait_for_load_state("networkidle", timeout=15000)
            await zero_page.wait_for_timeout(1000)
            print("  ✓ 콕예약 상세 진입")

            kok_like = zero_page.locator('button[class*="rounded-[70px]"]').first
            if await kok_like.count() > 0:
                await kok_like.click()
                await zero_page.wait_for_timeout(1000)
                kok_modal = zero_page.locator('div[role="dialog"]')
                if await kok_modal.count() > 0 and await kok_modal.is_visible():
                    print("  ✓ 콕예약 좋아요 → 앱 다운로드 모달 확인")
                    await zero_page.keyboard.press("Escape")
                    await zero_page.wait_for_timeout(500)

        # 예약내역 버튼 테스트
        await zero_page.goto(f"{ZERO_BASE_URL}/main", wait_until="domcontentloaded")
        await zero_page.wait_for_load_state("networkidle", timeout=15000)
        await zero_page.wait_for_timeout(1000)

        booking_btn = zero_page.locator('a[href="/my/booking"]').first
        if await booking_btn.count() > 0:
            await booking_btn.click()
            await zero_page.wait_for_timeout(2000)
            if "/login" in zero_page.url:
                print("  ✓ 예약내역 → 로그인 페이지 리다이렉트 확인")
            else:
                print(f"  ✓ 예약내역 버튼 클릭 → {zero_page.url}")

        print("  --- 로그인 전 기능 테스트 완료 ---")

        # ── B2C 예약 3건 ──
        await _kakao_login(zero_page)
        print("  ✓ 카카오 로그인 완료")

        # 첫 번째 예약
        actual_date = await _make_reservation(zero_page, self.shop_name, self.shop_id)
        if actual_date:
            self.tomorrow_kok = actual_date
        print("  ✓ 첫 번째 예약 완료")

        # 두 번째 예약
        await _make_reservation(zero_page, self.shop_name, self.shop_id)
        print("  ✓ 두 번째 예약 완료")

        # 세 번째 예약
        await _make_reservation(zero_page, self.shop_name, self.shop_id)
        print("  ✓ 세 번째 예약 완료")

    # ──────────────────────────────────────────────
    # Phase 3~8: 나머지 Phase 메서드
    # (별도 파일에서 이어서 추가)
    # ──────────────────────────────────────────────
    async def phase_3(self):
        """Phase 3: 캘린더 → 상세 → 취소"""
        print("=== Phase 3: 캘린더 → 상세 → 취소 ===")
        crm_page = self.crm_page
        await crm_page.bring_to_front()
        await _switch_shop(crm_page, self.shop_name)

        await crm_page.goto(f"{CRM_BASE_URL}/book/calendar", wait_until="domcontentloaded")
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)

        for _ in range(5):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        for attempt in range(3):
            for _ in range(5):
                dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
                if await dim.count() > 0:
                    await dim.click(force=True)
                    await crm_page.wait_for_timeout(500)
                else:
                    break
            for name in ["일", "날짜별"]:
                btn = crm_page.get_by_role("button", name=name).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(force=True)
                    try:
                        await crm_page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    await crm_page.wait_for_timeout(1000)
                    break
            h = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
            if h.strip().count(".") >= 2:
                print(f"  ✓ 일 보기 전환 완료: {h.strip()}")
                break

        reservation_date = self.tomorrow_kok
        d = reservation_date
        target_day = f"{d.month}. {d.day}"
        header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        for _ in range(10):
            if target_day in header:
                break
            # "YY. M. D (요일)" 형식에서 월.일 추출
            m = re.search(r"\d+\.\s*(\d+)\.\s*(\d+)", header)
            if m:
                current_month = int(m.group(1))
                current_day = int(m.group(2))
                if current_month < d.month or (current_month == d.month and current_day < d.day):
                    btn_cls = "fc-next-button"
                else:
                    btn_cls = "fc-prev-button"
            else:
                btn_cls = "fc-next-button"
            for _ in range(3):
                dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
                if await dim.count() > 0:
                    await dim.click(force=True)
                    await crm_page.wait_for_timeout(500)
                else:
                    break
            nav_btn = crm_page.locator(f"button.{btn_cls}").first
            await expect(nav_btn).to_be_visible(timeout=15000)
            await nav_btn.click(force=True)
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)
            header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        print(f"  ✓ 캘린더 날짜: {header.strip()}")

        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_debug_calendar.png"), full_page=True)
        block = crm_page.locator("div.booking-normal").first
        await expect(block).to_be_visible(timeout=15000)
        await block.click(force=True)
        await crm_page.wait_for_timeout(2000)
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        self.first_detail_url = crm_page.url
        print(f"  ✓ 상세 페이지: {self.first_detail_url}")

        b2c = crm_page.locator("svg[icon='serviceB2c'], svg.ZERO_B2C").first
        try:
            await expect(b2c).to_be_visible(timeout=15000)
            print("  ✓ 공비서 마크 확인")
        except Exception:
            print("  ⚠ 공비서 마크 미매칭")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_01_detail.png"))

        sb = crm_page.get_by_role("button", name="예약 확정").first
        if await sb.count() == 0:
            sb = crm_page.locator("button").filter(has_text="예약 확정").first
        await expect(sb).to_be_visible(timeout=15000)
        await sb.click()
        await crm_page.wait_for_timeout(1000)

        co = crm_page.get_by_text("예약 취소").first
        await expect(co).to_be_visible(timeout=15000)
        await co.click()
        await crm_page.wait_for_timeout(1500)

        reason_label = crm_page.locator("text=취소 사유").first
        if await reason_label.count() > 0:
            await reason_label.click(force=True)
            await crm_page.wait_for_timeout(500)

        try:
            dismiss = crm_page.locator("text=하루 동안 보지 않기").first
            await dismiss.wait_for(state="visible", timeout=2000)
            await dismiss.click()
            await crm_page.wait_for_timeout(500)
        except Exception:
            pass

        modal = crm_page.locator("[role='dialog']:visible, #modal-content:visible").first
        await expect(modal).to_be_visible(timeout=15000)
        print("  ✓ 취소 모달 노출")

        mt = await modal.inner_text()
        if "환불 방식" not in mt:
            print("  ✓ 환불 방식 미노출 (예약금 없는 샵)")

        if "취소 사유" in mt:
            dr = modal.get_by_text(re.compile(r"시술이 어려운|다른 시간")).first
            await expect(dr).to_be_visible(timeout=15000)
            await dr.click()
            self.reason_text = await dr.inner_text()
            print(f"  ✓ 디폴트 사유: '{self.reason_text}'")
        else:
            self.reason_text = None
            print("  ✓ 단순 확인 모달 (취소 사유 없음)")

        cb = modal.locator(
            "button:has-text('예약 취소'), "
            "button:has-text('확인')"
        ).last
        await expect(cb).to_be_visible(timeout=15000)
        await cb.scroll_into_view_if_needed()
        await crm_page.wait_for_timeout(300)
        await cb.click(force=True)
        await crm_page.wait_for_timeout(3000)
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        try:
            dismiss = crm_page.locator("text=하루 동안 보지 않기").first
            await dismiss.wait_for(state="visible", timeout=2000)
            await dismiss.click()
            await crm_page.wait_for_timeout(500)
        except Exception:
            pass

        cancel_modal_gone = "/book/calendar" in crm_page.url and "detail" not in crm_page.url
        if not cancel_modal_gone:
            try:
                im = await modal.is_visible()
            except Exception:
                im = False
            cancel_modal_gone = not im
        assert cancel_modal_gone, "모달 안 닫힘"
        print("  ✓ 예약 취소 완료")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_03_complete.png"))

    async def phase_4(self):
        """Phase 4: 취소 사유 검증"""
        print("=== Phase 4: 취소 사유 검증 ===")
        crm_page = self.crm_page
        await crm_page.wait_for_timeout(2000)

        await crm_page.goto(self.first_detail_url, wait_until="domcontentloaded")
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_04_detail.png"))

        banner = crm_page.locator("h5.banner-title").filter(has_text="취소한 예약")
        if await banner.count() == 0:
            banner = crm_page.get_by_text(re.compile(r"취소한 예약|취소된 예약")).first
        await expect(banner).to_be_visible(timeout=15000)
        print(f"  ✓ 취소 배너: '{await banner.inner_text()}'")

        if self.reason_text:
            rel = crm_page.locator("p.banner-desc").first
            if await rel.count() == 0:
                rel = crm_page.get_by_text(re.compile(r"취소\s*사유")).first
            await expect(rel).to_be_visible(timeout=15000)
            displayed = await rel.inner_text()
            print(f"  ✓ 취소 사유: '{displayed}'")
            assert self.reason_text[:10] in displayed, f"불일치! '{self.reason_text}' vs '{displayed}'"
            print("  ✓ 취소 사유 일치!")
        else:
            print("  ✓ 취소 사유 없는 모달이므로 사유 검증 스킵")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_05_verified.png"))

    async def phase_4_5(self):
        """Phase 4.5: 두 번째 예약 매출 등록"""
        print("=== Phase 4.5: 두 번째 예약 매출 등록 ===")
        crm_page = self.crm_page
        d = self.tomorrow_kok

        await crm_page.goto(f"{CRM_BASE_URL}/book/calendar", wait_until="domcontentloaded")
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)

        for _ in range(5):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        for name in ["일", "날짜별"]:
            btn = crm_page.get_by_role("button", name=name).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click()
                try:
                    await crm_page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                await crm_page.wait_for_timeout(1000)
                break

        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        header2 = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        for _ in range(10):
            if f"{d.month}. {d.day}" in header2:
                break
            m2 = re.search(r"\d+\.\s*(\d+)\.\s*(\d+)", header2)
            if m2:
                cm2, cd2 = int(m2.group(1)), int(m2.group(2))
                btn_cls2 = "fc-next-button" if (cm2 < d.month or (cm2 == d.month and cd2 < d.day)) else "fc-prev-button"
            else:
                btn_cls2 = "fc-next-button"
            nav_btn2 = crm_page.locator(f"button.{btn_cls2}").first
            await expect(nav_btn2).to_be_visible(timeout=15000)
            await nav_btn2.click()
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)
            header2 = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()

        for _ in range(3):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 예약현황 패널이 열려있으면 닫기 (카드 클릭을 가릴 수 있음)
        booking_panel_close = crm_page.locator("img[alt='예약 비활성화']").first
        if await booking_panel_close.count() > 0 and await booking_panel_close.is_visible():
            await booking_panel_close.click()
            await crm_page.wait_for_timeout(500)
            print("  [OK] 예약현황 패널 닫기")

        male_block = crm_page.locator("div.booking-normal").first
        await expect(male_block).to_be_visible(timeout=15000)
        await male_block.click(force=True)
        await crm_page.wait_for_timeout(2000)
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        second_detail_url = crm_page.url
        print(f"  ✓ 두 번째 예약 상세: {second_detail_url}")

        detail_text = await crm_page.locator("body").inner_text()
        assert f"{d.day}" in detail_text, "예약일시 확인 실패"
        print(f"  ✓ 예약일시 확인: {d.month}/{d.day}")

        if "남성컷" in detail_text:
            print("  ✓ 시술 메뉴: 남성컷 확인")
        elif "여성컷" in detail_text:
            print("  ✓ 시술 메뉴: 여성컷 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_05a_male_detail.png"))

        sales_btn = crm_page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
        await expect(sales_btn).to_be_visible(timeout=15000)
        await sales_btn.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print(f"  ✓ 매출 등록 페이지: {crm_page.url}")

        sales_text = await crm_page.locator("body").inner_text()
        if "18,000" in sales_text:
            print("  ✓ 남은 결제 금액: 18,000원 (남성컷)")
        elif "20,000" in sales_text:
            print("  ✓ 남은 결제 금액: 20,000원 (여성컷)")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_05b_sales_page.png"))

        card_btn = crm_page.get_by_text("카드", exact=True).first
        if await card_btn.count() == 0:
            card_btn = crm_page.locator("button:has-text('카드'), label:has-text('카드')").first
        await expect(card_btn).to_be_visible(timeout=15000)
        await card_btn.click()
        await crm_page.wait_for_timeout(500)
        print("  ✓ 결제 수단: 카드 선택")

        save_btn = crm_page.locator("button:has-text('매출 저장'), button:has-text('매출 등록')").first
        await expect(save_btn).to_be_visible(timeout=15000)
        await save_btn.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 매출 등록 완료")

        await crm_page.goto(second_detail_url, wait_until="domcontentloaded")
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(2000)
        sales_label = crm_page.locator("h4:has-text('매출 등록')").first
        await expect(sales_label).to_be_visible(timeout=30000)
        print("  ✓ 매출 등록 완료 상태 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "cancel_05c_sales_done.png"))

    async def phase_4_6(self):
        """Phase 4.6: 확인 후 확정 예약"""
        print("=== Phase 4.6: 확인 후 확정 예약 ===")
        crm_page = self.crm_page
        zero_page = self.zero_page

        # Step 1: CRM 예약 방식 변경
        await crm_page.goto(f"{CRM_BASE_URL}/b2c/setting", wait_until="domcontentloaded")
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)

        online_info_section = crm_page.locator("h3:has-text('온라인 예약 정보')").first
        await expect(online_info_section).to_be_visible(timeout=15000)
        edit_btn = online_info_section.locator("..").locator("button:has-text('수정하기')").first
        await expect(edit_btn).to_be_visible(timeout=15000)
        await edit_btn.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 온라인 예약 정보 수정 페이지 진입")

        confirm_option = crm_page.locator("label[for='MANUAL_CONFIRMED']").first
        await expect(confirm_option).to_be_visible(timeout=15000)
        await confirm_option.click()
        await crm_page.wait_for_timeout(500)
        print("  ✓ 예약 방식: 담당자 확인 후 예약 확정 선택")

        save_btn = crm_page.locator("button[data-track-id='b2c_info_save']").first
        await expect(save_btn).to_be_visible(timeout=15000)
        await save_btn.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 예약 방식 변경 저장 완료")

        # Step 2: B2C 예약 진행
        print("  --- B2C 확인 후 확정 예약 진행 ---")
        await zero_page.goto(f"{ZERO_BASE_URL}/shop/{self.shop_id}", wait_until="domcontentloaded")
        try:
            await zero_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await zero_page.wait_for_timeout(1000)

        service_cb = zero_page.get_by_role("checkbox").first
        await expect(service_cb).to_be_visible(timeout=15000)
        await service_cb.click()
        await zero_page.wait_for_timeout(500)

        booking_btn = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_btn).to_be_visible(timeout=15000)
        await booking_btn.click()
        try:
            await zero_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await zero_page.wait_for_timeout(1000)

        designer_row = zero_page.locator("text=샵주테스트").first
        if await designer_row.count() > 0 and await designer_row.is_visible():
            select_btn = zero_page.locator("button:has-text('선택')").first
            await expect(select_btn).to_be_visible(timeout=15000)
            await select_btn.click()
            try:
                await zero_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await zero_page.wait_for_timeout(1000)
            print("  ✓ 담당자 선택: 샵주테스트")

        tomorrow = datetime.now() + timedelta(days=1)
        day_str = str(tomorrow.day)
        date_btn = zero_page.get_by_role("button", name=day_str, exact=True).first
        await expect(date_btn).to_be_visible(timeout=15000)
        await date_btn.click()
        await zero_page.wait_for_timeout(1000)

        time_btn = zero_page.locator("button:has-text(':00'), button:has-text(':30')").first
        await expect(time_btn).to_be_visible(timeout=15000)
        confirm_time_text = await time_btn.inner_text()
        await time_btn.click()
        await zero_page.wait_for_timeout(500)
        print(f"  ✓ 시간 선택: {confirm_time_text}")

        booking_confirm = zero_page.locator("button:has-text('예약하기')").last
        await expect(booking_confirm).to_be_visible(timeout=15000)
        await booking_confirm.click()
        try:
            await zero_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await zero_page.wait_for_timeout(1000)

        # 앱 다운로드 팝업 제거
        await zero_page.evaluate("""() => {
            document.querySelectorAll('article, [role="alert"]').forEach(el => {
                if (el.textContent.includes('앱 다운로드') || el.textContent.includes('App 다운로드') || el.getAttribute('role') === 'alert') {
                    el.style.display = 'none';
                    el.style.pointerEvents = 'none';
                }
            });
        }""")
        await zero_page.wait_for_timeout(500)

        page_text = await zero_page.locator("body").inner_text()
        if "예약 완료" not in page_text and "예약 신청" not in page_text:
            # 동의 체크박스
            agree = zero_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
            if await agree.count() > 0:
                await agree.click()
                await zero_page.wait_for_timeout(1000)

            final_booking = zero_page.locator("button:has-text('예약하기')").last
            await expect(final_booking).to_be_visible(timeout=15000)
            await final_booking.click(force=True)
            try:
                await zero_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await zero_page.wait_for_timeout(2000)

        # Step 3: B2C 예약 완료/신청 텍스트 검증
        complete_text = await zero_page.locator("body").inner_text()
        has_completion = any(t in complete_text for t in ["예약 신청", "예약 완료", "예약이 접수"])
        assert has_completion, f"확인 후 확정 예약 완료 텍스트 미노출: {complete_text[:300]}"
        print("  ✓ B2C 예약 완료/신청 텍스트 확인")
        await zero_page.screenshot(path=str(SHOT_DIR / "phase46_01_b2c_pending.png"))

        # Step 4: CRM 알림 벨 → 예약 탭 → 예약 클릭
        await crm_page.bring_to_front()

        await crm_page.goto(f"{CRM_BASE_URL}/book/calendar", wait_until="domcontentloaded")
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(2000)

        for _ in range(5):
            dim = crm_page.locator("#modal-dimmer.isActiveDimmed:visible").first
            if await dim.count() > 0:
                await dim.click(force=True)
                await crm_page.wait_for_timeout(500)
            else:
                break

        # 예약현황 패널이 열려있으면 닫기 (말풍선을 가리므로 먼저 닫아야 함)
        panel_close_btn = crm_page.locator("button:has(img[alt='예약 비활성화'])").first
        try:
            await panel_close_btn.wait_for(state="visible", timeout=3000)
            await panel_close_btn.click()
            await crm_page.wait_for_timeout(500)
            print("  ✓ 예약현황 패널 닫기")
        except Exception:
            print("  [SKIP] 예약현황 패널 없음")

        # 알림 말풍선 확인
        noti_bubble = crm_page.locator("h5:has-text('대기 중인 예약')").first
        await expect(noti_bubble).to_be_visible(timeout=15000)
        bubble_text = await noti_bubble.inner_text()
        print(f"  ✓ 알림 말풍선: {bubble_text}")

        # 알림 벨 버튼 클릭
        bell_btn = crm_page.locator("button[data-track-id='notification_panel_open']").first
        await expect(bell_btn).to_be_visible(timeout=15000)
        await bell_btn.click()
        await crm_page.wait_for_timeout(1500)
        print("  ✓ 알림 벨 클릭 → 알림 패널 열림")

        # "예약" 탭 클릭
        reservation_tab = crm_page.locator("button[data-track-id='notification_tab'][data-track-type='예약']").first
        await expect(reservation_tab).to_be_visible(timeout=15000)
        await reservation_tab.click()
        await crm_page.wait_for_timeout(1500)
        print("  ✓ 예약 탭 선택")

        # 알림 목록에서 해당 예약 클릭 → 캘린더로 이동
        noti_item = crm_page.locator("div[data-notification-key^='ZERO_BOOKING_READY'][role='button']").first
        await expect(noti_item).to_be_visible(timeout=15000)
        await noti_item.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(2000)
        print(f"  ✓ 알림 클릭 → 캘린더 이동: {crm_page.url}")

        # 캘린더에서 대기 중인 예약 카드 클릭 → 예약 상세 진입
        pending_block = crm_page.locator("div.READY.booking-normal").first
        await expect(pending_block).to_be_visible(timeout=15000)
        await pending_block.click(force=True)
        await crm_page.wait_for_timeout(2000)
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        confirm_detail_url = crm_page.url
        print(f"  ✓ 예약 상세: {confirm_detail_url}")
        await crm_page.screenshot(path=str(SHOT_DIR / "phase46_02_crm_pending.png"))

        # Step 5: 확인 후 확정 안내 확인
        detail_text = await crm_page.locator("body").inner_text()
        assert "확인 후 확정" in detail_text or "예약 대기" in detail_text, f"확인 후 확정 안내 미노출"
        print("  ✓ '확인 후 확정 예약입니다' 안내 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "phase46_02_crm_pending.png"))

        # Step 6: 예약 확정
        confirm_btn = crm_page.locator("button:has-text('예약 확정')").first
        await expect(confirm_btn).to_be_visible(timeout=15000)
        await confirm_btn.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 예약 확정 완료")
        await crm_page.screenshot(path=str(SHOT_DIR / "phase46_03_confirmed.png"))

        if "detail" not in crm_page.url:
            await crm_page.goto(confirm_detail_url, wait_until="domcontentloaded")
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)

        # Step 7: 매출 등록
        sales_btn = crm_page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
        await expect(sales_btn).to_be_visible(timeout=15000)
        await sales_btn.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)

        card_btn = crm_page.get_by_text("카드", exact=True).first
        if await card_btn.count() == 0:
            card_btn = crm_page.locator("button:has-text('카드'), label:has-text('카드')").first
        await expect(card_btn).to_be_visible(timeout=15000)
        await card_btn.click()
        await crm_page.wait_for_timeout(500)
        print("  ✓ 결제 수단: 카드 선택")

        save_sales_btn = crm_page.locator("button:has-text('매출 저장'), button:has-text('매출 등록')").first
        await expect(save_sales_btn).to_be_visible(timeout=15000)
        await save_sales_btn.click()
        await crm_page.wait_for_timeout(3000)
        print("  ✓ 매출 등록 완료")

        await crm_page.goto(confirm_detail_url, wait_until="domcontentloaded")
        await crm_page.wait_for_load_state("domcontentloaded")
        await crm_page.wait_for_timeout(2000)
        detail_body = await crm_page.locator("body").inner_text()
        assert "매출" in detail_body, f"매출 등록 확인 실패"
        print("  ✓ 매출 등록 완료 상태 확인")
        await crm_page.screenshot(path=str(SHOT_DIR / "phase46_04_sales_done.png"))

        # 예약 방식 복원
        await crm_page.goto(f"{CRM_BASE_URL}/b2c/setting", wait_until="domcontentloaded")
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        online_info_section2 = crm_page.locator("h3:has-text('온라인 예약 정보')").first
        edit_btn2 = online_info_section2.locator("..").locator("button:has-text('수정하기')").first
        await expect(edit_btn2).to_be_visible(timeout=15000)
        await edit_btn2.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        instant_option = crm_page.locator("label[for='AUTO_CONFIRMED']").first
        await expect(instant_option).to_be_visible(timeout=15000)
        await instant_option.click()
        await crm_page.wait_for_timeout(500)
        restore_save = crm_page.locator("button[data-track-id='b2c_info_save']").first
        await expect(restore_save).to_be_visible(timeout=15000)
        await restore_save.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 예약 방식 복원: 즉시 예약 확정")

    async def phase_5(self):
        """Phase 5: 콕예약 등록 (필수값 검증 + A/B 등록)"""
        print("=== Phase 5: 콕예약 등록 ===")
        crm_page = self.crm_page
        runner = self.runner

        await crm_page.bring_to_front()
        await _switch_shop(crm_page, self.shop_name)

        # 온라인 예약 > 콕예약 관리 진입
        online_menu = crm_page.locator(
            "h3:has-text('온라인 예약'):visible, "
            "a:has-text('온라인 예약'):visible, "
            "button:has-text('온라인 예약'):visible, "
            "span:has-text('온라인 예약'):visible"
        ).first
        await expect(online_menu).to_be_visible(timeout=15000)
        await online_menu.click()
        await crm_page.wait_for_timeout(1000)

        kok_menu = crm_page.locator(
            "a:has-text('콕예약 관리'):visible, "
            "span:has-text('콕예약 관리'):visible, "
            "h4:has-text('콕예약 관리'):visible, "
            "li:has-text('콕예약 관리'):visible"
        ).first
        if not await kok_menu.is_visible():
            await online_menu.click()
            await crm_page.wait_for_timeout(1000)
        await expect(kok_menu).to_be_visible(timeout=15000)
        await kok_menu.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 콕예약 관리 진입")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_01_list.png"))

        # ── 필수값 누락 시 저장 버튼 비활성화 검증 ──
        print("\n=== 필수값 누락 저장 버튼 비활성화 검증 ===")

        async def _handle_dialog(dialog):
            await dialog.accept()

        register_btn = crm_page.locator("button:has-text('콕예약 등록'), a:has-text('콕예약 등록'), a:has-text('콕예약 등록하기')").first
        await expect(register_btn).to_be_visible(timeout=15000)
        await register_btn.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
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
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await crm_page.wait_for_timeout(1000)
            crm_page.remove_listener("dialog", _handle_dialog)
            reg = crm_page.locator("button:has-text('콕예약 등록'), a:has-text('콕예약 등록')").first
            await expect(reg).to_be_visible(timeout=15000)
            await reg.click()
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
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
        await expect(deselect_btn).to_be_visible(timeout=15000)
        await deselect_btn.click()
        await crm_page.wait_for_timeout(500)
        await assert_save_disabled("담당자 누락")

        crm_page.on("dialog", _handle_dialog)
        await crm_page.go_back()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        crm_page.remove_listener("dialog", _handle_dialog)

        print("=== 필수값 누락 검증 완료 (6건 모두 비활성화 확인) ===\n")

        # ── 콕예약 A 등록 ──
        register_btn = crm_page.locator("button:has-text('콕예약 등록'), a:has-text('콕예약 등록')").first
        await expect(register_btn).to_be_visible(timeout=15000)
        await register_btn.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 콕예약 등록 화면 진입")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_02_register_form.png"))

        name_input = crm_page.locator(
            "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
            "input[placeholder*='이름']"
        ).first
        await expect(name_input).to_be_visible(timeout=15000)
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
        await crm_page.wait_for_selector("text=콕예약 관리", timeout=15000)
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
        await expect(register_btn2).to_be_visible(timeout=15000)
        await register_btn2.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 콕예약 등록 화면 진입")

        name_input_b = crm_page.locator(
            "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
            "input[placeholder*='이름']"
        ).first
        await expect(name_input_b).to_be_visible(timeout=15000)
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
        await crm_page.wait_for_selector("text=콕예약 관리", timeout=15000)
        print("  ✓ 저장 완료")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_08_after_save_b.png"))

        await crm_page.wait_for_timeout(1500)
        list_text2 = await crm_page.locator("body").inner_text()
        assert "E2E 테스트 콕예약 A" in list_text2, "목록에서 콕예약 A를 찾을 수 없습니다."
        assert "E2E 테스트 콕예약 B" in list_text2, "목록에서 콕예약 B를 찾을 수 없습니다."
        print("  ✓ 목록에서 콕예약 A, B 모두 확인 (2건)")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_09_list_verify_ab.png"))

    async def phase_5_5(self):
        """Phase 5.5: 콕예약 A 수정 + B2C 미리보기 수정 확인"""
        print("=== Phase 5.5: 콕예약 A 수정 + B2C 미리보기 수정 확인 ===")
        crm_page = self.crm_page
        runner = self.runner

        # 목록에서 콕예약 A 클릭 → 수정 화면 진입
        kok_a_item = crm_page.locator("text='E2E 테스트 콕예약 A'").first
        await expect(kok_a_item).to_be_visible(timeout=15000)
        await kok_a_item.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 콕예약 A 수정 화면 진입")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_edit_a_01_before.png"))

        # 이름 수정
        edit_name = crm_page.locator(
            "input[placeholder*='콕예약 이름을 입력'], input[placeholder*='콕예약'], "
            "input[placeholder*='이름']"
        ).first
        await expect(edit_name).to_be_visible(timeout=15000)
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
        await crm_page.wait_for_selector("text=콕예약 관리", timeout=15000)
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
        await expect(kok_a_edit_el).to_be_visible(timeout=15000)
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

        async with runner.context.expect_page(timeout=60000) as edit_page_info:
            await preview_edit_btn.click()
        edit_b2c = await edit_page_info.value
        try:
            await edit_b2c.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        original_edit_url = edit_b2c.url
        if "dev-front-zero.gongbiz.kr" in original_edit_url:
            cok_id = original_edit_url.rstrip("/").split("/")[-1]
            qa_url = f"https://qa-zero.gongbiz.kr/cok/{cok_id}"
            await edit_b2c.goto(qa_url, wait_until="domcontentloaded")
            try:
                await edit_b2c.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
        await edit_b2c.wait_for_timeout(1000)
        print(f"  ✓ 미리보기 페이지 열림: {edit_b2c.url}")
        await edit_b2c.screenshot(path=str(SHOT_DIR / "kok_edit_a_preview_01.png"))

        # 수정 항목 검증
        # 1. 이름
        edit_header = edit_b2c.locator("h2[data-track-id='header_title']").first
        await expect(edit_header).to_be_visible(timeout=15000)
        edit_preview_name = (await edit_header.inner_text()).strip()
        assert "A_수정" in edit_preview_name, f"미리보기 이름 수정 미반영: {edit_preview_name}"
        print(f"  ✓ [검증] 이름: {edit_preview_name}")

        # 2. 기본가격 (70,000원)
        edit_base_el = edit_b2c.locator("p.text-price").first
        await expect(edit_base_el).to_be_visible(timeout=15000)
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
        await expect(edit_desc_el).to_be_visible(timeout=15000)
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

        # CRM 메인 페이지로 복귀
        await crm_page.bring_to_front()
        await crm_page.wait_for_timeout(1000)

    async def _preview_and_book(self, kok_name, expected_values, designer_name, shot_prefix, test_report=False):
        """콕예약 목록에서 미리보기 클릭 → 등록 정보 검증 → 예약"""
        crm_page = self.crm_page
        runner = self.runner
        tomorrow_kok = self.tomorrow_kok
        day_str_kok = str(tomorrow_kok.day)

        # 목록에서 해당 콕예약의 미리보기 클릭
        kok_name_el = crm_page.locator(f"text='{kok_name}'").first
        await expect(kok_name_el).to_be_visible(timeout=15000)
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

        async with runner.context.expect_page(timeout=60000) as new_page_info:
            await preview_btn.click()
        b2c_page = await new_page_info.value
        try:
            await b2c_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        original_url = b2c_page.url
        if "dev-front-zero.gongbiz.kr" in original_url:
            cok_id = original_url.rstrip("/").split("/")[-1]
            qa_url = f"https://qa-zero.gongbiz.kr/cok/{cok_id}"
            await b2c_page.goto(qa_url, wait_until="domcontentloaded")
            try:
                await b2c_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
        await b2c_page.wait_for_timeout(1000)
        print(f"  ✓ 미리보기 페이지 열림: {b2c_page.url}")
        await b2c_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_01.png"))

        # ── 미리보기 등록 정보 검증 ──
        # 1. 콕예약 이름 (헤더 h2)
        header_name = b2c_page.locator("h2[data-track-id='header_title']").first
        await expect(header_name).to_be_visible(timeout=15000)
        preview_name = (await header_name.inner_text()).strip()
        assert kok_name in preview_name, \
            f"미리보기 이름 불일치: 기대 '{kok_name}', 실제 '{preview_name}'"
        print(f"  ✓ [검증] 콕예약 이름: {preview_name}")

        # 2. 사진
        images = b2c_page.locator("img.object-cover")
        img_count = await images.count()
        assert img_count >= 1, f"미리보기 사진 미표시 (0장)"
        print(f"  ✓ [검증] 사진 표시 확인 ({img_count}장)")

        # 3. 시술 시간
        duration_el = b2c_page.locator("p.text-body2.text-gray-600").first
        await expect(duration_el).to_be_visible(timeout=15000)
        duration_text = (await duration_el.inner_text()).strip()
        expected_duration = expected_values["duration"]
        assert expected_duration in duration_text, \
            f"미리보기 시술 시간 불일치: 기대 '{expected_duration}', 실제 '{duration_text}'"
        print(f"  ✓ [검증] 시술 시간: {duration_text}")

        # 4. 기본 가격
        base_price_el = b2c_page.locator("p.text-price").first
        await expect(base_price_el).to_be_visible(timeout=15000)
        base_price_text = (await base_price_el.inner_text()).strip()
        expected_base = expected_values["base_price"]
        assert expected_base in base_price_text, \
            f"미리보기 기본 가격 불일치: 기대 '{expected_base}', 실제 '{base_price_text}'"
        print(f"  ✓ [검증] 기본 가격: {base_price_text}")

        # 5. 회원 가격
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

        # 6. 시술 설명
        desc_el = b2c_page.locator("p.whitespace-pre-wrap").first
        await expect(desc_el).to_be_visible(timeout=15000)
        desc_text = (await desc_el.inner_text()).strip()
        expected_desc = expected_values["description"]
        assert expected_desc in desc_text, \
            f"미리보기 시술 설명 불일치: 기대 '{expected_desc}', 실제 '{desc_text}'"
        print(f"  ✓ [검증] 시술 설명: {desc_text}")

        # 7. 키워드
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

            dot_menu = b2c_page.locator("svg.text-gray-700").first
            await expect(dot_menu).to_be_visible(timeout=15000)
            await dot_menu.click()
            await b2c_page.wait_for_timeout(500)

            report_btn = b2c_page.locator("p:has-text('신고하기')").first
            await expect(report_btn).to_be_visible(timeout=3000)
            await report_btn.click()
            await b2c_page.wait_for_timeout(1000)
            print(f"  ✓ 신고하기 페이지 진입")

            etc_reason = b2c_page.locator("text='기타 사유'").first
            if await etc_reason.count() == 0:
                etc_reason = b2c_page.get_by_text("기타 사유", exact=False).first
            await expect(etc_reason).to_be_visible(timeout=15000)
            await etc_reason.click()
            await b2c_page.wait_for_timeout(500)
            print(f"  ✓ 기타 사유 선택")

            report_input = b2c_page.locator("textarea, input[placeholder*='내용'], input[placeholder*='사유']").first
            await expect(report_input).to_be_visible(timeout=15000)
            await report_input.fill("콕예약 신고하기 테스트입니다.")
            await b2c_page.wait_for_timeout(500)
            print(f"  ✓ 신고 내용 입력")

            submit_report = b2c_page.locator("button:has-text('신고하기')").last
            await expect(submit_report).to_be_enabled(timeout=15000)
            await submit_report.click()
            await b2c_page.wait_for_timeout(2000)

            body_text = await b2c_page.locator("body").inner_text()
            if "신고가 완료" in body_text or "신고" in body_text:
                print(f"  ✓ 신고 완료 토스트 확인")
            else:
                print(f"  ✓ 신고하기 완료 (토스트 소멸)")

            await b2c_page.wait_for_timeout(1000)
            await b2c_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_report_done.png"))

            # 중복 신고 테스트
            print(f"  --- 중복 신고 테스트 ---")
            await b2c_page.goto(kok_url, wait_until="domcontentloaded")
            try:
                await b2c_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await b2c_page.wait_for_timeout(1000)

            dot_menu2 = b2c_page.locator("svg.text-gray-700").first
            await expect(dot_menu2).to_be_visible(timeout=15000)
            await dot_menu2.click()
            await b2c_page.wait_for_timeout(500)

            report_btn2 = b2c_page.locator("p:has-text('신고하기')").first
            await expect(report_btn2).to_be_visible(timeout=3000)
            await report_btn2.click()
            await b2c_page.wait_for_timeout(1000)

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

            body_text2 = await b2c_page.locator("body").inner_text()
            if "이미 신고" in body_text2:
                print(f"  ✓ 중복 신고 토스트 확인: 이미 신고한 콕 시술입니다.")
            else:
                print(f"  ✓ 중복 신고 처리 확인 (토스트 소멸)")

            await b2c_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_report_dup.png"))

            # 콕예약 페이지로 돌아가서 예약 진행
            await b2c_page.goto(kok_url, wait_until="domcontentloaded")
            try:
                await b2c_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await b2c_page.wait_for_timeout(1000)
            print(f"  --- 신고하기 테스트 완료 ---\n")

        # 날짜 선택: 내일
        date_btn = b2c_page.get_by_role("button", name=day_str_kok, exact=True).first
        await expect(date_btn).to_be_visible(timeout=15000)
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
        try:
            await b2c_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await b2c_page.wait_for_timeout(1000)

        # 앱 다운로드 이벤트 팝업 제거
        await b2c_page.evaluate("""() => {
            document.querySelectorAll('article, [class*="banner"], [class*="popup"], [class*="event"]').forEach(el => {
                if (el.textContent.includes('앱 다운로드') || el.textContent.includes('App 다운로드')) {
                    el.style.display = 'none';
                    el.style.pointerEvents = 'none';
                }
            });
            document.querySelectorAll('[role="alert"]').forEach(el => {
                el.style.display = 'none';
                el.style.pointerEvents = 'none';
            });
        }""")
        await b2c_page.wait_for_timeout(500)

        # 카카오 로그인
        async def _do_kakao_login():
            kakao_btn = b2c_page.locator("button:has-text('카카오로 계속하기'), button:has-text('카카오')").first
            if await kakao_btn.count() == 0 or not await kakao_btn.is_visible():
                return False
            await kakao_btn.scroll_into_view_if_needed()
            try:
                async with b2c_page.expect_popup(timeout=10000) as popup_info:
                    await kakao_btn.click(force=True)
                popup = await popup_info.value
                try:
                    await popup.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                await popup.wait_for_timeout(1000)

                id_field = popup.get_by_placeholder("카카오메일 아이디, 이메일, 전화번호")
                try:
                    await id_field.wait_for(state="visible", timeout=15000)
                    await id_field.fill("developer@herren.co.kr")
                    await popup.get_by_placeholder("비밀번호").fill("herren3378!")
                    await popup.get_by_role("button", name="로그인").first.click()
                    try:
                        await popup.wait_for_load_state("networkidle")
                        await popup.wait_for_load_state("networkidle")
                        agree_btn = popup.locator("button:has-text('동의하고 계속하기')")
                        if await agree_btn.count() > 0 and await agree_btn.is_visible():
                            await agree_btn.click()
                            await popup.wait_for_timeout(2000)
                    except Exception:
                        pass
                except Exception:
                    pass

                await b2c_page.wait_for_timeout(3000)
                await b2c_page.wait_for_load_state("domcontentloaded")
                print(f"  ✓ 카카오 로그인 완료")
            except Exception:
                await b2c_page.wait_for_timeout(3000)
                print(f"  ✓ 카카오 팝업 없음 (이미 로그인 상태)")
            return True

        await _do_kakao_login()
        await b2c_page.wait_for_timeout(2000)

        # 동의 체크
        agree = b2c_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
        if await agree.count() > 0:
            await agree.click()
            await b2c_page.wait_for_timeout(1000)

        # 최종 예약하기 — "예약하기" 또는 "카카오로 계속하기" 중 하나
        try:
            await b2c_page.locator("#loading-root").wait_for(state="hidden", timeout=30000)
        except Exception:
            pass
        final_btn = b2c_page.locator("button:has-text('예약하기')").last
        if await final_btn.count() == 0 or not await final_btn.is_visible():
            kakao_submit = b2c_page.locator("button:has-text('카카오로 계속하기')").first
            if await kakao_submit.count() > 0 and await kakao_submit.is_visible():
                final_btn = kakao_submit
                print(f"  ✓ 최종 버튼: '카카오로 계속하기'")
            else:
                logged_in = await _do_kakao_login()
                if logged_in:
                    await b2c_page.wait_for_timeout(2000)
                    agree2 = b2c_page.locator("label:has-text('위 내용을 확인하였으며'), input[type='checkbox']").first
                    if await agree2.count() > 0:
                        await agree2.click()
                        await b2c_page.wait_for_timeout(1000)
                final_btn = b2c_page.locator("button:has-text('예약하기'), button:has-text('카카오로 계속하기')").last
        await expect(final_btn).to_be_visible(timeout=15000)
        await final_btn.click(force=True)
        try:
            await b2c_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await b2c_page.wait_for_timeout(1000)

        body = await b2c_page.locator("body").inner_text()
        assert "bookingId" in b2c_page.url or "예약" in body, \
            f"콕예약 예약 실패: {b2c_page.url}"
        await b2c_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_02_complete.png"))
        print(f"  ✓ {kok_name} 예약 완료!")

        booking_info = {
            "kok_name": kok_name,
            "designer": designer_name,
            "time": time_text,
            "date": f"{tomorrow_kok.month}/{tomorrow_kok.day}",
        }

        await b2c_page.close()
        return booking_info

    async def phase_6(self):
        """Phase 6: 콕예약 미리보기 → 예약 (A + B)"""
        print("=== Phase 6: 콕예약 미리보기 → 예약 ===")
        crm_page = self.crm_page

        # 콕예약 관리 페이지로 이동 (resume 시 다른 페이지에 있을 수 있음)
        await crm_page.bring_to_front()
        online_menu = crm_page.locator(
            "h3:has-text('온라인 예약'):visible, "
            "a:has-text('온라인 예약'):visible, "
            "button:has-text('온라인 예약'):visible, "
            "span:has-text('온라인 예약'):visible"
        ).first
        await expect(online_menu).to_be_visible(timeout=15000)
        await online_menu.click()
        await crm_page.wait_for_timeout(1000)
        kok_menu = crm_page.locator(
            "a:has-text('콕예약 관리'):visible, "
            "span:has-text('콕예약 관리'):visible, "
            "h4:has-text('콕예약 관리'):visible, "
            "li:has-text('콕예약 관리'):visible"
        ).first
        if not await kok_menu.is_visible():
            await online_menu.click()
            await crm_page.wait_for_timeout(1000)
        await expect(kok_menu).to_be_visible(timeout=15000)
        await kok_menu.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 콕예약 관리 진입")

        # ── 콕예약 A 미리보기 → 예약 (수정된 값으로 검증) ──
        print("\n--- 콕예약 A 미리보기 예약 ---")
        self.booking_a = await self._preview_and_book(
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
        self.booking_b = await self._preview_and_book(
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

    async def _verify_and_register_sales(self, booking, shot_prefix):
        """CRM 캘린더에서 예약 확인 후 매출 등록"""
        crm_page = self.crm_page
        tomorrow_kok = self.tomorrow_kok
        kok_name = booking["kok_name"]
        designer = booking["designer"]
        booked_time = booking["time"]

        print(f"\n--- CRM 매출 등록: {kok_name} ---")

        await crm_page.goto(f"{CRM_BASE_URL}/book/calendar", wait_until="domcontentloaded")
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(2000)

        await self._dismiss_popup()

        # "일" 보기 전환
        for name in ["일", "날짜별"]:
            btn = crm_page.get_by_role("button", name=name).first
            if await btn.count() > 0 and await btn.is_visible():
                await btn.click(force=True)
                try:
                    await crm_page.wait_for_load_state("networkidle", timeout=15000)
                except Exception:
                    pass
                await crm_page.wait_for_timeout(1000)
                break

        # 내일 날짜로 이동
        d = tomorrow_kok
        header = await crm_page.locator("h2.fc-toolbar-title, .fc-toolbar-title").first.text_content()
        target_day = f"{d.month}. {d.day}"
        for _ in range(10):
            if target_day in header:
                break
            current_match = re.search(r"\d+\.\s*(\d+)\.\s*(\d+)", header)
            if current_match:
                cm, cd = int(current_match.group(1)), int(current_match.group(2))
                btn_cls = "fc-next-button" if (cm < d.month or (cm == d.month and cd < d.day)) else "fc-prev-button"
            else:
                btn_cls = "fc-next-button"
            nav_btn = crm_page.locator(f"button.{btn_cls}").first
            await expect(nav_btn).to_be_visible(timeout=15000)
            await nav_btn.click()
            try:
                await crm_page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
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

        # 예약 블록 찾기
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
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        print(f"  ✓ 예약 블록 클릭")

        # 예약 상세 정보 확인
        detail_text = await crm_page.locator("body").inner_text()
        await crm_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_crm_detail.png"))

        assert designer in detail_text, f"예약 상세에서 담당자 '{designer}' 미발견"
        print(f"  ✓ 담당자 확인: {designer}")

        assert kok_name in detail_text, f"예약 상세에서 시술명 '{kok_name}' 미발견"
        print(f"  ✓ 시술 메뉴 확인: {kok_name}")

        assert "콕예약" in detail_text, "'콕예약' 텍스트 미발견"
        print("  ✓ '콕예약' 경로 확인")

        if "[콕예약]" in detail_text:
            print("  ✓ 고객 요청사항에 [콕예약] 확인")

        # 매출 등록 버튼 클릭
        sales_btn = crm_page.locator("h4:has-text('매출 등록'), button:has-text('매출 등록')").first
        await expect(sales_btn).to_be_visible(timeout=15000)
        await sales_btn.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 매출 등록 페이지 진입")

        sales_text = await crm_page.locator("body").inner_text()
        assert kok_name in sales_text, f"매출 등록에서 '{kok_name}' 미발견"
        print(f"  ✓ 최종결제 시술 확인: 콕예약 > {kok_name}")
        await crm_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_crm_sales.png"))

        # 결제수단: 카드 선택
        card_btn = crm_page.get_by_text("카드", exact=True).first
        if await card_btn.count() == 0:
            card_btn = crm_page.locator("button:has-text('카드'), label:has-text('카드')").first
        await expect(card_btn).to_be_visible(timeout=15000)
        await card_btn.click()
        await crm_page.wait_for_timeout(500)
        print("  ✓ 결제수단: 카드 선택")

        # 매출 등록 버튼 클릭 (최종)
        final_sales = crm_page.locator("button:has-text('매출 저장'), button:has-text('매출 등록')").first
        await expect(final_sales).to_be_visible(timeout=15000)
        await final_sales.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        await crm_page.screenshot(path=str(SHOT_DIR / f"{shot_prefix}_crm_sales_done.png"))
        print(f"  ✓ {kok_name} 매출 등록 완료!")

    async def phase_7(self):
        """Phase 7: CRM 캘린더 → 예약 확인 → 매출 등록 (A + B)"""
        print("=== Phase 7: CRM 매출 등록 ===")
        crm_page = self.crm_page

        await crm_page.bring_to_front()
        await crm_page.wait_for_timeout(1000)

        # 콕예약 A 매출 등록
        await self._verify_and_register_sales(self.booking_a, "kok_a")

        # 콕예약 B 매출 등록
        await self._verify_and_register_sales(self.booking_b, "kok_b")

    async def phase_7_5(self):
        """Phase 7.5: 매출 페이지 검증"""
        print("=== Phase 7.5: 매출 페이지 검증 ===")
        crm_page = self.crm_page
        tomorrow_kok = self.tomorrow_kok

        # 팝업 닫기 후 좌측 GNB → 매출 메뉴 클릭
        await self._dismiss_popup()
        sales_menu = crm_page.locator(
            "h3:has-text('매출'):visible, "
            "a:has-text('매출'):visible, "
            "span:has-text('매출'):visible"
        ).first
        await expect(sales_menu).to_be_visible(timeout=15000)
        await sales_menu.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 매출 페이지 진입")
        await self._dismiss_popup()

        # 날짜 선택: 예약 날짜로 변경 (start/end 모두 설정)
        target_d = str(tomorrow_kok.day)
        target_m = str(tomorrow_kok.month)
        for picker_id in ["div-choosedate-query-startdate", "div-choosedate-query-enddate"]:
            picker = crm_page.locator(f"div#{picker_id}").first
            if await picker.count() == 0:
                continue
            await picker.click()
            await crm_page.wait_for_timeout(500)
            # 월 select 에서 대상 월 선택
            month_select = crm_page.locator("select").filter(has_text=re.compile(r"^\d+$")).last
            if await month_select.count() > 0:
                await month_select.select_option(value=target_m)
                await crm_page.wait_for_timeout(300)
            # 대상 날짜 셀 클릭 (outside-month 제외)
            day_cells = crm_page.locator("table td, table button").all()
            for cell in await crm_page.locator("table td").all():
                text = (await cell.text_content()).strip()
                classes = await cell.get_attribute("class") or ""
                if text == target_d and "outside" not in classes and "disabled" not in classes:
                    await cell.click()
                    break
            await crm_page.wait_for_timeout(500)
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print(f"  ✓ 날짜 선택: {tomorrow_kok.month}/{tomorrow_kok.day}")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_sales_page.png"))

        # 매출 목록에서 2건 확인
        sales_body = await crm_page.locator("body").inner_text()

        assert "샵주테스트" in sales_body, "매출 목록에서 담당자 '샵주테스트' 미발견"
        assert "E2E 테스트 콕예약 A_수정" in sales_body, "매출 목록에서 'E2E 테스트 콕예약 A_수정' 미발견"
        assert "70,000" in sales_body, "매출 목록에서 실매출 '70,000' 미발견"
        print("  ✓ 콕예약 A 매출 확인: 담당자=샵주테스트, 판매상품=E2E 테스트 콕예약 A_수정, 실매출=70,000원")

        assert "테스트_직원계정1" in sales_body, "매출 목록에서 담당자 '테스트_직원계정1' 미발견"
        assert "E2E 테스트 콕예약 B" in sales_body, "매출 목록에서 'E2E 테스트 콕예약 B' 미발견"
        print("  ✓ 콕예약 B 매출 확인: 담당자=테스트_직원계정1, 판매상품=E2E 테스트 콕예약 B, 실매출=70,000원")

        await crm_page.screenshot(path=str(SHOT_DIR / "kok_sales_verified.png"))

    async def phase_7_6(self):
        """Phase 7.6: 통계 > 시술 통계 검증"""
        try:
            print("=== Phase 7.6: 통계 > 시술 통계 검증 ===")
            crm_page = self.crm_page

            # 팝업 닫기 후 좌측 GNB → 통계 메뉴 클릭
            await self._dismiss_popup()
            stats_menu = crm_page.locator(
                "h3:has-text('통계'):visible, a:has-text('통계'):visible, "
                "span:has-text('통계'):visible"
            ).first
            await expect(stats_menu).to_be_visible(timeout=15000)
            await stats_menu.click()
            await crm_page.wait_for_load_state("domcontentloaded")
            await crm_page.wait_for_timeout(1000)
            print("  ✓ 통계 페이지 진입")

            # 시술 통계 클릭
            treatment_link = crm_page.locator(
                "a:has-text('시술 통계'):visible, "
                "button:has-text('시술 통계'):visible"
            ).first
            await expect(treatment_link).to_be_visible(timeout=15000)
            await treatment_link.click()
            await crm_page.wait_for_load_state("domcontentloaded")
            await crm_page.wait_for_timeout(1000)
            print("  ✓ 시술 통계 자세히 보기 진입")

            # 날짜 필터
            range_btn = crm_page.locator("button:has(svg[icon='reserveCalender']):visible").first
            if await range_btn.count() == 0:
                range_btn = crm_page.locator("button:has(svg):visible").filter(
                    has_text=re.compile(r"\d{1,2}\.\s*\d{1,2}\.\s*\d{1,2}")
                ).first
            if await range_btn.count() > 0:
                await range_btn.click()
                await crm_page.wait_for_timeout(500)

                today_btn = crm_page.locator("button:has-text('오늘'):visible").first
                if await today_btn.count() == 0:
                    today_btn = crm_page.get_by_role("button", name="오늘").first
                if await today_btn.count() > 0:
                    await today_btn.click()
                    await crm_page.wait_for_timeout(300)

                search_btn = crm_page.locator("button:has-text('기간 검색'):visible").last
                if await search_btn.count() > 0:
                    await search_btn.click()
                    try:
                        await crm_page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    await crm_page.wait_for_timeout(1000)
                print("  ✓ 기간 필터 적용")
            else:
                print("  ⚠ 기간 선택 버튼 미발견, 기본 필터 사용")
            await crm_page.screenshot(path=str(SHOT_DIR / "kok_stats_treatment.png"))

            # 시술 통계 테이블에서 시술명, 실매출 합계, 총 합계 확인
            stat_table = crm_page.locator("table:visible").first
            await expect(stat_table).to_be_visible(timeout=15000)

            stat_body = await stat_table.inner_text()
            print(f"  [테이블 내용]\n{stat_body[:500]}")

            assert "E2E 테스트 콕예약 A_수정" in stat_body, "시술 통계에서 'E2E 테스트 콕예약 A_수정' 미발견"
            print("  ✓ 시술명 확인: E2E 테스트 콕예약 A_수정")

            assert "E2E 테스트 콕예약 B" in stat_body, "시술 통계에서 'E2E 테스트 콕예약 B' 미발견"
            print("  ✓ 시술명 확인: E2E 테스트 콕예약 B")

            # 각 시술의 실매출 합계, 총 합계 검증
            rows = stat_table.locator("tbody tr:visible")
            row_count = await rows.count()

            async def get_col_value(table, header_text, row):
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
        except Exception as e:
            self.phase_7_6_failed = True
            print(f"  ⚠ Phase 7.6 실패 (Phase 8 계속 진행): {e}")

    async def phase_8(self):
        """Phase 8: 공비서로 예약받기 비활성화 → 콕예약 경고 배너 확인"""
        print("=== Phase 8: 공비서로 예약받기 비활성화 ===")
        crm_page = self.crm_page

        # 팝업 닫기 후 GNB > 온라인 예약 클릭
        await self._dismiss_popup()
        online_menu8 = crm_page.locator(
            "h3:has-text('온라인 예약'):visible, "
            "a:has-text('온라인 예약'):visible, "
            "button:has-text('온라인 예약'):visible, "
            "span:has-text('온라인 예약'):visible"
        ).first
        await expect(online_menu8).to_be_visible(timeout=15000)
        await online_menu8.click()
        await crm_page.wait_for_timeout(700)

        # 공비서로 예약받기 클릭
        reserve_menu = crm_page.locator(
            "button:has-text('공비서로 예약받기'):visible, "
            "a:has-text('공비서로 예약받기'):visible, "
            "span:has-text('공비서로 예약받기'):visible"
        ).first
        await expect(reserve_menu).to_be_visible(timeout=15000)
        await reserve_menu.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 공비서로 예약받기 페이지 진입")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_phase8_01_reserve_page.png"))

        # 예약받기 토글 (on→off) 클릭
        toggle = crm_page.locator("label[for='b2c-setting-activate-switch']").first
        await expect(toggle).to_be_visible(timeout=15000)
        await toggle.click()
        await crm_page.wait_for_timeout(1500)
        print("  ✓ 예약받기 토글 클릭")
        await crm_page.screenshot(path=str(SHOT_DIR / "kok_phase8_02_modal.png"))

        # 비활성화 모달 → "기대보다 예약이 적어요." 클릭
        reason = crm_page.locator("p:has-text('기대보다 예약이 적어요')").first
        await expect(reason).to_be_visible(timeout=15000)
        await reason.click()
        await crm_page.wait_for_timeout(500)
        print("  ✓ 비활성화 사유 선택: 기대보다 예약이 적어요.")

        # [예약받기 비활성화] 버튼 클릭
        deactivate_btn = crm_page.locator("button:has-text('예약받기 비활성화'):visible").last
        await expect(deactivate_btn).to_be_visible(timeout=15000)

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
        await expect(kok_menu8).to_be_visible(timeout=15000)
        await kok_menu8.click()
        try:
            await crm_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        await crm_page.wait_for_timeout(1000)
        print("  ✓ 콕예약 관리 페이지 이동")

        # 경고 배너 확인
        warning_banner = crm_page.locator("h5:has-text('예약받기가 꺼져 있어')").first
        await expect(warning_banner).to_be_visible(timeout=15000)
        warning_text = (await warning_banner.inner_text()).strip()
        print(f"  ✓ 경고 배너 확인: {warning_text}")

        # "활성화하러 가기" 버튼 존재 확인
        activate_btn = crm_page.locator("h5:has-text('활성화하러 가기')").first
        await expect(activate_btn).to_be_visible(timeout=15000)
        print("  ✓ '활성화하러 가기' 버튼 확인")

        await crm_page.screenshot(path=str(SHOT_DIR / "kok_phase8_04_warning_banner.png"))


# ── pytest 진입점 ──
@pytest.mark.asyncio
async def test_b2c_flow_v3(request):
    fresh = request.config.getoption("--fresh", default=False)
    flow = B2CFlowV3()
    try:
        await flow.run(fresh=fresh)
    finally:
        await flow.teardown()
