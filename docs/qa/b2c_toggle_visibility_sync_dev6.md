# DEV6 공비서 예약받기 토글 연동 테스트

## 목적
`dev6 > 미입점_샵생성 > 공비서로 예약받기`의 토글 상태가
`qa-zero > 내주변 > 목록보기` 노출 상태와 동기화되는지 검증한다.

## 분기 시나리오

### 1.1 토글 ON인 경우
1. CRM 토글 ON 확인
2. QA-ZERO 내주변 목록에서 `미입점_샵생성` 노출 확인
3. CRM 토글 OFF 처리
4. OFF 모달에서 `예약받기 비활성화` 클릭
5. QA-ZERO 내주변 목록에서 `미입점_샵생성` 미노출 확인

### 1.2 토글 OFF인 경우
1. CRM 토글 OFF 확인
2. QA-ZERO 내주변 목록에서 `미입점_샵생성` 미노출 확인
3. CRM 토글 ON 처리
4. QA-ZERO 내주변 목록에서 `미입점_샵생성` 노출 확인

## 검증 포인트
- CRM 토글 DOM: `#b2c-setting-activate-switch`
- OFF 확정 모달 버튼: `예약받기 비활성화`
- QA-ZERO 목록 기준: 본문 텍스트에 `미입점_샵생성` 포함 여부

## 자동화 파일
- `auto_web_test/B2C_tests/test_b2c_toggle_visibility_sync_dev6.py`

## 실행 방법
```bash
export CRM_USER_ID="jaketest"
export CRM_USER_PW="gong2023@@"
pytest -q -s auto_web_test/B2C_tests/test_b2c_toggle_visibility_sync_dev6.py
```

## 생성 스크린샷
- 기본 저장 경로: `qa_artifacts/screenshots`
- 분기별로 아래 파일 생성
  - `toggle_branch_01_initial_crm.png`
  - `toggle_branch_02_*_nearby_list.png`
  - `toggle_branch_03_*_applied_crm.png`
  - `toggle_branch_04_*_nearby_list.png`
