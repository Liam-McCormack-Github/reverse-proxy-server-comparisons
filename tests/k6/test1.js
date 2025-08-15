import { check } from "k6";

import http from "k6/http";

import { COMMON_OPTIONS, SERVERS } from "./config.js";

const activeServer = SERVERS[__ENV.PROXY_TARGET] || SERVERS.go;

export const options = {
  ...COMMON_OPTIONS,

  stages: [
    { duration: "15s", target: 10 },

    { duration: "30s", target: 50 },

    { duration: "1m", target: 1000 },

    { duration: "30s", target: 50 },

    { duration: "15s", target: 10 },
  ],
};

export default function () {
  const res = http.get(`${activeServer}`);

  check(res, {
    "status is 200": (r) => r.status === 200,
  });
}
