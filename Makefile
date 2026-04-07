# 프로젝트 공통 설정
PROJECT_ID  := cloud-sre-platform-dev
REGION      := asia-northeast3
CLUSTER     := sre-platform-cluster
NODE_POOL   := sre-platform-cluster-spot-pool

# ── GKE 클러스터 비용 제어 ────────────────────────────────────────────────────

## 클러스터 노드 수를 0으로 축소 (야간/주말 비용 절감용)
## control plane 비용($0.10/hr)은 유지되나 노드 VM 비용은 0원
cluster-down:
	# 1단계: 오토스케일러 비활성화 (활성 상태에서 resize 시 즉시 재복구하는 문제 방지)
	gcloud container clusters update $(CLUSTER) \
		--node-pool $(NODE_POOL) \
		--no-enable-autoscaling \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--quiet
	# 2단계: 노드 수 0으로 축소 (regional 클러스터이므로 zone당 0개 = 총 0개)
	gcloud container clusters resize $(CLUSTER) \
		--node-pool $(NODE_POOL) \
		--num-nodes 0 \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--quiet

## 클러스터 노드를 복구 후 오토스케일러 재활성화 (작업 재개 시)
cluster-up:
	# 1단계: 노드 수 복구 (regional 클러스터이므로 zone당 1개 = 총 3개)
	gcloud container clusters resize $(CLUSTER) \
		--node-pool $(NODE_POOL) \
		--num-nodes 1 \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--quiet
	# 2단계: 오토스케일러 재활성화
	gcloud container clusters update $(CLUSTER) \
		--node-pool $(NODE_POOL) \
		--enable-autoscaling \
		--min-nodes 0 \
		--max-nodes 3 \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--quiet

## 현재 노드 상태 확인
cluster-status:
	kubectl get nodes
	@echo ""
	gcloud container node-pools describe $(NODE_POOL) \
		--cluster $(CLUSTER) \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--format="table(name, autoscaling.minNodeCount, autoscaling.maxNodeCount, initialNodeCount)"

# ── Terraform ─────────────────────────────────────────────────────────────────

## terraform plan 실행
tf-plan:
	cd terraform && terraform plan

## terraform apply 실행
tf-apply:
	cd terraform && terraform apply

## terraform destroy 실행 (전체 인프라 삭제 — 주의)
tf-destroy:
	cd terraform && terraform destroy

.PHONY: cluster-down cluster-up cluster-status tf-plan tf-apply tf-destroy
