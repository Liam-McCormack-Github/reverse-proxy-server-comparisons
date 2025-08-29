import { check, group } from "k6";

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
  group(`Image endpoint test for ${activeServer}`, function () {
    const res = http.get(`${activeServer}/api/v1/image`);

    check(res, {
      "status is 200 for image endpoint": (r) => r && r.status === 200,
      "content-type is image/png": (r) =>
        r && r.headers && r.headers["Content-Type"] === "image/png",
      "image body is not empty": (r) => r && r.body && r.body.length > 0,
    });
  });
}
