# Bootstrap — GCP 초기 환경 설정

Terraform을 실행하기 전에 필요한 GCP 리소스와 로컬 환경을 준비하는 절차.
`scripts/bootstrap.sh` 스크립트로 대부분 자동화되어 있으며, **프로젝트 생애 주기 당 최초 1회만 실행**한다.

---

## 사전 조건 (스크립트 실행 전 수동으로 완료)

### 1. 로컬 도구 설치

```bash
# Terraform 버전 관리 (tfenv)
brew install tfenv
tfenv install 1.7.5
tfenv use 1.7.5
terraform version

# gcloud CLI (google-cloud-sdk)
brew install --cask google-cloud-sdk

# kubectl — 쿠버네티스 클러스터 제어 CLI
brew install kubectl

# gke-gcloud-auth-plugin — kubectl이 GKE에 인증하기 위한 플러그인
# brew cask로 설치한 경우 bin 경로를 PATH에 추가해야 함
echo 'export PATH="/opt/homebrew/share/google-cloud-sdk/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# 설치 확인
gke-gcloud-auth-plugin --version
kubectl version --client
```

### 2. gcloud 인증

```bash
# 계정 초기화 (인터랙티브 — 브라우저 인증 필요)
gcloud init

# Terraform이 사용할 ADC(Application Default Credentials) 설정
gcloud auth application-default login
```

### 3. Billing Account ID 확인

```bash
gcloud billing accounts list
# 출력 예시: ACCOUNT_ID: XXXXXX-XXXXXX-XXXXXX
```

---

## 스크립트 실행

```bash
# 프로젝트 루트에서 실행
BILLING_ACCOUNT_ID=XXXXXX-XXXXXX-XXXXXX ./scripts/bootstrap.sh
```

스크립트가 수행하는 작업 순서:

| 단계 | 작업 | 비고 |
|------|------|------|
| 1 | GCP 프로젝트 생성 | 이미 존재하면 건너뜀 |
| 2 | Billing 계정 연결 | 프리 트라이얼 계정 |
| 3 | GCP API 활성화 | GKE, AR, BigQuery 등 — 약 1~2분 소요 |
| 4 | Terraform 서비스 계정 생성 + IAM 역할 부여 | 이미 존재하면 건너뜀 |
| 5 | 서비스 계정 키 파일 생성 | `~/.config/gcloud/terraform-sa-key.json` |
| 6 | Terraform state용 GCS 버킷 생성 + 버전 관리 활성화 | 이미 존재하면 건너뜀 |
| 7 | Budget Alert 설정 | 임계치 80%, 100% ($250 기준) |

---

## 스크립트 실행 후 로컬 환경 마무리

스크립트 완료 후 아래 환경변수를 `~/.zshrc`에 추가한다.

```bash
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/terraform-sa-key.json
```

```bash
source ~/.zshrc
```

---

## 설정값 커스터마이징

스크립트 상단의 환경변수로 기본값을 오버라이드할 수 있다.

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `PROJECT_ID` | `cloud-sre-platform-dev` | GCP 프로젝트 ID |
| `REGION` | `asia-northeast3` | 기본 리전 (서울) |
| `TFSTATE_BUCKET` | `{PROJECT_ID}-tfstate` | Terraform state 버킷 이름 |
| `BILLING_ACCOUNT_ID` | (필수 입력) | GCP 결제 계정 ID |

```bash
# 예시: 프로젝트 ID를 변경해서 실행
PROJECT_ID=my-custom-project \
BILLING_ACCOUNT_ID=XXXXXX-XXXXXX-XXXXXX \
./scripts/bootstrap.sh
```

---

## 보안 주의사항

- `~/.config/gcloud/terraform-sa-key.json` 키 파일은 **git에 절대 커밋하지 않는다.**
- 이 파일은 `.gitignore`에서 `*-sa-key.json` 패턴으로 제외되어 있다.
- 키 파일이 노출된 경우 즉시 GCP 콘솔 → IAM → 서비스 계정에서 해당 키를 비활성화/삭제한다.

---

## 다음 단계

Bootstrap 완료 후 `terraform/` 디렉토리에서 Terraform 코드 작성을 시작한다.  
진행 순서는 [PLAN.md](PLAN.md) Stage 1 "Terraform 구성" 섹션 참고.

---

## Terraform apply 후 — GKE 클러스터 로컬 연결

`terraform apply`로 GKE 클러스터가 생성된 뒤, 아래 명령어로 로컬 kubectl을 클러스터에 연결한다.

```bash
# kubeconfig 생성 (kubectl이 클러스터를 인식하게 함)
gcloud container clusters get-credentials sre-platform-cluster \
  --region asia-northeast3 \
  --project cloud-sre-platform-dev

# 노드 연결 확인
kubectl get nodes
```

노드가 `Ready` 상태로 출력되면 정상 연결된 것이다.
