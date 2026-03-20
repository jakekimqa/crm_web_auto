# import asyncio
# import pytest
# from playwright.async_api import async_playwright, Page, expect
# from datetime import datetime, timedelta
#
#
# class GongbizAutomationTest:
#     def __init__(self):
#         self.page = None
#         self.browser = None
#         self.context = None
#
#     async def setup(self):
#         """브라우저 설정"""
#         self.playwright = await async_playwright().start()
#         self.browser = await self.playwright.chromium.launch(
#             headless=False,  # 테스트 진행상황을 보려면 False
#             slow_mo=1000  # 각 액션 사이 1초 대기
#         )
#         self.context = await self.browser.new_context(
#             viewport={'width': 1920, 'height': 1080}
#         )
#         self.page = await self.context.new_page()
#
#     async def teardown(self):
#         """브라우저 종료"""
#         if self.browser:
#             await self.browser.close()
#         if self.playwright:
#             await self.playwright.stop()
#
#     async def navigate_to_main(self):
#         """메인 페이지로 이동"""
#         await self.page.goto("https://dev-front-zero.gongbiz.kr/main")
#         await self.page.wait_for_load_state('networkidle')
#
#     async def login_with_kakao(self):
#         """카카오 로그인"""
#         try:
#             # 마이 메뉴 클릭 (로그인 페이지로 이동)
#             await self.page.click("text=마이")
#             await self.page.wait_for_load_state('networkidle')
#
#             # 로그인 클릭
#             await self.page.click("text=로그인 / 회원가입")
#
#             # 새창(팝업) 대기를 위한 Promise 설정
#             async with self.page.expect_popup() as popup_info:
#                 # 카카오 로그인 버튼 클릭
#                 await self.page.click("text=카카오로 로그인")
#
#             # 팝업 창 객체 받기
#             popup = await popup_info.value
#             await popup.wait_for_load_state('networkidle')
#
#             print("✓ 카카오 로그인 팝업 창 감지됨")
#
#             # 팝업 창에서 로그인 진행
#             # 이메일 입력 (다양한 셀렉터 시도)
#             await popup.fill('input[name="loginId"]', "developer@herren.co.kr")
#
#             # 비밀번호 입력
#             await popup.fill("input[type='password']", "herren3378!")
#
#             print("✓ 로그인 정보 입력 완료")
#
#             # 로그인 버튼 클릭 (다양한 셀렉터 시도)
#             login_selectors = [
#                 'button[type="submit"]',
#                 'button:has-text("로그인")',
#                 '.btn_login',
#                 '#login_btn',
#                 'input[type="submit"]'
#             ]
#
#             for selector in login_selectors:
#                 try:
#                     await popup.click(selector)
#                     break
#                 except:
#                     continue
#
#             # 팝업이 닫힐 때까지 대기 (로그인 성공시 자동으로 닫힘)
#             # await popup.wait_for_event('close', timeout=10000)
#             # print("✓ 카카오 로그인 팝업 닫힘 확인")
#
#             # 원본 페이지로 돌아와서 로그인 완료 확인
#             await self.page.wait_for_load_state('networkidle')
#
#             # 로그인 성공 확인 (로그인 후 변경되는 요소 확인)
#             # 예: 마이페이지에 사용자 정보가 표시되는지 확인
#             await self.page.wait_for_timeout(2000)  # 2초 대기
#
#             print("✓ 카카오 로그인 완료")
#
#         except Exception as e:
#             print(f"❌ 로그인 실패: {e}")
#             # 디버깅을 위한 스크린샷 저장
#             await self.page.screenshot(path=f"login_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
#             raise
#
#     async def verify_home_page(self):
#         """홈페이지 요소 확인"""
#         try:
#             # 홈 페이지로 이동 (로그인 후)
#             await self.page.click("text=홈")
#             await self.page.wait_for_load_state('networkidle')
#
#             # 타이틀 "공비서" 확인
#             title_element = await self.page.wait_for_selector("text=공비서")
#             assert title_element is not None, "홈페이지 타이틀 '공비서'를 찾을 수 없습니다"
#             print("✓ 홈페이지 타이틀 '공비서' 확인")
#
#             # 상단 메뉴 확인
#             menus = ["내주변", "샵 검색", "매거진", "Only 공비서", "오늘예약"]
#             for menu in menus:
#                 menu_element = await self.page.wait_for_selector(f"text={menu}")
#                 assert menu_element is not None, f"메뉴 '{menu}'를 찾을 수 없습니다"
#             print("✓ 상단 메뉴 확인 완료")
#
#             # 하단탭 확인
#             bottom_tabs = ["홈", "내주변", "콕예약", "예약내역", "마이"]
#             for tab in bottom_tabs:
#                 tab_element = await self.page.wait_for_selector(f"text={tab}")
#                 assert tab_element is not None, f"하단탭 '{tab}'를 찾을 수 없습니다"
#             print("✓ 하단탭 확인 완료")
#
#         except Exception as e:
#             print(f"❌ 홈페이지 확인 실패: {e}")
#             raise
#
#     async def check_nearby_page(self):
#         """내주변 페이지 확인"""
#         try:
#             # 내주변 탭 클릭
#             map = self.page.get_by_text("내주변").nth(1)
#             await map.click()
#             # await self.page.click("text=내주변")
#             await self.page.wait_for_load_state('networkidle')
#
#             # "내주변 가까운 뷰티샵 찾기" 텍스트 확인
#             nearby_text = await self.page.wait_for_selector("text=내주변 가까운 뷰티샵 찾기")
#             assert nearby_text is not None, "'내주변 가까운 뷰티샵 찾기' 텍스트를 찾을 수 없습니다"
#             print("✓ 내주변 페이지 '내주변 가까운 뷰티샵 찾기' 확인")
#
#         except Exception as e:
#             print(f"❌ 내주변 페이지 확인 실패: {e}")
#             raise
#
#     async def enter_nail_shop(self):
#         """네일포시즌 샵 진입"""
#         try:
#             # 홈으로 이동
#             await self.page.click("text=홈")
#             await self.page.wait_for_load_state('networkidle')
#
#             # "네일포시즌 풋풋한..." 샵 클릭
#             shop_selector = "text=네일포시즌 풋풋한"
#             await self.page.click(shop_selector)
#             await self.page.wait_for_load_state('networkidle')
#
#             # 샵 정보 확인
#             shop_name = "네일포시즌 풋풋한리쌤 역삼점"
#             shop_address = "인천 강화군 강화읍 갑룡길 3-20 (관청리), 2층"
#             bottom_sheet_text = "네일포시즌 풋풋한리쌤 역삼점"
#
#             # 샵 이름 확인
#             name_element = await self.page.wait_for_selector(f"text={shop_name}")
#             assert name_element is not None, f"샵 이름 '{shop_name}'을 찾을 수 없습니다"
#             print(f"✓ 샵 이름 확인: {shop_name}")
#
#             # 주소 확인
#             address_element = await self.page.wait_for_selector(f"text={shop_address}")
#             assert address_element is not None, f"샵 주소 '{shop_address}'를 찾을 수 없습니다"
#             print(f"✓ 샵 주소 확인: {shop_address}")
#
#             # 바텀시트 텍스트 확인
#             bottom_sheet_element = await self.page.wait_for_selector(f"text={bottom_sheet_text}")
#             assert bottom_sheet_element is not None, f"바텀시트 텍스트 '{bottom_sheet_text}'를 찾을 수 없습니다"
#             print(f"✓ 바텀시트 텍스트 확인: {bottom_sheet_text}")
#
#         except Exception as e:
#             print(f"❌ 네일포시즌 샵 진입 실패: {e}")
#             raise
#
#     async def select_service_menu(self):
#         """콕예약 서비스 선택"""
#         try:
#             # 콕예약 - 자동화_콕예약 클릭
#             await self.page.click("text=자동화_콕예약")
#             await self.page.wait_for_load_state('networkidle')
#
#             # 시술 정보 확인
#             service_name = "자동화_콕예약"
#             service_time = "1시간 소요"
#             service_price = "50,000원"
#
#             # 시술명 확인
#             name_element = await self.page.wait_for_selector(f"text={service_name}")
#             assert name_element is not None, f"시술명 '{service_name}'을 찾을 수 없습니다"
#             print(f"✓ 시술명 확인: {service_name}")
#
#             # 시술시간 확인
#             time_element = await self.page.wait_for_selector(f"text={service_time}")
#             assert time_element is not None, f"시술시간 '{service_time}'을 찾을 수 없습니다"
#             print(f"✓ 시술시간 확인: {service_time}")
#
#             # 가격 확인
#             price_element = await self.page.wait_for_selector(f"text={service_price}")
#             assert price_element is not None, f"가격 '{service_price}'을 찾을 수 없습니다"
#             print(f"✓ 가격 확인: {service_price}")
#
#         except Exception as e:
#             print(f"❌ 서비스 메뉴 선택 실패: {e}")
#             raise
#
#     async def make_reservation(self):
#         """예약하기"""
#         try:
#             # 내일 날짜 계산
#             tomorrow = datetime.now() + timedelta(days=1)
#             tomorrow_day = str(tomorrow.day)
#
#             print(f"✓ 내일 날짜는 {tomorrow_day}일")
#
#             # 내일 날짜 선택 (구체적인 셀렉터는 실제 DOM 구조에 따라 조정 필요)
#
#             cal_container = self.page.locator("div.flex.flex-nowrap.overflow-x-auto").first
#             # tmr_btn = cal_container.get_by_text(name='{tomorrow.day}')
#             # tmr_btn = cal_container.get_by_role("button", name=tomorrow.day).locator(":visible")
#             await cal_container.locator(f'button:has(> p:has-text("{tomorrow_day}"))').first.click()
#             print(f"✓ 내일 날짜 선택: {tomorrow_day}일")
#
#
#
#             # 은솔원장 선택
#             await self.page.click("text=은솔 원장")
#
#             # 오전 9시 선택
#             reserve_time = self.page.get_by_text("오전 9:00").nth(1)
#             await reserve_time.click()
#
#             # 바텀시트 변경 확인
#             deposit_text = "예약금 25,000원"
#             payment_text = "예약금만 미리 결제해요"
#             reservation_button = "예약하기"
#
#             # 예약금 텍스트 확인
#             deposit_element = await self.page.wait_for_selector(f"text={deposit_text}")
#             assert deposit_element is not None, f"예약금 텍스트 '{deposit_text}'를 찾을 수 없습니다"
#             print(f"✓ 예약금 확인: {deposit_text}")
#
#             # 결제 안내 텍스트 확인
#             payment_element = await self.page.wait_for_selector(f"text={payment_text}")
#             assert payment_element is not None, f"결제 안내 텍스트 '{payment_text}'를 찾을 수 없습니다"
#             print(f"✓ 결제 안내 확인: {payment_text}")
#
#             # 예약하기 버튼 클릭
#             await self.page.click(f"button:has-text('{reservation_button}')")
#             await self.page.wait_for_load_state('networkidle')
#             print("✓ 예약하기 버튼 클릭 완료")
#
#         except Exception as e:
#             print(f"❌ 예약하기 실패: {e}")
#             raise
#
#     async def verify_payment_page(self):
#         """결제 페이지 확인"""
#         try:
#             # 결제 페이지 정보 확인
#             shop_name = "네일포시즌 풋풋한리쌤 역삼점"
#             customer_name = "헤렌테스트"
#             payment_amount = "25,000원"
#             customer_request = "[콕예약] 자동화_콕예약"
#
#             # 샵 이름 확인
#             shop_element = await self.page.wait_for_selector(f"text={shop_name}")
#             assert shop_element is not None, f"샵 이름 '{shop_name}'을 찾을 수 없습니다"
#             print(f"✓ 샵 이름 확인: {shop_name}")
#
#             # 예약자 이름 확인
#             customer_element = await self.page.wait_for_selector(f"text={customer_name}")
#             assert customer_element is not None, f"예약자 이름 '{customer_name}'을 찾을 수 없습니다"
#             print(f"✓ 예약자 이름 확인: {customer_name}")
#
#             # 결제 금액 확인
#             amount_element = await self.page.wait_for_selector(f"text={payment_amount}")
#             assert amount_element is not None, f"결제 금액 '{payment_amount}'을 찾을 수 없습니다"
#             print(f"✓ 결제 금액 확인: {payment_amount}")
#
#             # 고객 요청사항 확인
#             request_element = await self.page.wait_for_selector(f"text={customer_request}")
#             assert request_element is not None, f"고객 요청사항 '{customer_request}'를 찾을 수 없습니다"
#             print(f"✓ 고객 요청사항 확인: {customer_request}")
#
#
#             # 우측상단 닫기 버튼 클릭
#
#             close_btn = self.page.get_by_role("button", name="닫기").locator(":visible").first
#             await close_btn.click()
#             print("✓ 결제 페이지 닫기 버튼 클릭/콕예약 페이지")
#
#             # 뒤로가기 버튼 클릭
#             back_btn = self.page.get_by_role("button", name="뒤로가기").locator(":visible").first
#             await back_btn.click()
#             print("✓ 뒤로가기 버튼 클릭/샵 상세 페이지")
#
#
#
#
#         except Exception as e:
#             print(f"❌ 결제 페이지 확인 실패: {e}")
#             raise
#
#     async def verify_shop_detail_again(self):
#         """샵 상세 페이지 재검증"""
#         try:
#             # 샵 이름 검증
#             shop_name = "네일포시즌 풋풋한리쌤 역삼점"
#             name_element = await self.page.wait_for_selector(f"text={shop_name}")
#             assert name_element is not None, f"샵 이름 '{shop_name}'을 찾을 수 없습니다"
#             print(f"✓ 샵 이름 재검증 완료: {shop_name}")
#
#             # 바텀시트에서 샵 이름 검증
#             bottom_sheet_name = await self.page.wait_for_selector(f"text={shop_name}")
#             assert bottom_sheet_name is not None, f"바텀시트 샵 이름 '{shop_name}'을 찾을 수 없습니다"
#             print(f"✓ 바텀시트 샵 이름 검증 완료: {shop_name}")
#
#         except Exception as e:
#             print(f"❌ 샵 상세 페이지 재검증 실패: {e}")
#             raise
#
#     async def select_french_powder_service(self):
#         """프렌치/파우더 서비스 선택"""
#         try:
#             # 아래로 스크롤하여 프렌치/파우더 찾기
#             await self.page.evaluate("window.scrollBy(0, 300)")
#             await self.page.wait_for_timeout(1000)
#
#             # 프렌치/파우더 클릭
#             await self.page.click("text=프렌치/파우더")
#             await self.page.wait_for_load_state('networkidle')
#             print("✓ 프렌치/파우더 서비스 선택")
#
#             # 예약금 0원 검증
#             deposit_text = "예약금 0원"
#             deposit_element = await self.page.wait_for_selector(f"text={deposit_text}")
#             assert deposit_element is not None, f"예약금 텍스트 '{deposit_text}'를 찾을 수 없습니다"
#             print(f"✓ 예약금 검증 완료: {deposit_text}")
#
#             # [1 예약하기] 버튼 클릭
#             reservation_button_selectors = [
#                 "button:has-text('예약하기')",
#                 "[data-count='1']:has-text('예약하기')"
#             ]
#
#             for selector in reservation_button_selectors:
#                 try:
#                     await self.page.click(selector)
#                     break
#                 except:
#                     continue
#
#             await self.page.wait_for_load_state('networkidle')
#             print("✓ [예약하기] 버튼 클릭")
#
#         except Exception as e:
#             print(f"❌ 프렌치/파우더 서비스 선택 실패: {e}")
#             raise
#
#     async def select_staff_eunsol(self):
#         """은솔 원장 선택"""
#         try:
#             # 타이틀 "담당자 선택" 검증
#             title_text = "담당자 선택"
#             title_element = await self.page.wait_for_selector(f"text={title_text}")
#             assert title_element is not None, f"타이틀 '{title_text}'를 찾을 수 없습니다"
#             print(f"✓ 타이틀 검증: {title_text}")
#
#             # 은솔 원장의 [선택] 버튼 클릭
#             staff_list = self.page.locator("li:has(p:has-text('은솔 원장'))").first
#             select_btn = staff_list.get_by_role("button", name="선택").first
#             await select_btn.click()
#
#             print("✓ 은솔 원장 선택 완료")
#
#         except Exception as e:
#             print(f"❌ 은솔 원장 선택 실패: {e}")
#             raise
#
#     async def select_datetime_tomorrow_10am(self):
#         """내일 날짜 오전 9시 선택"""
#         try:
#             # 타이틀 "날짜/시간 선택" 검증
#             title_text = "날짜/시간 선택"
#             title_element = await self.page.wait_for_selector(f"text={title_text}")
#             assert title_element is not None, f"타이틀 '{title_text}'를 찾을 수 없습니다"
#             print(f"✓ 타이틀 검증: {title_text}")
#
#             # 내일 날짜 계산
#             tomorrow = datetime.now() + timedelta(days=1)
#             tomorrow_day = str(tomorrow.day)
#
#             # 내일 날짜 클릭
#             tmr_date = self.page.locator(f'div.cursor-pointer:has(p:has-text("{tomorrow_day}"))').locator(":visible").first
#             await tmr_date.click()
#             await self.page.wait_for_timeout(1000)
#
#             print(f"✓ 내일 날짜 선택: {tomorrow_day}일")
#
#             # 오전 9시 선택
#             time_selectors = [
#                 "text=9:00",
#                 "[data-time='9:00']",
#                 ".time-slot:has-text('9:00')"
#             ]
#
#             for selector in time_selectors:
#                 try:
#                     await self.page.click(selector)
#                     break
#                 except:
#                     continue
#
#             await self.page.wait_for_timeout(1000)
#             print("✓ 오전 9시 선택")
#
#             # [예약하기] 버튼 클릭
#             await self.page.click("button:has-text('예약하기')")
#             await self.page.wait_for_load_state('networkidle')
#             print("✓ [예약하기] 버튼 클릭")
#
#         except Exception as e:
#             print(f"❌ 날짜/시간 선택 실패: {e}")
#             raise
#
#     async def verify_payment_page_zero_amount(self):
#         """결제 페이지 검증 (0원)"""
#         try:
#             # 타이틀 "결제" 검증
#             title_text = "결제"
#             title_element = await self.page.wait_for_selector(f"text={title_text}")
#             assert title_element is not None, f"타이틀 '{title_text}'를 찾을 수 없습니다"
#             print(f"✓ 타이틀 검증: {title_text}")
#
#             # 예약 정보 - 샵 이름 검증
#             shop_name = "네일포시즌 풋풋한리쌤 역삼점"
#             shop_element = await self.page.wait_for_selector(f"text={shop_name}")
#             assert shop_element is not None, f"샵 이름 '{shop_name}'을 찾을 수 없습니다"
#             print(f"✓ 예약 정보 샵 이름 검증: {shop_name}")
#
#             # 예약자 이름 검증
#             customer_name = "헤렌테스트"
#             customer_element = await self.page.wait_for_selector(f"text={customer_name}")
#             assert customer_element is not None, f"예약자 이름 '{customer_name}'을 찾을 수 없습니다"
#             print(f"✓ 예약자 이름 검증: {customer_name}")
#
#             # 지금 결제할 금액 0원 검증
#             payment_amount = "지금 결제할 금액 : 0원"
#             # 여러 가능한 텍스트 형태로 시도
#             amount_texts = [
#                 "지금 결제할 금액 : 0원",
#                 "지금 결제할 금액: 0원",
#                 "결제할 금액 : 0원",
#                 "결제할 금액: 0원",
#                 "0원"
#             ]
#
#             amount_found = False
#             for amount_text in amount_texts:
#                 try:
#                     amount_element = await self.page.wait_for_selector(f"text={amount_text}", timeout=3000)
#                     if amount_element:
#                         amount_found = True
#                         print(f"✓ 결제 금액 검증: {amount_text}")
#                         break
#                 except:
#                     continue
#
#             assert amount_found, "결제 금액 0원을 찾을 수 없습니다"
#
#             # 고객 요청사항 입력
#             request_text = "웹 자동화 테스트입니다."
#             await self.page.get_by_placeholder("요청할 메시지나 이미지를 남겨주세요.").fill(request_text)
#
#
#             print(f"✓ 고객 요청사항 입력: {request_text}")
#
#             # 바텀시트 결제 금액 0원 재검증
#             bottom_amount_texts = [
#                 "지금 결제할 금액 : 0원",
#                 "지금 결제할 금액: 0원",
#                 "0원"
#             ]
#
#             bottom_amount_found = False
#             for amount_text in bottom_amount_texts:
#                 try:
#                     bottom_element = await self.page.wait_for_selector(f"text={amount_text}", timeout=3000)
#                     if bottom_element:
#                         bottom_amount_found = True
#                         print(f"✓ 바텀시트 결제 금액 재검증: {amount_text}")
#                         break
#                 except:
#                     continue
#
#             assert bottom_amount_found, "바텀시트에서 결제 금액 0원을 찾을 수 없습니다"
#
#             # [예약하기] 버튼 클릭
#             await self.page.click("button:has-text('예약하기')")
#             await self.page.wait_for_load_state('networkidle')
#             print("✓ [예약하기] 버튼 클릭")
#
#         except Exception as e:
#             print(f"❌ 결제 페이지 검증 (0원) 실패: {e}")
#             raise
#
#     async def verify_reservation_complete(self):
#         """예약 완료 페이지 검증"""
#         try:
#             # "예약 완료 되었어요." 검증
#             complete_text = "예약 완료 되었어요."
#             complete_element = await self.page.wait_for_selector(f"text={complete_text}")
#             assert complete_element is not None, f"완료 메시지 '{complete_text}'를 찾을 수 없습니다"
#             print(f"✓ 예약 완료 메시지 검증: {complete_text}")
#
#             # 샵 이름 검증
#             shop_name = "네일포시즌 풋풋한리쌤 역삼점"
#             shop_element = await self.page.wait_for_selector(f"text={shop_name}")
#             assert shop_element is not None, f"샵 이름 '{shop_name}'을 찾을 수 없습니다"
#             print(f"✓ 샵 이름 검증: {shop_name}")
#
#             # 바텀시트 버튼 검증
#             bottom_button_text = "앱에서 예약내역 확인하기"
#             button_element = await self.page.wait_for_selector(f"text={bottom_button_text}")
#             assert button_element is not None, f"바텀시트 버튼 '{bottom_button_text}'를 찾을 수 없습니다"
#             print(f"✓ 바텀시트 버튼 검증: {bottom_button_text}")
#
#             # 닫기 버튼 클릭
#             close_btn = self.page.get_by_role("button", name="닫기").locator(":visible").first
#             await close_btn.click()
#             print("✓ 닫기 버튼 클릭 완료")
#
#         except Exception as e:
#             print(f"❌ 예약 완료 페이지 검증 실패: {e}")
#             raise
#
#
#
#     async def run_full_test(self):
#         """전체 테스트 실행"""
#         try:
#             await self.setup()
#
#             print("🚀 공비서 B2C 자동화 테스트 시작")
#
#             # 1. 메인 페이지 접속
#             print("\n1. 메인 페이지 접속")
#             await self.navigate_to_main()
#
#             # 2. 카카오 로그인
#             print("\n2. 카카오 로그인")
#             await self.login_with_kakao()
#
#             # 3. 홈페이지 요소 확인
#             print("\n3. 홈페이지 요소 확인")
#             await self.verify_home_page()
#
#             # 4. 내주변 페이지 확인
#             print("\n4. 내주변 페이지 확인")
#             await self.check_nearby_page()
#
#             # 5. 네일포시즌 샵 진입
#             print("\n5. 네일포시즌 샵 진입")
#             await self.enter_nail_shop()
#
#             # 6. 서비스 메뉴 선택
#             print("\n6. 콕예약 서비스 선택")
#             await self.select_service_menu()
#
#             # 7. 예약하기
#             print("\n7. 예약하기")
#             await self.make_reservation()
#
#             # 8. 결제 페이지 확인
#             print("\n8. 결제 페이지 확인")
#             await self.verify_payment_page()
#
#             # 9. 샵 상세 페이지 재검증
#             print("\n10. 샵 상세 페이지 재검증")
#             await self.verify_shop_detail_again()
#
#             # 10. 프렌치/파우더 서비스 선택
#             print("\n11. 프렌치/파우더 서비스 선택")
#             await self.select_french_powder_service()
#
#             # 11. 은솔 원장 선택
#             print("\n12. 은솔 원장 선택")
#             await self.select_staff_eunsol()
#
#             # 12. 내일 오전 9시 선택
#             print("\n13. 내일 날짜 오전 10시 선택")
#             await self.select_datetime_tomorrow_10am()
#
#             # 13. 결제 페이지 검증 (0원)
#             print("\n14. 결제 페이지 검증 (0원)")
#             await self.verify_payment_page_zero_amount()
#
#             # 14. 예약 완료 페이지 검증
#             print("\n15. 예약 완료 페이지 검증")
#             await self.verify_reservation_complete()
#
#
#             print("\n🎉 모든 테스트가 성공적으로 완료되었습니다!")
#
#         except Exception as e:
#             print(f"\n❌ 테스트 실패: {e}")
#             raise
#         finally:
#             await self.teardown()
#
#
# # 개별 테스트 함수들 (pytest 사용시)
# @pytest.mark.asyncio
# async def test_gongbiz_full_flow():
#     """전체 플로우 테스트"""
#     test = GongbizAutomationTest()
#     await test.run_full_test()
#
#
# # @pytest.mark.asyncio
# # async def test_login_only():
# #     """로그인만 테스트"""
# #     test = GongbizAutomationTest()
# #     try:
# #         await test.setup()
# #         await test.navigate_to_main()
# #         await test.login_with_kakao()
# #         print("✓ 로그인 테스트 완료")
# #     finally:
# #         await test.teardown()
# #
# #
# # @pytest.mark.asyncio
# # async def test_home_verification():
# #     """홈페이지 요소 확인만 테스트"""
# #     test = GongbizAutomationTest()
# #     try:
# #         await test.setup()
# #         await test.navigate_to_main()
# #         await test.login_with_kakao()
# #         await test.verify_home_page()
# #         print("✓ 홈페이지 확인 테스트 완료")
# #     finally:
# #         await test.teardown()
#
#
# # @pytest.mark.asyncio
# # async def test_french_powder_reservation():
# #     """프렌치/파우더 예약 플로우만 테스트"""
# #     test = GongbizAutomationTest()
# #     try:
# #         await test.setup()
# #         await test.navigate_to_main()
# #         await test.login_with_kakao()
# #         await test.verify_home_page()
# #         await test.enter_nail_shop()
# #         await test.verify_shop_detail_again()
# #         await test.select_french_powder_service()
# #         await test.select_staff_eunsol()
# #         await test.select_datetime_tomorrow_10am()
# #         await test.verify_payment_page_zero_amount()
# #         await test.verify_reservation_complete()
# #         print("✓ 프렌치/파우더 예약 테스트 완료")
# #     finally:
# #         await test.teardown()
# #
# # @pytest.mark.asyncio
# # async def test_cockbook_reservation():
# #     """콕예약 플로우만 테스트"""
# #     test = GongbizAutomationTest()
# #     try:
# #         await test.setup()
# #         await test.navigate_to_main()
# #         await test.login_with_kakao()
# #         await test.verify_home_page()
# #         await test.enter_nail_shop()
# #         await test.select_service_menu()
# #         await test.make_reservation()
# #         await test.verify_payment_page()
# #         print("✓ 콕예약 테스트 완료")
# #     finally:
# #         await test.teardown()
#
#
#
#
# # 메인 실행 함수
# async def main():
#     """테스트 실행"""
#     test = GongbizAutomationTest()
#     await test.run_full_test()
#
#
# if __name__ == "__main__":
#     # 직접 실행
#     asyncio.run(main())
#
# # 사용법:
# # 1. 터미널에서 직접 실행: python test_gongbiz.py
# # 2. pytest로 실행: pytest test_gongbiz.py -v
# # 3. 특정 테스트만 실행: pytest test_gongbiz.py::test_login_only -v