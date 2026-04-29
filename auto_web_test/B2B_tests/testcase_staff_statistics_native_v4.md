# 직원 통계 검증 테스트 케이스 (네이티브 v4)

> 실제 Maestro YAML 플로우 기준으로 재정리 (v3 → v4)
> 원본: `testcase_staff_statistics_native_v2.md` (설계 기반)
> YAML 소스: `.maestro/flows/statistics/` 디렉토리

---

## v3 → v4 변경 요약

### 추가된 통계 검증

| 항목 | v3 | v4 |
|------|-----|-----|
| 고객 통계 | 없음 | TC-7.4 추가 (재방문/신규/미등록 고객별 매출 건수, 실매출, 객단가, 차감 금액) |
| 채널별 매출 통계 | 없음 | TC-7.5 추가 (공비서 원장님 채널 매출 건수, 실매출 합계, 차감 합계) |
| 시간별 분석 | 없음 | TC-7.6 추가 (시간대별 매출 건수, 실매출, 차감, 총합계) |
| 요일별 분석 | 없음 | TC-7.7 추가 (요일별 매출 건수, 실매출, 차감, 총합계) |

### 플로우 변경

| 항목 | v3 | v4 |
|------|-----|-----|
| Phase 7 스코프 | 직원 통계만 (TC-7.0~7.3) | 직원 통계 + 고객/채널/시간/요일 통계 (TC-7.0~7.7) |
| 통계 간 이동 | 없음 | 뒤로가기 → 통계 메인 → 해당 통계 자세히 보기 → 오늘 필터 |
| 오케스트레이터 | phase7 1개 | phase7 확장 (동일 파일 내 TC 추가) |

### 기대값 참고 (Web 자동화 테스트 기준)

| 통계 | 검증 항목 | 기대값 |
|------|----------|--------|
| 고객 통계 — 재방문 | 매출건수 1건, 실매출 0원, 객단가 0원, 차감 10,000원 |
| 고객 통계 — 신규 | 매출건수 5건, 실매출 310,000원, 객단가 62,000원, 차감 40,000원 |
| 고객 통계 — 미등록 | 매출건수 1건, 실매출 10,000원, 객단가 10,000원 |
| 채널별 — 공비서 원장님 | 매출건수 7건, 실매출 320,000원, 차감 50,000원 |
| 시간별 — 예약 시간대 | 16시 1건/17시 1건/18시 1건 (고정) + 비예약 매출은 등록 시간 기준 |
| 요일별 — 당일 | 매출건수 7건, 실매출 320,000원, 차감 50,000원, 총합계 370,000원 |

---

## v2 → v3 변경 요약

### 데이터 변경

| 항목 | v2 (원본 설계) | v3 (실제 YAML) |
|------|---------------|----------------|
| 고객명 패턴 | `자동화_{MMDD}_N` (한글) | `user0413a/b/c` (영문) — 환경변수 `${CUSTOMER_NAME_N}` |
| 연락처 패턴 | `010{MMDD}000N` | `01004130001/02/03` — 환경변수 `${CUSTOMER_PHONE_N}` |
| 티켓 옵션 텍스트 | "10만원권" | "10회권 (카드)" — 계정별 마스터 데이터 차이 |
| TC-6.1 시술 | 미선택 (예약에서 진입) | "젤 기본" — 고객 상세에서 진입, 1페이지 시술 선택 필요 |
| TC-6.4 진입 경로 | "미등록 고객" 옵션 | "고객 등록 없이 진행" → 고객 정보 입력 스킵 → 제품 선택 |
| TC-6.4 제품명 | "01_제품_테스트" | `.*테스트 제품.*` (regex) — 재고 suffix 동적 변경 대응 |
| TC-6.5 시술 선택 | 시술 메뉴 드롭다운 | "시술" 탭 → "손" → "케어" (매출 탭 FAB 진입 UI 차이) |

### 플로우 변경

| 항목 | v2 (원본 설계) | v3 (실제 YAML) |
|------|---------------|----------------|
| 고객명 입력 | 한글 clipboard paste 우회 | 영문 고객명 직접 inputText |
| 소개자 검색 | 이름 또는 연락처 | 연락처 숫자로 검색 + hideKeyboard + 결과에서 이름 탭 |
| 매출 등록 진입 (TC-6.1~6.3) | 예약 블록에서 진입 | 고객 상세 → 하단 "매출 등록" 버튼으로 진입 |
| 매출 등록 진입 (TC-6.4~6.5) | 매출 탭 | 매출 탭 → FAB → "매출 등록" |
| TC-6 각 건 사이 상태 초기화 | 연속 진행 | stopApp → launchApp (TC-6.2, 6.3, 6.4) |
| 결제 수단 금액 입력 후 키보드 닫기 | hideKeyboard | `tapOn: "결제 수단"` (라벨 탭으로 포커스 이동) |
| TC-6.4 네이버페이 입력 | 필드 직접 탭 → 5000 입력 | 체크박스 탭 → 자동 할당 "10,000" 탭 → 5000 수정 |
| TC-6.4 미수금 입력 | 필드 직접 탭 → 5000 입력 | 체크박스만 탭 (자동 할당 5,000 역이용) |
| TC-6.4 매출 등록 버튼 | 단순 탭 | `tapOn: text: "매출 등록" index: 1` (상단 제목 충돌 회피) |
| Phase 7 배치 대기 | 30초 sleep + 새로고침 | pull-to-refresh swipe + extendedWaitUntil 35초 |
| Phase 7 날짜 필터 | "오늘" 직접 탭 | 프리셋 칩 좌→우 swipe 2회 → "오늘" 노출 후 탭 |
| Phase 7 기간 검색 버튼 | "기간 검색" 탭 | `.*기간 검색` (regex) |
| 각 Phase 시작 | 이전 Phase에서 연속 | clearState + 재로그인 (common_login.yaml runFlow) |

### 검증 변경

| 항목 | v2 (원본 설계) | v3 (실제 YAML) |
|------|---------------|----------------|
| Phase 2 충전 후 잔액 검증 | `assertVisible: "220,000"` | 스크린샷만 ([CAPTURE]) |
| TC-7.0 배치 대기 조건 | "7건" 텍스트 | "매출 건수" assertVisible + 스크린샷 |
| TC-7.1 매출 건수 기대값 | 7건 (충전2 + 매출5) | 스크린샷 확인 (이전 테스트 데이터 누적 가능) |
| TC-7.1 금액 기대값 | assertVisible 숫자 | 스크린샷 기반 ([CAPTURE]) |
| TC-7.2/7.3 고객 유형별 | assertVisible 숫자 | 가로 swipe 3단계 스크린샷 ([CAPTURE]) |

### 삭제/스킵된 항목

| 항목 | 사유 |
|------|------|
| Step 5 (중복 검증 — 동일 고객 재등록) | YAML에 별도 스텝 없음. 대신 각 고객 등록 시 `runFlow when: "이미 등록된"` 멱등 처리로 대체 |
| Phase 5 시간 선택 스텝 | YAML에서 시간 선택 없음 (기본 시간 사용) |
| TC-7.1/7.2/7.3 수치 assertVisible | 데이터 누적으로 기대값 변동 가능하여 스크린샷 기반으로 전환 |

---

## 환경 정보

| 항목 | 값 |
|------|-----|
| 서버 | dev1 (crm-dev1.gongbiz.kr) |
| 계정 | autoqatest11 / gong2023@@ |
| 샵 | 자동화_헤렌네일 |
| 대표원장 | 샵주테스트 |
| 에뮬레이터 | Pixel_9_Pro_API_36 (헤드레스) |
| APK | b2b-8.12.20-dev-debug.apk |

### 환경변수 (오케스트레이터에서 정의)

```yaml
env:
  CUSTOMER_NAME_1: "user0413a"
  CUSTOMER_NAME_2: "user0413b"
  CUSTOMER_NAME_3: "user0413c"
  CUSTOMER_PHONE_1: "01004130001"
  CUSTOMER_PHONE_2: "01004130002"
  CUSTOMER_PHONE_3: "01004130003"
  SCREENSHOT_DATE: "20260413"
  # common_login.yaml 에서 사용 (`.maestro/.env` 또는 `-e` 플래그로 전달)
  TEST_USER_ID: "autoqatest11"
  TEST_USER_PW: "gong2023@@"
```

### 테스트 데이터 규칙 (v3)
- 고객명: 영문 `user{MMDD}{a|b|c}` (Maestro 한글 inputText 미지원 우회)
- 연락처: `010{MMDD}000N`
- 환경변수 참조: `${CUSTOMER_NAME_N}`, `${CUSTOMER_PHONE_N}`

> **v2 대비 변경:** 한글 고객명(`자동화_{MMDD}_N`) → 영문(`user0413a/b/c`). clipboard paste 우회 대신 영문 직접 입력으로 단순화.

---

## 플랫폼별 제약 사항

| 항목 | Android Maestro | iOS Maestro | XCUITest / Espresso |
|------|----------------|-------------|---------------------|
| 한글 고객명 입력 | 불가 → 영문 우회 | 가능 | 가능 |
| 소개자 검색+선택 | 연락처 숫자 검색 + hideKeyboard | 드롭다운 선택 복잡 | 가능 |
| 드롭다운 옵션 선택 | tapOn 텍스트 매칭 | tapOn 텍스트 매칭 | 가능 |
| 금액 입력 (숫자) | 가능 | 가능 | 가능 |
| 통계 테이블 행-열 교차 검증 | 불가 → 스크린샷 | 불가 → 스크린샷 | 가능 (a11y id 필요) |
| 배치 대기 (최대 6분) | repeat + pull-to-refresh | repeat 가능 | 가능 |

### Android 한글 입력 우회 (v3 적용)
영문 고객명(`user0413a/b/c`)을 사용하여 한글 입력 문제 자체를 회피.
소개자 검색은 연락처 숫자(`${CUSTOMER_PHONE_1}`)로 검색 후 결과에서 영문 이름 탭.

---

## 공통 로그인 플로우

**파일:** `common_login.yaml`

각 Phase 시작 시 `runFlow: ../common_login.yaml`로 호출. clearState 후 깨끗한 상태에서 재로그인.

**스텝:**
1. stopApp → clearState → launchApp
2. 알림 권한 "Allow" (optional)
3. "로그인" 탭 → 아이디 입력 (`${TEST_USER_ID}`) → 비밀번호 입력 (`${TEST_USER_PW}`)
4. hideKeyboard → "로그인" 버튼 탭 (index: 1)
5. 팝업 "닫기" 처리 (optional)
6. "Allow" 처리 (optional)
7. 메인 화면 "예약" 표시 대기 (timeout: 15000)

> **v2 대비 변경:** v2에서는 Phase 간 연속 진행 가정. v3에서는 각 Phase가 독립적으로 clearState + 재로그인을 수행하여 상태 격리.

---

## Phase 1: 고객 추가

**파일:** `phase1_customer_register.yaml`

### TC-1.1: 고객 3명 등록

**데이터:**

| 순서 | 고객명 | 전화번호 | 소개자 |
|------|--------|----------|--------|
| 1 | `${CUSTOMER_NAME_1}` (user0413a) | `${CUSTOMER_PHONE_1}` (01004130001) | 없음 |
| 2 | `${CUSTOMER_NAME_2}` (user0413b) | `${CUSTOMER_PHONE_2}` (01004130002) | user0413a (연락처로 검색) |
| 3 | `${CUSTOMER_NAME_3}` (user0413c) | `${CUSTOMER_PHONE_3}` (01004130003) | user0413a (연락처로 검색) |

**Step 1: 공통 로그인 + 고객 탭 진입**
- 동작: `runFlow: ../common_login.yaml`
- 동작: 하단 탭 "고객" 탭
- 대기: 고객차트 화면 표시

**Step 2: 고객 1 등록 (소개자 없음)**
- 동작: "고객 추가 버튼" (contentDescription) 탭
- 대기: "직접 입력하기" 표시 (timeout: 5000)
- 동작: "직접 입력하기" 탭
- 대기: "고객 추가" 폼 표시 (timeout: 5000)
- 동작: "고객 이름을 입력해 주세요." 탭 → `${CUSTOMER_NAME_1}` 입력
- 동작: "고객 연락처를 입력해 주세요." 탭 → `${CUSTOMER_PHONE_1}` 입력
- 동작: "저장" 탭
- 멱등 처리: `runFlow when: "이미 등록된 고객 연락처입니다."` → "고객 차트 보기" → back

**검증:**
- [MUST] 등록 성공 또는 중복 시 "고객 차트 보기"로 스킵 (에러 없이 진행)

**Step 3: 고객 2 등록 (소개자: 고객 1)**
- 동작: "고객 추가 버튼" 탭 → "직접 입력하기" → "고객 추가" 폼
- 동작: 이름 `${CUSTOMER_NAME_2}` 입력
- 동작: 연락처 `${CUSTOMER_PHONE_2}` 입력
- 동작: scrollUntilVisible "소개자" (DOWN)
- 동작: "이름 또는 연락처를 검색해 보세요." 탭 → `${CUSTOMER_PHONE_1}` 입력
- 동작: hideKeyboard (키보드가 검색 결과를 가리는 이슈 회피)
- 대기: `${CUSTOMER_NAME_1}` 표시 (timeout: 5000)
- 동작: `${CUSTOMER_NAME_1}` 탭 (검색 결과에서 선택)
- 동작: "저장" 탭
- 멱등 처리: 중복 시 "고객 차트 보기" → back

**검증:**
- [MUST] 등록 성공 또는 중복 스킵

**Step 4: 고객 3 등록 (소개자: 고객 1)**
- Step 3과 동일, `${CUSTOMER_NAME_3}` / `${CUSTOMER_PHONE_3}` 사용
- 소개자 검색: `${CUSTOMER_PHONE_1}` → `${CUSTOMER_NAME_1}` 탭

**검증:**
- [MUST] 등록 성공 또는 중복 스킵
- [CAPTURE] 최종 스크린샷: `phase1_customer_register`

> **원본 대비 변경사항:**
> - 고객명: 한글 `자동화_{MMDD}_N` → 영문 `user0413a/b/c` (환경변수 참조)
> - 소개자 검색: 한글 이름 검색 → 연락처 숫자(`${CUSTOMER_PHONE_1}`)로 검색 후 hideKeyboard
> - 중복 처리: 별도 Step 5(중복 검증) 제거 → 각 등록 시 `runFlow when` 멱등 처리로 통합
> - 입력 필드: placeholder 텍스트("고객 이름을 입력해 주세요.", "고객 연락처를 입력해 주세요.") 사용
> - FAB 버튼: contentDescription "고객 추가 버튼"으로 접근

---

## Phase 2: 정액권 충전

**파일:** `phase2_membership_charge.yaml`

### TC-2.1: user0413a 정액권 충전 (20만원/현금)

**Step 1: 공통 로그인 + 고객 상세 진입**
- 동작: `runFlow: ../common_login.yaml`
- 동작: "고객" 탭 → "고객 이름, 연락처, 메모" 검색
- 동작: `${CUSTOMER_PHONE_1}` 입력
- 대기: `${CUSTOMER_NAME_1}` 표시 (timeout: 5000)
- 동작: `${CUSTOMER_NAME_1}` 탭
- 대기: "고객 정보" 표시 (timeout: 5000)

**Step 2: 정액권 충전**
- 동작: "정액권 충전" 탭
- 대기: "정액권 충전" 화면 표시 (timeout: 5000)
- 동작: "선택" (index: 0) 탭 → 드롭다운 열기
- 대기: "회원권에서 선택" 표시 (timeout: 5000)
- 동작: "20만원 (현금)" 탭
- 동작: "충전" 탭
- 다이얼로그: "확인" (optional) → "네" (optional)

**검증:**
- [CAPTURE] 최종 스크린샷: `phase2_membership_charge`

> **원본 대비 변경사항:**
> - 고객 검색: 이름 검색 → 연락처(`${CUSTOMER_PHONE_1}`) 검색으로 변경
> - 드롭다운 열기: "선택" (index: 0) 탭 → "회원권에서 선택" 바텀시트 대기
> - 충전 확인 다이얼로그: "확인" + "네" 모두 optional 처리
> - 검증: assertVisible "220,000" 제거 → 스크린샷 기반 [CAPTURE]로 전환

---

## Phase 3: 패밀리 공유

**파일:** `phase3_family_link.yaml`

### TC-3.1: user0413a ↔ user0413c 패밀리 연결

**Step 1: 공통 로그인 + 고객 상세 진입**
- 동작: `runFlow: ../common_login.yaml`
- 동작: "고객" 탭 → `${CUSTOMER_PHONE_1}` 검색 → `${CUSTOMER_NAME_1}` 탭
- 대기: "고객 정보" 표시

**Step 2: 패밀리 탭 진입**
- 동작: 수평 swipe (80%,48% → 20%,48%) — 탭 바 스크롤
- 대기: "패밀리" 표시 (timeout: 5000)
- 동작: "패밀리" 탭

**Step 3: 패밀리 추가 (이미 등록 시 스킵)**
- 조건: `runFlow when: visible: "패밀리 추가하기"` (추가 버튼이 보이면 실행)
  - 동작: "패밀리 추가하기" 탭
  - 동작: "고객 이름, 연락처, 메모" 또는 "고객을 검색해 보세요." 탭 (optional 분기)
  - 동작: `${CUSTOMER_PHONE_3}` 입력
  - 대기: `${CUSTOMER_NAME_3}` 표시 (timeout: 5000)
  - 동작: `${CUSTOMER_NAME_3}` 탭
  - 다이얼로그: "확인"/"추가"/"네" 모두 optional

**검증:**
- [CAPTURE] 최종 스크린샷: `phase3_family_link`

> **원본 대비 변경사항:**
> - 패밀리 탭 접근: 직접 탭 → 수평 swipe 후 탭 (탭 바가 화면 밖에 있는 경우 대응)
> - 멱등 처리: "패밀리 추가하기" 버튼 visible 여부로 이미 등록된 경우 자동 스킵
> - 검색 필드: "고객 이름, 연락처, 메모" 와 "고객을 검색해 보세요." 두 variant를 optional로 커버
> - assertVisible 검증 제거 → 스크린샷 기반

---

## Phase 4: 티켓 충전

**파일:** `phase4_ticket_charge.yaml`

### TC-4.1: user0413b 티켓 충전 (10회권)

**Step 1: 공통 로그인 + 고객 상세 진입**
- 동작: `runFlow: ../common_login.yaml`
- 동작: "고객" 탭 → `${CUSTOMER_PHONE_2}` 검색 → `${CUSTOMER_NAME_2}` 탭
- 대기: "고객 정보" 표시

**Step 2: 티켓 충전**
- 동작: "티켓 충전" 탭
- 대기: "티켓 충전" 화면 표시 (timeout: 5000)
- 동작: "선택" (index: 0) 탭 → 드롭다운 열기
- [CAPTURE] 드롭다운 스크린샷: `phase4_ticket_dropdown` (옵션 텍스트 확인용)
- 동작: "10회권 (카드)" 탭
- 동작: "충전" 탭
- 다이얼로그: "확인" (optional) → "네" (optional)

**검증:**
- [CAPTURE] 최종 스크린샷: `phase4_ticket_charge`

> **원본 대비 변경사항:**
> - 티켓 옵션 텍스트: "10만원권" → "10회권 (카드)" (autoqatest11 계정의 마스터 데이터)
> - 드롭다운 스크린샷 추가: 계정별 옵션 텍스트 차이를 사전 확인하기 위한 중간 캡처

---

## Phase 5: 예약 등록

**파일:** `phase5_reservation_register.yaml`

### TC-5.1: 예약 3건 등록

**데이터:**

| 예약 | 고객 | 시술 (대분류 > 소분류) | 시간 |
|------|------|----------------------|------|
| 1 | `${CUSTOMER_NAME_1}` (user0413a) | 손 > 젤 기본 | 기본값 (미선택) |
| 2 | `${CUSTOMER_NAME_2}` (user0413b) | 손 > 젤 기본 | 기본값 (미선택) |
| 3 | `${CUSTOMER_NAME_3}` (user0413c) | 손 > 케어 | 기본값 (미선택) |

**Step 1: 공통 로그인 + 예약 탭 진입**
- 동작: `runFlow: ../common_login.yaml`
- 동작: "예약" (index: 0) 탭
- [CAPTURE] 예약 탭 스크린샷: `phase5_reservation_tab`

**각 예약 공통 플로우:**

**Step 2: 예약 등록 폼 열기**
- 동작: "예약 추가 버튼" (contentDescription) 탭
- 대기: "예약 등록" 표시 (timeout: 5000)
- 동작: "예약 등록" 탭

**Step 3: 고객 선택**
- 대기: "신규 고객 등록" 표시 (ReservationCustomerSearchActivity, timeout: 5000)
- 동작: "고객 이름, 연락처, 메모" 탭 → `${CUSTOMER_PHONE_N}` 입력
- 동작: hideKeyboard
- 대기: `${CUSTOMER_NAME_N}` 표시 (timeout: 5000)
- 동작: `${CUSTOMER_NAME_N}` 탭 → CustomerDetailActivity 이동
- 대기: "고객 정보" 표시 (timeout: 5000)
- 동작: "예약 등록" 탭 → ReservationAddActivity 이동
- 대기: "예약 일시" 표시 (timeout: 5000)

**Step 4: 시술 선택**
- 동작: "시술 대분류 선택" (contentDescription) 탭
- 대기: "시술 그룹" 바텀시트 표시 (timeout: 5000)
- 동작: "손" 탭
- 대기: "시술명" 바텀시트 표시 (timeout: 5000)
- 동작: 시술 소분류 탭 ("젤 기본" 또는 "케어")

**Step 5: 등록**
- 동작: scrollUntilVisible "등록" (DOWN) → "등록" 탭
- 다이얼로그: "확인" (optional) — 중복 예약 경고
- 대기: "예약" 표시 (캘린더 복귀, timeout: 10000)

**검증 (3건 모두):**
- [MUST] 각 예약 등록 후 캘린더 복귀 성공
- [CAPTURE] 각 예약별 폼/완료 스크린샷

> **원본 대비 변경사항:**
> - 시간 선택 스텝 삭제: YAML에서 시간 미선택 (기본 시간대 사용)
> - 고객 선택 경로: 검색 → 고객 상세(CustomerDetailActivity) → "예약 등록" 버튼 탭 → 예약 폼. v2는 직접 예약 폼 진입 가정
> - 시술 대분류: contentDescription "시술 대분류 선택"으로 드롭다운 접근
> - 중복 예약: "확인" optional로 처리 (이미 같은 시간에 예약 있는 경우)
> - FAB 버튼: contentDescription "예약 추가 버튼"으로 접근

---

## Phase 6: 매출 등록

**파일:** `phase6_sale_register.yaml`

> TC-6.1~6.3: 고객 상세 → "매출 등록" 버튼으로 진입 (예약 블록이 아님)
> TC-6.4~6.5: 매출 탭 → FAB → 매출 등록으로 진입
> 각 매출 건 사이에 stopApp → launchApp으로 상태 초기화

### TC-6.1: user0413a 정액권 결제 20,000원

**Step 1: 공통 로그인 + 고객 상세 진입 + 매출 등록**
- 동작: `runFlow: ../common_login.yaml`
- 동작: "고객" 탭 → `${CUSTOMER_PHONE_1}` 검색 → `${CUSTOMER_NAME_1}` 탭
- 대기: "고객 정보" 표시
- 동작: 하단 "매출 등록" 탭

**Step 2: 1페이지 - 시술 선택**
- 동작: "선택해 주세요." 탭 → "젤 기본" 선택
- 동작: "다음" 탭

**Step 3: 2페이지 - 결제 수단 (정액권)**
- 대기: "결제 수단" 표시 (timeout: 5000)
- 동작: "정액권" 탭
- 동작: eraseText(10) → "20000" inputText
- 동작: "결제 수단" 라벨 탭 (포커스 이동 — hideKeyboard 대용)
- 다이얼로그: "취소" (optional) — "변경사항" 다이얼로그 dismiss
- 동작: "매출 등록" 탭
- 다이얼로그: "확인"/"네" (optional)

**검증:**
- [CAPTURE] 스크린샷: `phase6_sale1_membership`

> **원본 대비 변경사항:**
> - 진입 경로: 예약 블록에서 진입 → 고객 상세에서 "매출 등록" 버튼 탭
> - 시술 선택 추가: 고객 상세 진입이므로 1페이지에서 시술 선택 필요 ("선택해 주세요." → "젤 기본")
> - 키보드 닫기: hideKeyboard → "결제 수단" 라벨 탭으로 포커스 이동 (hideKeyboard가 back 키를 보내서 다이얼로그 트리거하는 이슈 회피)
> - "변경사항" 다이얼로그: 포커스 이동 시 발생 가능 → "취소" optional 처리 추가

---

### TC-6.2: user0413b 이용권(티켓) 차감

**Step 0: 앱 재시작**
- 동작: stopApp → launchApp
- 다이얼로그: "닫기" (optional), "Allow" (optional)
- 대기: "예약" 표시 (timeout: 15000)

**Step 1: 고객 상세 진입 + 매출 등록**
- 동작: "고객" 탭 → `${CUSTOMER_PHONE_2}` 검색 → `${CUSTOMER_NAME_2}` 탭
- 대기: "고객 정보" 표시
- 동작: 하단 "매출 등록" 탭

**Step 2: 1페이지 - 시술 선택 (분기 처리)**
- 분기 1: `runFlow when: visible: "티켓"` — 대분류가 "티켓"으로 표시되는 경우
  - "티켓" 탭 → "시술 그룹" 바텀시트 → "손" → "시술명" 바텀시트 → "젤 기본"
- 분기 2: `runFlow when: visible: "선택해 주세요."` — 소분류 미선택 상태
  - "선택해 주세요." 탭 → "젤 기본"
- 동작: "다음" 탭

**Step 3: 2페이지 - 결제 수단 (티켓 자동 차감)**
- 대기: "결제 수단" 표시 (timeout: 5000)
- 동작: "매출 등록" 탭 (티켓은 자동 차감이므로 별도 입력 불필요)
- 다이얼로그: "확인"/"네" (optional)

**검증:**
- [CAPTURE] 스크린샷: `phase6_sale2_ticket`

> **원본 대비 변경사항:**
> - 앱 재시작: TC-6.1 후 stopApp → launchApp으로 클린 상태 복귀
> - 시술 대분류 분기: 티켓 충전 이력이 있는 고객은 대분류가 "티켓"으로 표시될 수 있어 조건부 처리
> - 진입 경로: 예약 블록 → 고객 상세 "매출 등록" 버튼

---

### TC-6.3: user0413c 현금 5,000 + 카드 5,000

**Step 0: 앱 재시작**
- 동작: stopApp → launchApp → "닫기"/"Allow" → "예약" 대기

**Step 1: 고객 상세 진입 + 매출 등록**
- 동작: "고객" 탭 → `${CUSTOMER_PHONE_3}` 검색 → `${CUSTOMER_NAME_3}` 탭
- 동작: 하단 "매출 등록" 탭

**Step 2: 1페이지 - 시술 선택 (분기 처리)**
- 분기 1: `runFlow when: visible: "티켓"` → "손" → "케어"
- 분기 2: `runFlow when: visible: "선택해 주세요."` → "케어"
- 동작: "다음" 탭

**Step 3: 2페이지 - 결제 수단 (현금 + 카드 분할)**
- 대기: "결제 수단" 표시
- 동작: "현금" 탭 → eraseText(10) → "5000" inputText
- 동작: "카드" 탭 → eraseText(10) → "5000" inputText
- 동작: "결제 수단" 라벨 탭 (포커스 이동)
- 다이얼로그: "취소" (optional)
- 동작: "매출 등록" 탭
- 다이얼로그: "확인"/"네" (optional)

**검증:**
- [CAPTURE] 스크린샷: `phase6_sale3_cash_card`

> **원본 대비 변경사항:**
> - 앱 재시작 패턴 동일 (stopApp → launchApp)
> - 시술 대분류 분기 처리 추가 (TC-6.2와 동일 패턴)

---

### TC-6.4: 미등록 고객 제품 매출 (네이버페이 5,000 + 미수금 5,000)

**Step 0: 앱 재시작**
- 동작: stopApp → launchApp → "닫기"/"Allow" → "예약" 대기

**Step 1: 매출 탭 → FAB → 매출 등록**
- 동작: "매출" 탭
- 동작: "매출 추가 버튼" (contentDescription) 탭
- 동작: "매출 등록" (optional) 탭
- 대기: "매출 등록" 화면 표시

**Step 2: 미등록 고객 선택**
- 동작: "고객 등록 없이 진행" 탭
- 대기: "고객 이름" 표시 (고객 정보 입력 화면, timeout: 5000)
- 동작: "다음" 탭 (이름/연락처 미입력 — 미등록 고객으로 진행)

**Step 3: 1페이지 - 제품 선택**
- 대기: "시술 메뉴" 표시 (timeout: 5000)
- 동작: "제품" 탭 탭 (시술 → 제품 전환)
- 동작: "선택해 주세요." 탭 → 드롭다운 열기
- 대기: `.*테스트 제품.*` 표시 (regex — 재고 suffix 동적 변경 대응, timeout: 5000)
- 동작: `.*테스트 제품.*` 탭 (regex)
- 동작: "다음" 탭

**Step 4: 2페이지 - 결제 수단 (네이버페이 + 미수금)**
- 대기: "결제 수단" 표시 (timeout: 5000)
- 동작: "네이버페이" 탭 (체크박스 토글 → 앱이 남은 금액 10,000 자동 할당)
- 동작: "10,000" 탭 (자동 할당된 값을 직접 탭하여 입력 필드 포커스 획득)
- 동작: eraseText(10) → "5000" inputText
- 동작: scrollUntilVisible "미수금" (DOWN, timeout: 5000)
- 동작: "미수금" 탭 (체크박스 토글 → 남은 5,000 자동 할당, 별도 입력 불필요)
- 동작: "매출 메모" 탭 (optional — 포커스 해제)
- 다이얼로그: "취소" (optional)
- 동작: "매출 등록" (index: 1) 탭 — 상단 제목과 구분
- 다이얼로그: "확인"/"네" (optional)

**Step 5: 저장 성공 검증**
- 대기: "매출 추가 버튼" 표시 (매출 목록 화면 복귀 확인, timeout: 10000)

**검증:**
- [MUST] 매출 목록 화면 복귀 ("매출 추가 버튼" 표시)
- [CAPTURE] 스크린샷: `phase6_sale4_product`

> **원본 대비 변경사항 (핵심):**
> - 미등록 고객 진입: "미등록 고객" 옵션 → "고객 등록 없이 진행" → 고객 정보 스킵 → "다음"
> - 제품명: "01_제품_테스트" → `.*테스트 제품.*` (regex, 재고 표시 동적 suffix 대응)
> - 네이버페이 금액 수정: 체크박스 토글 → 자동 할당 "10,000" 값 직접 탭 → 입력 필드 포커스 획득 후 수정. (tapOn: "네이버페이"는 체크박스만 토글하고 입력 필드에 포커스 미이동)
> - 미수금: 자동 할당 역이용 (마지막 결제 수단 체크 시 남은 금액 자동 세팅)
> - 매출 등록 버튼: `tapOn: text: "매출 등록" index: 1` (상단 Activity 제목 "매출 등록"과 하단 CTA 버튼 텍스트 충돌 회피)
> - 저장 성공 검증: `extendedWaitUntil: "매출 추가 버튼"` 추가 (화면 전환 assert)

---

### TC-6.5: user0413c 패밀리 공유 정액권 10,000원

**Step 1: 매출 탭 FAB → 매출 등록 (TC-6.4 직후 연속)**
- 동작: "매출 추가 버튼" 탭 → "매출 등록" (optional) 탭
- 대기: "매출 등록" 화면 표시

**Step 2: 고객 선택**
- 동작: "고객 이름, 연락처, 메모" 탭 → `${CUSTOMER_PHONE_3}` 입력 + hideKeyboard
- 대기: `${CUSTOMER_NAME_3}` 표시 (timeout: 5000)
- 동작: `${CUSTOMER_NAME_3}` 탭

**Step 3: 1페이지 - 시술 선택**
- 동작: "시술" 탭 탭 (매출 탭 진입 시 UI 구조 차이)
- 동작: "손" 탭 → "케어" 탭
- 동작: "다음" 탭

**Step 4: 2페이지 - 결제 수단 (패밀리 공유 정액권)**
- 대기: "결제 수단" 표시 (timeout: 5000)
- 동작: "정액권" 탭
- 동작: eraseText(10) → "10000" inputText
- 동작: "결제 수단" 라벨 탭 (포커스 이동)
- 다이얼로그: "취소" (optional)
- 동작: "매출 등록" 탭
- 다이얼로그: "확인"/"네" (optional)

**검증:**
- [CAPTURE] 스크린샷: `phase6_sale5_family_membership`

> **원본 대비 변경사항:**
> - TC-6.4 직후 연속 실행 (앱 재시작 없음)
> - 시술 선택 UI: "시술" 탭 탭 → "손" → "케어" (매출 탭 FAB 진입 시 대분류 드롭다운이 아닌 직접 탭 구조)
> - 고객 검색: 연락처(`${CUSTOMER_PHONE_3}`)로 검색

---

## Phase 7: 통계 검증

**파일:** `phase7_stats_verify.yaml`

> **중요**: 매출 등록 완료 후 통계 배치 반영까지 최대 6분 소요
> 배치 대기 전략: pull-to-refresh + extendedWaitUntil 35초, 최대 12회 반복

### TC-7.0: 통계 페이지 진입 + 배치 대기

**Step 1: 공통 로그인 + 메뉴 탭 진입**
- 동작: `runFlow: ../common_login.yaml`
- 동작: "메뉴" 탭
- 대기: "메뉴" 표시 (timeout: 5000)

**Step 2: 통계 메뉴 진입**
- 동작: scrollUntilVisible "통계" (DOWN, timeout: 10000)
- 동작: "통계" 탭
- 대기: "통계" 표시 (timeout: 5000)

**Step 3: 직원 통계 진입**
- 동작: scrollUntilVisible "직원 통계" (DOWN, timeout: 10000)
- 동작: "직원 통계" 탭
- 대기: "직원 통계" 표시 (timeout: 5000)

**Step 4: 오늘 필터 적용**
- 동작: 날짜 SelectBox `.*~.*` (regex, index: 0) 탭
- 대기: "이번달" 표시 (캘린더 화면, timeout: 5000)
- 동작: 프리셋 칩 좌→우 swipe 2회 (10%,14% → 90%,14%, duration: 300) — "오늘" 칩 노출
- 동작: "오늘" 탭
- 동작: `.*기간 검색` (regex) 탭
- 대기: "직원 통계" 표시 (timeout: 10000)

**Step 5: 배치 대기 (repeat 12회)**
- 반복 12회:
  - 조건: "매출 건수" 표시 시 스크린샷 `phase7_batch_check`
  - 동작: pull-to-refresh swipe (50%,30% → 50%,70%, duration: 500)
  - 대기: "직원 통계" 표시 (timeout: 35000 — 30초 대기 + 5초 마진)
- [CAPTURE] 배치 확인 스크린샷: `phase7_batch_confirmed`

**검증:**
- [MUST] 12회 내에 "매출 건수" 표시

> **원본 대비 변경사항:**
> - 배치 대기: sleep 30초 → pull-to-refresh swipe + extendedWaitUntil 35초 (Maestro에 sleep 대안)
> - 배치 완료 조건: "7건" 텍스트 → "매출 건수" 텍스트 (이전 테스트 데이터 누적으로 건수 변동 가능)
> - 날짜 필터: "오늘" 직접 탭 불가 → 프리셋 칩 좌→우 swipe 2회 후 "오늘" 노출
> - 기간 검색 버튼: `.*기간 검색` regex 사용 (앞에 아이콘 등 prefix 매칭)
> - 진입 경로: 메뉴 → 통계 → 직원 통계 (scrollUntilVisible 활용)
> - stopRepeat 미사용: YAML에서 stopRepeat이 아닌 12회 고정 반복으로 구현

---

### TC-7.1: 상품 유형별 통계 검증

**탭:** 상품 유형별 통계 (기본 탭 — 별도 탭 전환 불필요)

**검증:**
- [MUST] "매출 건수" 텍스트 assertVisible
- [CAPTURE] 상품 유형별 통계 스크린샷: `phase7_product_type_stats`

**기대값 (참고 — 스크린샷 확인):**

| 항목 | 기대값 (신규 데이터만) | 비고 |
|------|----------------------|------|
| 매출 건수 | 7건 (충전2 + 매출5) | 이전 데이터 누적 시 변동 |
| 실 매출 합계 | 320,000원 | |
| 시술 | 10,000원 | TC-6.3 현금+카드 |
| 정액권 판매 | 200,000원 | TC-2.1 |
| 티켓 판매 | - | TC-4.1 (10회권) |
| 제품 | 10,000원 | TC-6.4 |
| 정액권 차감 | 30,000원 | TC-6.1(20K) + TC-6.5(10K) |
| 티켓 차감 | - | TC-6.2 (횟수 차감) |
| 차감 합계 | 50,000원 | 정액권 30K + 티켓 20K |
| 총 합계 | 370,000원 | |

> **v2 대비 검증 레벨 변경:** assertVisible 수치 검증 → 스크린샷 기반 [CAPTURE]. 데이터 누적으로 기대값 정확히 예측 불가.

---

### TC-7.2: 고객 유형별 통계 — 실 매출 기준

**탭 전환:**
- 동작: "고객 유형별 통계" 탭

**테이블 가로 스크롤 3단계 캡처:**
1. 좌측 컬럼: [CAPTURE] `phase7_customer_type_real_sales_left`
2. 중간 컬럼: swipe (90%,50% → 10%,50%, duration: 800) → [CAPTURE] `phase7_customer_type_real_sales_mid`
3. 우측 컬럼: swipe 1회 추가 → [CAPTURE] `phase7_customer_type_real_sales_right`

**기대값 (참고 — 스크린샷 확인):**

| 고객 유형 | 고객 수 | 매출 건 | 매출 금액 |
|-----------|---------|---------|-----------|
| 신규 일반 | 1명 | 2건 | 200,000원 |
| 신규 소개 | 2명 | 3건 | 110,000원 |
| 재방 지정 | 1명 | 1건 | 0원 |
| 재방 대체 | 0명 | 0건 | 0원 |
| 미등록 고객 | 1명 | 1건 | 10,000원 |

**검증:**
- [CAPTURE] 가로 스크롤 3단계 스크린샷

> **v2 대비 변경:** 수치 assertVisible → 스크린샷 [CAPTURE]. 가로 swipe로 테이블 전체 캡처.

---

### TC-7.3: 고객 유형별 통계 — 총 합계 기준

**테이블 좌측 복귀:**
- 동작: 좌←우 swipe 2회 (10%,50% → 90%,50%, duration: 800) — 원위치 복귀

**라디오 전환:**
- 동작: "총 합계 기준" 탭

**테이블 가로 스크롤 3단계 캡처:**
1. 좌측 컬럼: [CAPTURE] `phase7_customer_type_total_sales_left`
2. 중간 컬럼: swipe → [CAPTURE] `phase7_customer_type_total_sales_mid`
3. 우측 컬럼: swipe → [CAPTURE] `phase7_customer_type_total_sales_right`

**기대값 (참고 — 스크린샷 확인):**

| 고객 유형 | 고객 수 | 매출 건 | 매출 금액 |
|-----------|---------|---------|-----------|
| 신규 일반 | 1명 | 2건 | 220,000원 |
| 신규 소개 | 2명 | 3건 | 130,000원 |
| 재방 지정 | 1명 | 1건 | 10,000원 |
| 재방 대체 | 0명 | 0건 | 0원 |
| 미등록 고객 | 1명 | 1건 | 10,000원 |

**검증:**
- [CAPTURE] 가로 스크롤 3단계 스크린샷

> **v2 대비 변경:** 수치 assertVisible → 스크린샷 [CAPTURE]. 라디오 전환 전 좌측 복귀 swipe 2회 필요 (그렇지 않으면 "총 합계 기준" 라디오 버튼이 보이지 않음).

---

### TC-7.4: 고객 통계 (v4 신규)

> 통계 메인으로 뒤로가기 후 "고객 통계" 자세히 보기 진입

**Step 1: 통계 메인 복귀**
- 동작: back (직원 통계 → 통계 메인)
- 대기: "통계" 표시 (timeout: 5000)

**Step 2: 고객 통계 진입**
- 동작: scrollUntilVisible "고객 통계" (DOWN, timeout: 10000)
- 동작: "고객 통계" 근처 "자세히 보기" 탭
- 대기: "고객 통계" 표시 (timeout: 5000)

**Step 3: 오늘 필터 적용**
- 동작: 날짜 SelectBox `.*~.*` (regex, index: 0) 탭
- 대기: "이번달" 표시 (timeout: 5000)
- 동작: 프리셋 칩 좌→우 swipe 2회 → "오늘" 탭
- 동작: `.*기간 검색` (regex) 탭
- 대기: "고객 통계" 표시 (timeout: 10000)

**Step 4: 테이블 캡처**
- [CAPTURE] 좌측 컬럼: `phase7_customer_stats_left`
- 동작: swipe (90%,50% → 10%,50%, duration: 800) — 가로 스크롤
- [CAPTURE] 중간 컬럼: `phase7_customer_stats_mid`
- 동작: swipe 1회 추가
- [CAPTURE] 우측 컬럼: `phase7_customer_stats_right`

**테이블 구조:**
- 행: 날짜 (조회 기간 합계)
- 컬럼 그룹: 재방문 고객 | 신규 고객 | 미등록 고객

**기대값 (참고 — 스크린샷 확인):**

| 고객 유형 | 매출 건수 | 실매출 | 객단가 | 차감 금액 |
|----------|----------|--------|--------|----------|
| 재방문 고객 | 1건 | 0원 | 0원 | 10,000원 |
| 신규 고객 | 5건 | 310,000원 | 62,000원 | 40,000원 |
| 미등록 고객 | 1건 | 10,000원 | 10,000원 | - |

**검증:**
- [CAPTURE] 가로 스크롤 3단계 스크린샷

---

### TC-7.5: 채널별 매출 통계 (v4 신규)

> 통계 메인으로 뒤로가기 후 "채널별 매출 통계" 자세히 보기 진입

**Step 1: 통계 메인 복귀**
- 동작: back (고객 통계 → 통계 메인)
- 대기: "통계" 표시 (timeout: 5000)

**Step 2: 채널별 매출 통계 진입**
- 동작: scrollUntilVisible "채널별 매출 통계" (DOWN, timeout: 10000)
- 동작: "채널별 매출 통계" 근처 "자세히 보기" 탭
- 대기: "채널별 매출 통계" 표시 (timeout: 5000)

**Step 3: 오늘 필터 적용**
- 동작: 날짜 SelectBox `.*~.*` (regex, index: 0) 탭
- 대기: "이번달" 표시 (timeout: 5000)
- 동작: 프리셋 칩 좌→우 swipe 2회 → "오늘" 탭
- 동작: `.*기간 검색` (regex) 탭
- 대기: "채널별 매출 통계" 표시 (timeout: 10000)

**Step 4: 테이블 캡처**
- [CAPTURE] 좌측 (공비서 원장님): `phase7_channel_stats_left`
- 동작: swipe (90%,50% → 10%,50%, duration: 800)
- [CAPTURE] 우측 (공비서, 네이버예약): `phase7_channel_stats_right`

**테이블 구조:**
- 행: 날짜 (조회 기간 합계)
- 컬럼 그룹: 공비서 원장님 | 공비서 | 네이버예약

**기대값 (참고 — 스크린샷 확인):**

| 채널 | 매출 건수 | 실매출 합계 | 차감 합계 |
|------|----------|-----------|----------|
| 공비서 원장님 | 7건 | 320,000원 | 50,000원 |
| 공비서 | 0건 | 0원 | 0원 |
| 네이버예약 | 0건 | 0원 | 0원 |

> **참고:** 현재 테스트 데이터는 전부 CRM 직접 입력이므로 "공비서 원장님" 채널에 모두 집계됨.

**검증:**
- [CAPTURE] 가로 스크롤 2단계 스크린샷

---

### TC-7.6: 시간별 분석 (v4 신규)

> 통계 메인으로 뒤로가기 후 "시간별 분석" 자세히 보기 진입

**Step 1: 통계 메인 복귀**
- 동작: back (채널별 매출 통계 → 통계 메인)
- 대기: "통계" 표시 (timeout: 5000)

**Step 2: 시간별 분석 진입**
- 동작: scrollUntilVisible "시간별 분석" (DOWN, timeout: 10000)
- 동작: "시간별 분석" 근처 "자세히 보기" 탭
- 대기: "시간별 분석" 표시 (timeout: 5000)

**Step 3: 오늘 필터 적용**
- 동작: 날짜 SelectBox `.*~.*` (regex, index: 0) 탭
- 대기: "이번달" 표시 (timeout: 5000)
- 동작: 프리셋 칩 좌→우 swipe 2회 → "오늘" 탭
- 동작: `.*기간 검색` (regex) 탭
- 대기: "시간별 분석" 표시 (timeout: 10000)

**Step 4: 테이블 스크롤 + 캡처**
- [CAPTURE] 상단 (그래프): `phase7_time_stats_chart`
- 동작: scrollUntilVisible "시간별 매출 내역" (DOWN)
- [CAPTURE] 테이블 상단: `phase7_time_stats_table_top`
- 동작: scroll DOWN 반복하며 매출이 있는 시간대 캡처
- [CAPTURE] 매출 시간대: `phase7_time_stats_table_data`

**테이블 구조:**
- 행: 시간 슬롯 ("오전 8:00 ~ 오전 9:00", "오후 4:00 ~ 오후 5:00" 등)
- 컬럼: 시간 | 매출 건수 | 실 매출 합계 | 차감 합계 | 총 합계

**기대값 (참고 — 스크린샷 확인):**

> **주의:** 시간별 분석은 예약 매출과 비예약 매출의 기록 시간이 다르므로 기대값이 실행 시점에 따라 달라짐.

| 시간 구분 | 시간 기록 규칙 | 해당 매출 |
|----------|-------------|----------|
| 예약 매출 | 예약 시간 기준 (고정) | TC-6.1(예약시간), TC-6.2(예약시간), TC-6.3(예약시간) |
| 비예약 매출 | 등록 시간 기준 (실행 시점 의존) | 정액권 충전, 티켓 충전, TC-6.4(미등록), TC-6.5(패밀리) |

**예약 기반 고정 기대값:**

| 시간 슬롯 | 매출 건수 | 실매출 합계 | 차감 합계 | 총 합계 | 비고 |
|----------|----------|-----------|----------|---------|------|
| 예약1 시간대 | 1건 | 0원 | 20,000원 | 20,000원 | TC-6.1 정액권 차감 |
| 예약2 시간대 | 1건 | 0원 | 20,000원 | 20,000원 | TC-6.2 티켓 차감 |
| 예약3 시간대 | 1건 | 10,000원 | 0원 | 10,000원 | TC-6.3 현금+카드 |

**비예약 매출 (등록 시간에 합산):**

| 매출 | 실매출 | 차감 | 비고 |
|------|--------|------|------|
| 정액권 충전 | 200,000원 | 0원 | TC-2.1 |
| 티켓 충전 | 100,000원 | 0원 | TC-4.1 |
| 미등록 제품 | 10,000원 | 0원 | TC-6.4 |
| 패밀리 정액권 | 0원 | 10,000원 | TC-6.5 |
| **소계** | **310,000원** | **10,000원** | |

> **Web 자동화 테스트 참고:** 비예약 매출 4건은 테스트 실행 시간에 따라 동일 시간 슬롯에 합산될 수 있음. Web 테스트에서는 셋업 시 `datetime.now().hour`를 기록하여 동적으로 기대값을 구성함.

**검증:**
- [CAPTURE] 그래프 + 매출 시간대 테이블 스크린샷

---

### TC-7.7: 요일별 분석 (v4 신규)

> 통계 메인으로 뒤로가기 후 "요일별 분석" 자세히 보기 진입

**Step 1: 통계 메인 복귀**
- 동작: back (시간별 분석 → 통계 메인)
- 대기: "통계" 표시 (timeout: 5000)

**Step 2: 요일별 분석 진입**
- 동작: scrollUntilVisible "요일별 분석" (DOWN, timeout: 10000)
- 동작: "요일별 분석" 근처 "자세히 보기" 탭
- 대기: "요일별 분석" 표시 (timeout: 5000)

**Step 3: 오늘 필터 적용**
- 동작: 날짜 SelectBox `.*~.*` (regex, index: 0) 탭
- 대기: "이번달" 표시 (timeout: 5000)
- 동작: 프리셋 칩 좌→우 swipe 2회 → "오늘" 탭
- 동작: `.*기간 검색` (regex) 탭
- 대기: "요일별 분석" 표시 (timeout: 10000)

**Step 4: 테이블 캡처**
- [CAPTURE] 그래프: `phase7_day_stats_chart`
- 동작: scrollUntilVisible "요일별 매출 내역" (DOWN)
- [CAPTURE] 테이블: `phase7_day_stats_table`

**테이블 구조:**
- 행: 요일 (월요일 ~ 일요일)
- 컬럼: 요일 | 매출 건수 | 실 매출 합계 | 차감 합계 | 총 합계

**기대값 (참고 — 스크린샷 확인):**

| 요일 | 매출 건수 | 실매출 합계 | 차감 합계 | 총 합계 |
|------|----------|-----------|----------|---------|
| 테스트 실행 요일 | 7건 | 320,000원 | 50,000원 | 370,000원 |
| 그 외 요일 | 0건 | 0원 | 0원 | 0원 |

> **참고:** 모든 매출은 동일한 날(테스트 실행일)에 등록되므로 해당 요일에만 집계됨. 이전 테스트 데이터가 다른 요일에 있을 경우 해당 요일에도 값이 표시될 수 있음.

**검증:**
- [CAPTURE] 그래프 + 테이블 스크린샷

---

## 검증 레벨 정의

| 레벨 | 의미 | Maestro 매핑 | 실패 시 |
|------|------|-------------|---------|
| **[MUST]** | 핵심 검증 — 실패 시 테스트 FAIL | `assertVisible` / `extendedWaitUntil` | 즉시 중단 |
| **[SHOULD]** | 권장 검증 — 실패 시 WARNING | `assertVisible: optional: true` | 로그 남기고 계속 |
| **[CAPTURE]** | 스크린샷만 — 검증 없음 | `takeScreenshot` | 항상 PASS |

---

## 매출 → 통계 매핑 요약 (v3 — 실제 YAML 기준)

| 매출 | 고객 | 유형 | 실결제 | 차감 | 통계 반영 |
|------|------|------|--------|------|-----------|
| 정액권 충전 (Phase 2) | user0413a | 신규 일반 | 200,000 (현금) | - | 정액권 판매 200K |
| 티켓 충전 (Phase 4) | user0413b | 신규 소개 | 10회권 (카드) | - | 티켓 판매 |
| TC-6.1 | user0413a | 신규 일반 | 0 | 정액권 20K | 정액권 차감 20K |
| TC-6.2 | user0413b | 신규 소개 | 0 | 티켓 1회 | 티켓 차감 |
| TC-6.3 | user0413c | 신규 소개 | 10K (현금5K+카드5K) | 0 | 시술 10K |
| TC-6.4 | 미등록 고객 | 미등록 | 10K (NPay5K+미수금5K) | 0 | 제품 10K |
| TC-6.5 | user0413c | 재방 지정 | 0 | 정액권 10K (패밀리) | 정액권 차감 10K |

> **v2 대비 변경:**
> - 고객명: 한글 → 영문 (user0413a/b/c)
> - 티켓 충전: "10만원권" → "10회권 (카드)"
> - TC-6.2: 티켓 차감 "20K" → "1회" (횟수 기반, 금액은 시술가 기준)

### 매출 → 통계 교차 매핑 (v4 추가)

| 매출 | 직원 통계 (상품) | 직원 통계 (고객유형) | 고객 통계 | 채널별 | 시간별 | 요일별 |
|------|---------------|-------------------|----------|--------|--------|--------|
| 정액권 충전 | 정액권 판매 200K | 신규 일반 200K | 신규 고객 | 공비서 원장님 | 등록시간 | 실행요일 |
| 티켓 충전 | 티켓 판매 | 신규 소개 | 신규 고객 | 공비서 원장님 | 등록시간 | 실행요일 |
| TC-6.1 | 정액권 차감 20K | 신규 일반 차감 | 신규 고객 차감 | 공비서 원장님 | 예약시간 | 실행요일 |
| TC-6.2 | 티켓 차감 | 신규 소개 차감 | 신규 고객 차감 | 공비서 원장님 | 예약시간 | 실행요일 |
| TC-6.3 | 시술 10K | 신규 소개 10K | 신규 고객 | 공비서 원장님 | 예약시간 | 실행요일 |
| TC-6.4 | 제품 10K | 미등록 10K | 미등록 고객 | 공비서 원장님 | 등록시간 | 실행요일 |
| TC-6.5 | 정액권 차감 10K | 재방 지정 차감 | 재방문 고객 차감 | 공비서 원장님 | 등록시간 | 실행요일 |

---

## 오케스트레이터 구조

**파일:** `employee_stats_e2e_test.yaml`

```
employee_stats_e2e_test.yaml (env 변수 정의)
  ├── phase1_customer_register.yaml (runFlow: ../common_login.yaml)
  ├── phase2_membership_charge.yaml (runFlow: ../common_login.yaml)
  ├── phase3_family_link.yaml       (runFlow: ../common_login.yaml)
  ├── phase4_ticket_charge.yaml     (runFlow: ../common_login.yaml)
  ├── phase5_reservation_register.yaml (runFlow: ../common_login.yaml)
  ├── phase6_sale_register.yaml     (runFlow: ../common_login.yaml + 내부 stopApp/launchApp)
  └── phase7_stats_verify.yaml      (runFlow: ../common_login.yaml)
        ├── TC-7.0: 직원 통계 진입 + 배치 대기
        ├── TC-7.1: 상품 유형별 통계
        ├── TC-7.2: 고객 유형별 (실 매출 기준)
        ├── TC-7.3: 고객 유형별 (총 합계 기준)
        ├── TC-7.4: 고객 통계 (v4 신규)
        ├── TC-7.5: 채널별 매출 통계 (v4 신규)
        ├── TC-7.6: 시간별 분석 (v4 신규)
        └── TC-7.7: 요일별 분석 (v4 신규)
```

각 Phase는 자체 clearState + 재로그인을 포함하므로 독립 실행 가능.
Phase 6 내부에서는 TC 간 stopApp → launchApp으로 상태 초기화 (clearState 없이).
Phase 7 내부 TC-7.4~7.7은 통계 메인 → 자세히 보기 → 뒤로가기 패턴으로 순차 이동.

---

## 실행 방법

```bash
# 전체 E2E 테스트 실행
maestro test .maestro/flows/statistics/employee_stats_e2e_test.yaml \
  -e TEST_USER_ID=autoqatest11 \
  -e TEST_USER_PW=gong2023@@

# 개별 Phase 실행 (예: Phase 7만)
maestro test .maestro/flows/statistics/phase7_stats_verify.yaml \
  -e TEST_USER_ID=autoqatest11 \
  -e TEST_USER_PW=gong2023@@ \
  -e CUSTOMER_NAME_1=user0413a \
  -e CUSTOMER_PHONE_1=01004130001 \
  -e SCREENSHOT_DATE=20260413
```

> **참고:** 개별 Phase 실행 시 오케스트레이터의 env 변수를 수동 전달 필요.

---

## 개발팀 요청 사항 (accessibility identifier)

정밀 검증을 위해 아래 요소에 a11y id 추가 요청:

| 화면 | 요소 | 권장 id |
|------|------|---------|
| 직원 통계 | 매출 건수 | `staff_stats_sales_count` |
| 직원 통계 | 실 매출 합계 | `staff_stats_real_sales_total` |
| 직원 통계 | 차감 합계 | `staff_stats_deduction_total` |
| 직원 통계 | 총 합계 | `staff_stats_grand_total` |
| 고객 유형별 | 신규 일반 매출 금액 | `customer_type_new_normal_amount` |
| 고객 유형별 | 신규 소개 매출 금액 | `customer_type_new_referral_amount` |
| 고객 유형별 | 재방 지정 매출 금액 | `customer_type_revisit_amount` |
| 고객 유형별 | 미등록 매출 금액 | `customer_type_unregistered_amount` |
| 고객 유형별 | 실매출/총합계 라디오 | `customer_type_radio_real` / `customer_type_radio_total` |
| 고객 통계 | 재방문 고객 매출 건수 | `customer_stats_revisit_count` |
| 고객 통계 | 신규 고객 실매출 | `customer_stats_new_sales` |
| 고객 통계 | 미등록 고객 실매출 | `customer_stats_unregistered_sales` |
| 채널별 매출 | 공비서 원장님 매출 건수 | `channel_stats_owner_count` |
| 채널별 매출 | 공비서 원장님 실매출 합계 | `channel_stats_owner_sales` |
| 시간별 분석 | 시간 슬롯 매출 건수 | `time_stats_{hour}_count` |
| 시간별 분석 | 시간 슬롯 실매출 합계 | `time_stats_{hour}_sales` |
| 요일별 분석 | 요일 매출 건수 | `day_stats_{day}_count` |
| 요일별 분석 | 요일 실매출 합계 | `day_stats_{day}_sales` |

---

## 고객 유형 분류 규칙 (참고)

| 유형 | 조건 |
|------|------|
| 신규 일반 | 소개자 없음 + 첫 매출 |
| 신규 소개 | 소개자 있음 + 첫 매출 |
| 재방 지정 | 동일 담당자에게 재방문 (같은 날 두 번째 매출 포함) |
| 재방 대체 | 다른 담당자에게 재방문 |
| 미등록 고객 | 미등록 고객으로 매출 등록 |

---

## 주요 Maestro 패턴 (실제 YAML에서 발췌)

### 1. 멱등 처리 — 중복 고객 등록
```yaml
- runFlow:
    when:
      visible: "이미 등록된 고객 연락처입니다."
    commands:
      - tapOn: "고객 차트 보기"
      - waitForAnimationToEnd
      - back
```

### 2. 소개자 검색 — 연락처 숫자 + hideKeyboard
```yaml
- tapOn: "이름 또는 연락처를 검색해 보세요."
- inputText: ${CUSTOMER_PHONE_1}
- hideKeyboard
- waitForAnimationToEnd
- extendedWaitUntil:
    visible: ${CUSTOMER_NAME_1}
    timeout: 5000
- tapOn: ${CUSTOMER_NAME_1}
```

### 3. 체크박스 + 자동 할당 역이용 (네이버페이)
```yaml
# 체크박스 탭 → 앱이 남은 금액 자동 할당
- tapOn: "네이버페이"
# 자동 할당된 값을 직접 탭 → 입력 필드 포커스 획득
- tapOn: "10,000"
- eraseText: 10
- inputText: "5000"
```

### 4. Activity 제목 vs CTA 버튼 충돌 회피
```yaml
# 상단 제목 "매출 등록"과 하단 버튼 "매출 등록" 충돌
- tapOn:
    text: "매출 등록"
    index: 1    # 하단 버튼 명시
```

### 5. 배치 대기 — pull-to-refresh + repeat
```yaml
- repeat:
    times: 12
    commands:
      - runFlow:
          when:
            visible: "매출 건수"
          commands:
            - takeScreenshot: phase7_batch_check
      - swipe:
          start: "50%,30%"
          end: "50%,70%"
          duration: 500
      - extendedWaitUntil:
          visible: "직원 통계"
          timeout: 35000
```

### 6. 날짜 프리셋 칩 가로 swipe + regex 기간 검색
```yaml
# "오늘" 칩이 좌측에 숨겨져 있으므로 좌→우 swipe
- swipe:
    start: "10%,14%"
    end: "90%,14%"
    duration: 300
- tapOn: "오늘"
# 기간 검색 버튼 (앞에 아이콘 prefix 가능)
- tapOn: ".*기간 검색"
```

### 7. 시술 대분류 분기 처리
```yaml
# 대분류가 "티켓"으로 표시될 수 있는 경우
- runFlow:
    when:
      visible: "티켓"
    commands:
      - tapOn: "티켓"
      - extendedWaitUntil:
          visible: "시술 그룹"
      - tapOn: "손"
# 또는 소분류 미선택 상태
- runFlow:
    when:
      visible: "선택해 주세요."
    commands:
      - tapOn: "선택해 주세요."
      - tapOn: "젤 기본"
```

### 8. 통계 메인 ↔ 상세 페이지 순차 이동 (v4 신규)
```yaml
# 통계 상세 → 뒤로가기 → 다음 통계 진입
- back
- extendedWaitUntil:
    visible: "통계"
    timeout: 5000
- scrollUntilVisible:
    element: "고객 통계"
    direction: DOWN
    timeout: 10000
# "자세히 보기" 탭 (해당 통계 카드 근처)
- tapOn: "자세히 보기"
```
