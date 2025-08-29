import { check } from "k6";

import http from "k6/http";

import { COMMON_OPTIONS, SERVERS } from "./config.js";

const activeServer = SERVERS[__ENV.PROXY_TARGET] || SERVERS.go;

export const options = {
  ...COMMON_OPTIONS,
  stages: [
    { duration: "1m", target: 10 },
    { duration: "3m", target: 10000 },
    { duration: "1m", target: 10 },
  ],
};

export default function () {
  const res = http.get(`${activeServer}`);

  check(res, {
    "status is 200": (r) => r.status === 200,
  });
}
