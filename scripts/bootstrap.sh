#!/bin/bash
# =============================================================================
# bootstrap.sh
# GCP 프로젝트 초기 설정 스크립트 (최초 1회 실행)
#
# 사전 조건:
#   - gcloud CLI 설치 및 `gcloud init` 완료
#   - `gcloud auth application-default login` 완료
#   - Billing 계정 ID 준비 (gcloud billing accounts list 로 확인)
#
# 사용법:
#   BILLING_ACCOUNT_ID=XXXXXX-XXXXXX-XXXXXX ./scripts/bootstrap.sh
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# 설정값 (필요 시 수정)
# -----------------------------------------------------------------------------
PROJECT_ID="${PROJECT_ID:-cloud-sre-platform-dev}"   # GCP 프로젝트 ID (전역 고유값)
REGION="${REGION:-asia-northeast3}"               # 서울 리전
TFSTATE_BUCKET="${TFSTATE_BUCKET:-${PROJECT_ID}-tfstate}"  # Terraform 상태 파일 저장 버킷명
SA_NAME="terraform-sa"                            # 서비스 계정 이름 (GCP 내 식별자)
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"  # 서비스 계정 전체 이메일 (IAM 바인딩 시 사용)
KEY_PATH="${HOME}/.config/gcloud/terraform-sa-key.json"      # SA 키 저장 경로 (git 외부에 보관)

# Billing Account ID는 환경변수로 반드시 전달 필요
BILLING_ACCOUNT_ID="${BILLING_ACCOUNT_ID:?'오류: BILLING_ACCOUNT_ID 환경변수를 설정해주세요. (gcloud billing accounts list 로 확인)'}"

# -----------------------------------------------------------------------------
# 유틸 함수
# -----------------------------------------------------------------------------
info()    { echo "[INFO]  $*"; }
success() { echo "[OK]    $*"; }
warn()    { echo "[WARN]  $*"; }

# 이미 존재하면 건너뛰는 패턴을 위한 헬퍼
already_exists() { warn "$1 이미 존재합니다. 건너뜁니다."; }

# -----------------------------------------------------------------------------
# Step 1. GCP 프로젝트 생성 및 설정
# -----------------------------------------------------------------------------
info "Step 1/7: GCP 프로젝트 설정 중..."

if gcloud projects describe "$PROJECT_ID" &>/dev/null; then
  already_exists "프로젝트 '$PROJECT_ID'"
else
  gcloud projects create "$PROJECT_ID" \
    --name="$PROJECT_ID" \
    --quiet
  success "프로젝트 생성 완료: $PROJECT_ID"
fi

gcloud config set project "$PROJECT_ID" --quiet

# -----------------------------------------------------------------------------
# Step 2. Billing 계정 연결
# -----------------------------------------------------------------------------
info "Step 2/7: Billing 계정 연결 중..."

gcloud billing projects link "$PROJECT_ID" \
  --billing-account="$BILLING_ACCOUNT_ID" \
  --quiet

success "Billing 계정 연결 완료"

# -----------------------------------------------------------------------------
# Step 3. 필요한 GCP API 활성화 (약 1~2분 소요)
# -----------------------------------------------------------------------------
info "Step 3/7: GCP API 활성화 중... (1~2분 소요)"

APIS=(
  container.googleapis.com              # GKE: Kubernetes 클러스터 생성·관리
  artifactregistry.googleapis.com       # Artifact Registry: Docker 이미지 저장소
  bigquery.googleapis.com              # BigQuery: 비용 데이터 분석용 데이터 웨어하우스
  billingbudgets.googleapis.com        # Billing Budgets: 예산 알림 생성 API
  cloudbilling.googleapis.com          # Cloud Billing: 결제 계정 조회·연결 API
  storage.googleapis.com               # Cloud Storage(GCS): 파일 저장소 (tfstate 버킷 포함)
  iam.googleapis.com                   # IAM: 서비스 계정·권한 관리
  cloudresourcemanager.googleapis.com  # Resource Manager: 프로젝트 메타데이터 조회·수정
)

gcloud services enable "${APIS[@]}" --project="$PROJECT_ID" --quiet

success "API 활성화 완료"

# -----------------------------------------------------------------------------
# Step 4. Terraform 서비스 계정 생성 및 권한 설정
# -----------------------------------------------------------------------------
info "Step 4/7: Terraform 서비스 계정 생성 중..."

if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
  already_exists "서비스 계정 '$SA_EMAIL'"
else
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="Terraform Service Account" \
    --project="$PROJECT_ID" \
    --quiet
  success "서비스 계정 생성 완료: $SA_EMAIL"
fi

info "Step 4/7: IAM 역할 바인딩 중..."

ROLES=(
  roles/editor                  # 대부분의 GCP 리소스 생성·수정·삭제 (IAM 제외)
  roles/iam.securityAdmin       # IAM 정책 조회·수정 (서비스 계정에 역할 부여 시 필요)
  roles/container.admin         # GKE 클러스터 생성·관리·삭제
  roles/artifactregistry.admin  # Artifact Registry 저장소 생성·이미지 푸시·삭제
  roles/storage.admin           # GCS 버킷 생성·객체 읽기·쓰기 (tfstate 버킷 관리)
  roles/bigquery.admin          # BigQuery 데이터셋·테이블 생성·쿼리 (FinOps 비용 분석)
)

for ROLE in "${ROLES[@]}"; do
  info "  바인딩 중: $ROLE"
  # IAM은 read-modify-write 방식이라 연속 호출 시 409 충돌 발생 가능 → 실패 시 재시도
  for attempt in 1 2 3; do
    if gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="$ROLE" \
        --quiet > /dev/null; then
      break
    fi
    if [[ $attempt -eq 3 ]]; then
      echo "[ERROR] $ROLE 바인딩 실패 (3회 시도)" >&2
      exit 1
    fi
    warn "  재시도 중... ($attempt/3)"
    sleep 2
  done
done

success "IAM 역할 바인딩 완료"

# -----------------------------------------------------------------------------
# Step 5. 서비스 계정 키 생성 (로컬에만 저장, git에 절대 커밋 금지)
# -----------------------------------------------------------------------------
info "Step 5/7: 서비스 계정 키 생성 중..."

if [[ -f "$KEY_PATH" ]]; then
  already_exists "키 파일 '$KEY_PATH'"
else
  mkdir -p "$(dirname "$KEY_PATH")"
  gcloud iam service-accounts keys create "$KEY_PATH" \
    --iam-account="$SA_EMAIL" \
    --project="$PROJECT_ID" \
    --quiet
  chmod 600 "$KEY_PATH"
  success "키 파일 생성 완료: $KEY_PATH"
  warn "이 키 파일은 git에 절대 커밋하지 마세요!"
fi

# -----------------------------------------------------------------------------
# Step 6. Terraform state 저장용 GCS 버킷 생성
# -----------------------------------------------------------------------------
info "Step 6/7: Terraform state 버킷 생성 중..."

if gcloud storage buckets describe "gs://${TFSTATE_BUCKET}" &>/dev/null; then
  already_exists "버킷 'gs://${TFSTATE_BUCKET}'"
else
  # --uniform-bucket-level-access: 객체별 ACL 대신 버킷 IAM 정책으로 권한을 통일
  gcloud storage buckets create "gs://${TFSTATE_BUCKET}" \
    --project="$PROJECT_ID" \
    --location="$REGION" \
    --uniform-bucket-level-access \
    --quiet

  # --versioning: tfstate가 손상되거나 잘못 덮어쓰여도 이전 버전으로 복구 가능
  gcloud storage buckets update "gs://${TFSTATE_BUCKET}" \
    --versioning \
    --quiet

  success "버킷 생성 및 버전 관리 활성화 완료: gs://${TFSTATE_BUCKET}"
fi

# -----------------------------------------------------------------------------
# Step 7. Budget Alert 설정 ($250 임계치)
# -----------------------------------------------------------------------------
info "Step 7/7: Budget Alert 설정 중..."

# --budget-amount: free trial $300 중 여유분 고려한 임계값
# --threshold-rule: 80% ($200) 도달 시, 100% ($250) 도달 시 각각 이메일 알림 발송
gcloud billing budgets create \
  --billing-account="$BILLING_ACCOUNT_ID" \
  --display-name="${PROJECT_ID}-budget-alert" \
  --budget-amount=250USD \
  --threshold-rule=percent=0.8 \
  --threshold-rule=percent=1.0 \
  --quiet 2>/dev/null || warn "Budget Alert 생성 실패 또는 이미 존재합니다. GCP 콘솔에서 직접 확인하세요."

success "Budget Alert 설정 완료 (임계치: 80%, 100%)"

# -----------------------------------------------------------------------------
# 완료 안내
# -----------------------------------------------------------------------------
echo ""
echo "============================================================"
echo " Bootstrap 완료!"
echo "============================================================"
echo " 프로젝트 ID  : $PROJECT_ID"
echo " 리전         : $REGION"
echo " TF state 버킷: gs://${TFSTATE_BUCKET}"
echo " SA 키 파일   : $KEY_PATH"
echo ""
echo " 다음 단계:"
echo "   1. ~/.zshrc 에 아래 줄 추가:"
echo "      export GOOGLE_APPLICATION_CREDENTIALS=${KEY_PATH}"
echo "   2. source ~/.zshrc"
echo "   3. terraform/ 디렉토리에서 Terraform 코드 작성 시작"
echo "============================================================"
