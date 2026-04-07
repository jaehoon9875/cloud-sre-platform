# ISSUES.md

프로젝트 진행 중 발생한 이슈, 미해결 항목, 보류 결정 사항을 기록합니다.

---

## 심각도 기준

| 심각도 | 기준 |
|--------|------|
| 🔴 높음 | 다음 단계 진행을 막는 블로커 |
| 🟡 중간 | 기능에 영향은 있으나 우회 방법이 존재 |
| 🟢 낮음 | 사소한 불편, 나중에 처리해도 무방 |

---

## 진행 중 이슈

| # | 심각도 | 단계 | 제목 | 발생일 | 상태 |
|---|--------|------|------|--------|------|
| 1 | 🟢 낮음 | Stage 1 | `gcloud billing budgets create` CLI 명령어 INVALID_ARGUMENT 오류 | 2026-04-06 | 미해결 (콘솔에서 수동 설정으로 우회) |
| 2 | 🟡 중간 | Stage 1 | GKE node scale-down이 0으로 되지 않음 | 2026-04-07 | 미해결 |

### #2 상세

**현상**: `make cluster-down` 및 GitHub Actions workflow 실행 시 노드 수가 0이 되지 않고 1을 유지함  
**시도한 방법**:
- `terraform.tfvars` `min_node_count` 1 → 0 변경 후 `terraform apply`
- workflow에 `gcloud container clusters update --min-nodes 0` 추가 후 `resize --num-nodes 0` 실행  

**원인 후보**: 리전 클러스터(3 zone)에서 `resize` 명령이 zone별로 동작하는 방식 문제, 또는 오토스케일러가 min=0 반영 전에 복구하는 타이밍 문제로 추정  
**후속 조치**: `gcloud container node-pools update` 방식 또는 각 zone별 직접 제어 방법 조사 필요

---

### #1 상세

**현상**: `scripts/bootstrap.sh` Step 7에서 `gcloud billing budgets create` 실행 시 `INVALID_ARGUMENT` 오류 발생  
**우회**: GCP 콘솔 > 결제 > 예산 및 알림에서 수동 생성  
**원인 후보**: `--threshold-rule` 플래그 문법 또는 `--budget-amount` 형식 문제로 추정. CLI 버전에 따라 동작이 다를 수 있음  
**후속 조치**: gcloud 버전 업데이트 후 재시도 또는 올바른 플래그 문법 확인 필요  
**참고 문서**: https://docs.cloud.google.com/sdk/gcloud/reference/billing/budgets/create

---

## 보류 / 결정 필요

| # | 심각도 | 항목 | 내용 | 등록일 |
|---|--------|------|------|--------|
| - | - | - | (아직 없음) | - |

---

## 해결된 이슈

| # | 심각도 | 단계 | 제목 | 해결일 | 해결 방법 |
|---|--------|------|------|--------|-----------|
| - | - | - | (아직 없음) | - | - |

---

## 이슈 작성 방법

이슈 발생 시 "진행 중 이슈" 테이블에 추가합니다.

```
| 2 | 🟡 중간 | Stage 1 | terraform apply 시 권한 오류 | 2026-xx-xx | 조사 중 |
```

해결되면 해결된 이슈 섹션으로 옮기고 해결 방법을 기록합니다.
