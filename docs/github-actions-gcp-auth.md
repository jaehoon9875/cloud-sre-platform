# GitHub Actions — GCP 인증 설정 (Workload Identity Federation)

GitHub Actions workflow에서 GCP 리소스에 접근하기 위한 인증 설정 절차.  
SA 키 JSON 파일 없이 GitHub과 GCP 간 신뢰 관계를 구성하는 방식(권장).

**최초 1회만 실행**하면 되며, 이후 workflow는 자동으로 인증된다.

---

## 사전 조건

- GCP 프로젝트 생성 완료 (`cloud-sre-platform-dev`)
- Terraform SA 생성 완료 (`terraform-sa@cloud-sre-platform-dev.iam.gserviceaccount.com`)
- `gcloud` CLI 인증 완료

---

## 설정 절차

### Step 1. Workload Identity Pool 생성

```bash
gcloud iam workload-identity-pools create "github-pool" \
  --project="cloud-sre-platform-dev" \
  --location="global" \
  --display-name="GitHub Actions Pool"
```

### Step 2. OIDC Provider 생성

GitHub 저장소만 허용하도록 `--attribute-condition` 필수 지정.  
없으면 `INVALID_ARGUMENT` 오류 발생.

```bash
gcloud iam workload-identity-pools providers create-oidc "github-provider" \
  --project="cloud-sre-platform-dev" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --display-name="GitHub Provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
  --attribute-condition="assertion.repository == 'jaehoon9875/cloud-sre-platform'"
```

### Step 3. 프로젝트 번호 확인

```bash
gcloud projects describe cloud-sre-platform-dev --format="value(projectNumber)"
# 출력 예: 591264788426
```

### Step 4. SA에 WIF 권한 부여

`PROJECT_NUMBER`를 Step 3에서 확인한 값으로 교체.

```bash
gcloud iam service-accounts add-iam-policy-binding \
  "terraform-sa@cloud-sre-platform-dev.iam.gserviceaccount.com" \
  --project="cloud-sre-platform-dev" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/591264788426/locations/global/workloadIdentityPools/github-pool/attribute.repository/jaehoon9875/cloud-sre-platform"
```

### Step 5. WIF Provider 전체 경로 확인

```bash
gcloud iam workload-identity-pools providers describe "github-provider" \
  --project="cloud-sre-platform-dev" \
  --location="global" \
  --workload-identity-pool="github-pool" \
  --format="value(name)"
# 출력 예: projects/591264788426/locations/global/workloadIdentityPools/github-pool/providers/github-provider
```

### Step 6. GitHub Repository Secrets 등록

GitHub repo → Settings → Secrets and variables → Actions → "New repository secret"

| Secret 이름 | 값 |
|-------------|-----|
| `WIF_PROVIDER` | Step 5 출력값 (`projects/591264788426/locations/global/...`) |
| `WIF_SERVICE_ACCOUNT` | `terraform-sa@cloud-sre-platform-dev.iam.gserviceaccount.com` |

---

## 검증

GitHub Actions → workflow 수동 트리거 후 아래 step들이 성공하면 정상:
- `GCP 인증 (Workload Identity Federation)` ✅
- `gcloud CLI 설정` ✅

---

## 참고

- 이 설정은 `cloud-sre-platform` 저장소에서 실행되는 workflow에만 적용됨
- 다른 저장소에서 동일한 인증이 필요하면 Step 2의 `--attribute-condition` 값을 변경하거나 Step 4의 `--member` 조건을 `attribute.repository_owner`로 변경
