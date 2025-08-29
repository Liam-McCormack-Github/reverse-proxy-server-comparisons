import { check, group } from "k6";

import http from "k6/http";

import { COMMON_OPTIONS, SERVERS } from "./config.js";

const activeServer = SERVERS[__ENV.PROXY_TARGET] || SERVERS["go-proxy"];

export const options = {
  ...COMMON_OPTIONS,
  stages: [
    { duration: "1m", target: 2 },
    { duration: "3m", target: 200 },
    { duration: "1m", target: 2 },
  ],
};

export default function () {
  const requests = {
    root: { method: "GET", url: `${activeServer}/` },
    page: { method: "GET", url: `${activeServer}/page` },
    where: { method: "GET", url: `${activeServer}/wheredidicomefrom` },
    heavy: { method: "GET", url: `${activeServer}/heavy-asset` },
    image: { method: "GET", url: `${activeServer}/api/v1/image` },
  };
  const responses = http.batch(requests);

  check(responses.root, {
    "root: status is 200": (r) => r && r.status === 200,
  });

  check(responses.image, {
    "image: status is 200": (r) => r && r.status === 200,
    "image: content-type is image/png": (r) =>
      r && r.headers && r.headers["Content-Type"] === "image/png",
  });

  check(responses.page, {
    "page: status is 200": (r) => r && r.status === 200,
  });

  check(responses.where, {
    "where: status is 200": (r) => r && r.status === 200,
  });

  check(responses.heavy, {
    "heavy: status is 200": (r) => r && r.status === 200,
  });
}
