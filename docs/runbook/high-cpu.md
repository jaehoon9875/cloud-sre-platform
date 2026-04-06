# Runbook - High CPU

## 증상

- Pod CPU throttling rate 높음
- 응답 지연 증가

## 확인 절차

```bash
# 1. 어떤 pod가 CPU를 많이 쓰는지 확인
kubectl top pods -n <namespace>

# 2. throttling 메트릭 확인 (Grafana)
container_cpu_cfs_throttled_seconds_total

# 3. pod describe로 resource limit 확인
kubectl describe pod <pod-name> -n <namespace>
```

## 대응

<!-- 진행하면서 채워주세요 -->
