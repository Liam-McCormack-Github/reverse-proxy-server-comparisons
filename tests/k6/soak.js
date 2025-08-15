import { check, group } from "k6";
import http from "k6/http";
import { COMMON_OPTIONS, SERVERS } from "./config.js";

const activeServer = SERVERS[__ENV.PROXY_TARGET] || SERVERS.go;

export const options = {
  ...COMMON_OPTIONS,
  stages: [
    { duration: "1m", target: 10 },
    { duration: "15s", target: 0 },

    { duration: "2m", target: 100 },
    { duration: "10m", target: 1000 },
    { duration: "1m", target: 0 },

    { duration: "4m", target: 500 },
    { duration: "15m", target: 5000 },
    { duration: "2m", target: 0 },

    { duration: "5m", target: 1000 },
    { duration: "20m", target: 10000 },
    { duration: "2m", target: 0 },
  ],
};

export default function () {
  const endpoints = ["", "/page"];

  group(`User flow to ${activeServer}`, function () {
    for (const endpoint of endpoints) {
      const url = `${activeServer}${endpoint}`;
      const res = http.get(url);

      check(res, {
        [`status is 200 for '${endpoint || "/"}'`]: (r) => r.status === 200,
      });
    }
  });
}
