import http from "k6/http";
import { check, sleep } from "k6";

export const options = { vus: 5, duration: "20s", thresholds: { http_req_failed: ["rate<0.01"], http_req_duration: ["p(95)<500"] } };

export default function () {
  const response = http.get(`${__ENV.BASE_URL || "http://localhost:8000"}/health/ready`);
  check(response, { "ready is 200": (r) => r.status === 200 });
  sleep(0.2);
}

