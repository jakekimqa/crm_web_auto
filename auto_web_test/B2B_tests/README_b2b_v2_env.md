`test_b2b_v2.py`는 dev/prod 공용으로 쓰고, 환경값만 바꿔 실행하는 방식으로 운영하는 것을 권장합니다.

준비:
- dev는 [auto_web_test/.env.dev](/Users/jakekim/PycharmProjects/pythonProject1/auto_web_test/.env.dev) 를 바로 사용할 수 있습니다.
- prod는 [auto_web_test/.env.prod](/Users/jakekim/PycharmProjects/pythonProject1/auto_web_test/.env.prod) 의 `replace-me` 값을 실제 운영 값으로 바꿔야 합니다.
- 필요하면 예시 파일인 `*.example`을 참고해서 다시 만들 수 있습니다.

실행 예시:

```bash
chmod +x auto_web_test/run_b2b_v2.sh
auto_web_test/run_b2b_v2.sh auto_web_test/.env.dev
```

```bash
auto_web_test/run_b2b_v2.sh auto_web_test/.env.prod -k test_verify_shop_status_today_summary_v2
```

```bash
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." \
auto_web_test/run_b2b_v2.sh auto_web_test/.env.dev -k test_verify_statistics_details_v2
```

자주 쓰는 실행:

```bash
# dev 전체 실행
auto_web_test/run_b2b_v2.sh auto_web_test/.env.dev
```

```bash
# dev 통계만 실행
auto_web_test/run_b2b_v2.sh auto_web_test/.env.dev -k test_verify_statistics_details_v2
```

```bash
# dev 홈 샵 현황만 실행
auto_web_test/run_b2b_v2.sh auto_web_test/.env.dev -k test_verify_shop_status_today_summary_v2
```

```bash
# prod 실행
auto_web_test/run_b2b_v2.sh auto_web_test/.env.prod -k test_verify_statistics_details_v2
```

주의:
- 운영에서는 생성/충전/매출 등록처럼 데이터를 바꾸는 테스트보다 조회성 테스트를 우선 권장합니다.
- 현재 공용 실행 대상 파일은 `auto_web_test/B2B_tests/test_b2b_v2.py` 입니다.
