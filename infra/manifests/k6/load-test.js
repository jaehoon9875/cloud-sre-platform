import http from "k6/http";
import { check, sleep } from "k6";

// 부하 테스트 시나리오: 30초간 점진적 증가 → 1분 유지 → 감소
export const options = {
  stages: [
    { duration: "30s", target: 20 },  // 가상 유저 0 → 20 증가
    { duration: "1m",  target: 20 },  // 20명 유지
    { duration: "20s", target: 0  },  // 0으로 감소
  ],
  thresholds: {
    // /orders 엔드포인트만 응답시간 체크 (/slow는 의도적 지연이므로 제외)
    "http_req_duration{url:http://localhost:8000/orders}": ["p(95)<500"],
    http_req_failed: ["rate<0.1"],  // 에러율 10% 이하 (/error 엔드포인트 포함)
  },
};

const BASE_URL = "http://localhost:8000";

export default function () {
  // 정상 요청 (70%)
  const ordersRes = http.get(`${BASE_URL}/orders`);
  check(ordersRes, {
    "orders status 200": (r) => r.status === 200,
  });

  // 지연 요청 (20%) — 트레이싱 확인용
  if (Math.random() < 0.2) {
    const slowRes = http.get(`${BASE_URL}/slow`);
    check(slowRes, {
      "slow status 200": (r) => r.status === 200,
    });
  }

  // 에러 요청 (10%) — 에러율 메트릭 확인용
  if (Math.random() < 0.1) {
    const errorRes = http.get(`${BASE_URL}/error`);
    check(errorRes, {
      "error status 500": (r) => r.status === 500,
    });
  }

  sleep(1);
}
