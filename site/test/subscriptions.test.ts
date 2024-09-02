import { test, afterEach, mock } from "node:test";
import assert from "node:assert/strict";
import { site } from "../site.config.ts";
import {
  countNodes,
  getSubscription,
  MAX_BYTES,
} from "../src/subscriptions.ts";
import worker from "../src/worker.ts";

afterEach(() => mock.restoreAll());
const source = site.sources.find((source) => source.id === "all")!;
const fixture =
  "hysteria2://test@example.invalid:443#Test\nvless://test@example.invalid:443#Test\n";

function harness() {
  const entries = new Map<
    string,
    { bytes: ArrayBuffer; headers: Headers; expires: number }
  >();
  const pending: Promise<unknown>[] = [];
  let now = 0;
  const cache = {
    async match(request: Request) {
      const entry = entries.get(request.url);
      return entry && entry.expires > now
        ? new Response(entry.bytes, { headers: entry.headers })
        : undefined;
    },
    async put(request: Request, response: Response) {
      // Fully consume the tee as the real Cache API does.
      const bytes = await response.arrayBuffer();
      const ttl = Number(
        response.headers.get("cache-control")?.match(/max-age=(\d+)/)?.[1],
      );
      entries.set(request.url, {
        bytes,
        headers: response.headers,
        expires: now + ttl * 1000,
      });
    },
  };
  const ctx = {
    waitUntil(promise: Promise<unknown>) {
      pending.push(promise);
    },
  };
  return {
    cache,
    ctx,
    entries,
    advance(ms: number) {
      now += ms;
    },
    async flush() {
      await Promise.all(pending.splice(0));
    },
  };
}

test("counts real URI lines and YAML proxies, including flow-style YAML and anchors", () => {
  assert.equal(countNodes(fixture, "uri"), 2);
  assert.equal(
    countNodes("\r\nhy2://test@example.invalid:443\r\n\r\n", "uri"),
    1,
  );
  assert.equal(
    countNodes("base: &base {type: ss, name: test}\nproxies: [*base]", "clash"),
    1,
  );
  for (const body of ["", "<html>error</html>", fixture + "not a node"]) {
    assert.throws(() => countNodes(body, "uri"), { code: "invalid" });
  }
  for (const body of [
    "proxies: []",
    "proxies: [test]",
    "proxies: [",
    "rules: []",
  ]) {
    assert.throws(() => countNodes(body, "clash"), { code: "invalid" });
  }
});

test("follows GitHub attachment redirects, preserves bytes and stores real metadata", async () => {
  const h = harness();
  const fetcher = mock.method(
    globalThis,
    "fetch",
    async (url: URL, init: RequestInit) => {
      assert.equal(init.redirect, "manual");
      assert.deepEqual(Object.keys(init.headers!).sort(), [
        "Accept",
        "User-Agent",
      ]);
      if (url.hostname === "github.com")
        return new Response(null, {
          status: 302,
          headers: {
            location:
              "https://release-assets.githubusercontent.com/file?signature=fixture",
          },
        });
      assert.equal(url.hostname, "release-assets.githubusercontent.com");
      return new Response(fixture, {
        headers: {
          "last-modified": "Mon, 02 Nov 2026 05:40:20 GMT",
          etag: '"v1"',
        },
      });
    },
  );
  const response = await getSubscription(
    source,
    "https://site.example",
    h.cache,
    h.ctx,
  );
  assert.equal(await response.text(), fixture);
  assert.equal(response.headers.get("x-node-count"), "2");
  assert.equal(
    response.headers.get("last-modified"),
    "Mon, 02 Nov 2026 05:40:20 GMT",
  );
  assert.ok(response.headers.get("x-fetched-at"));
  await h.flush();
  assert.equal(
    await (
      await getSubscription(source, "https://site.example", h.cache, h.ctx)
    ).text(),
    fixture,
  );
  assert.equal(fetcher.mock.callCount(), 2, "second visit uses cache");
});

test("cache expires in five minutes and the same subscription URL receives fresh content", async () => {
  const h = harness();
  let version = fixture;
  const fetcher = mock.method(
    globalThis,
    "fetch",
    async () => new Response(version),
  );
  await (
    await getSubscription(source, "https://site.example", h.cache, h.ctx)
  ).text();
  await h.flush();
  version = "trojan://test@example.invalid:443#Updated\n";
  h.advance(299_000);
  assert.equal(
    await (
      await getSubscription(source, "https://site.example", h.cache, h.ctx)
    ).text(),
    fixture,
  );
  h.advance(1000);
  assert.equal(
    await (
      await getSubscription(source, "https://site.example", h.cache, h.ctx)
    ).text(),
    version,
  );
  await h.flush();
  assert.equal(fetcher.mock.callCount(), 2);
});

test("rejects foreign, insecure, credentialed and local redirect destinations", async () => {
  for (const location of [
    "https://evil.example/file",
    "http://github.com/file",
    "http://127.0.0.1/",
    "https://user:pass@github.com/file",
    "https://github.com:444/file",
  ]) {
    const h = harness();
    const fetcher = mock.method(
      globalThis,
      "fetch",
      async () => new Response(null, { status: 302, headers: { location } }),
    );
    await assert.rejects(
      getSubscription(source, "https://site.example", h.cache, h.ctx),
      { code: "unavailable" },
    );
    assert.equal(fetcher.mock.callCount(), 1);
    assert.equal(h.entries.size, 0);
    fetcher.mock.restore();
  }
});

test("bad responses and invalid content never enter the cache", async () => {
  for (const response of [
    new Response("missing", { status: 404 }),
    new Response("<html>error</html>"),
    new Response("partial", { status: 206 }),
    new Response(""),
  ]) {
    const h = harness();
    const fetcher = mock.method(globalThis, "fetch", async () => response);
    await assert.rejects(
      getSubscription(source, "https://site.example", h.cache, h.ctx),
    );
    await h.flush();
    assert.equal(h.entries.size, 0);
    fetcher.mock.restore();
  }
});

test("limits both declared and chunked response sizes", async () => {
  for (const response of [
    new Response("small", {
      headers: { "content-length": String(MAX_BYTES + 1) },
    }),
    new Response(new Uint8Array(MAX_BYTES + 1)),
  ]) {
    const h = harness();
    const fetcher = mock.method(globalThis, "fetch", async () => response);
    await assert.rejects(
      getSubscription(source, "https://site.example", h.cache, h.ctx),
      { code: "too_large" },
    );
    assert.equal(h.entries.size, 0);
    fetcher.mock.restore();
  }
});

test("upstream timeout is bounded and reports a timeout", async () => {
  const h = harness();
  mock.timers.enable({ apis: ["setTimeout"] });
  const started = Promise.withResolvers<void>();
  mock.method(
    globalThis,
    "fetch",
    (_url: URL, init: RequestInit) =>
      new Promise((_resolve, reject) => {
        init.signal!.addEventListener(
          "abort",
          () => reject(new Error("aborted")),
          { once: true },
        );
        started.resolve();
      }),
  );
  const result = getSubscription(
    source,
    "https://site.example",
    h.cache,
    h.ctx,
  );
  await started.promise;
  const assertion = assert.rejects(result, { code: "timeout" });
  mock.timers.tick(15_000);
  await assertion;
  mock.timers.reset();
});

test("public routes constrain IDs and methods, ignore visitor parameters and expose usable HEAD", async () => {
  const h = harness();
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "caches");
  Object.defineProperty(globalThis, "caches", {
    configurable: true,
    value: { default: h.cache },
  });
  const fetcher = mock.method(
    globalThis,
    "fetch",
    async (url: URL, init: RequestInit) => {
      assert.equal(
        url.href,
        "https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/subscribe.txt",
      );
      assert.equal(new Headers(init.headers).has("authorization"), false);
      assert.equal(new Headers(init.headers).has("cookie"), false);
      return new Response(fixture);
    },
  );
  try {
    for (const [path, method, status] of [
      ["/sub/unknown", "GET", 404],
      ["/api/missing", "GET", 404],
      ["/sub/all", "POST", 405],
    ]) {
      assert.equal(
        (
          await worker.fetch(
            new Request(`https://site.example${path}`, { method }),
            {} as Env,
            h.ctx as ExecutionContext,
          )
        ).status,
        status,
      );
    }
    assert.equal(fetcher.mock.callCount(), 0);
    const result = await worker.fetch(
      new Request("https://site.example/sub/all?url=https://evil.example", {
        headers: { authorization: "visitor-secret", cookie: "session=visitor" },
      }),
      {} as Env,
      h.ctx as ExecutionContext,
    );
    assert.equal(result.status, 200);
    assert.equal(result.headers.get("cache-control"), "no-store");
    assert.equal(result.headers.get("profile-update-interval"), "6");
    assert.equal(await result.text(), fixture);
    await h.flush();
    const head = await worker.fetch(
      new Request("https://site.example/sub/all", { method: "HEAD" }),
      {} as Env,
      h.ctx as ExecutionContext,
    );
    assert.equal(head.status, 200);
    assert.equal(await head.text(), "");
    assert.equal(head.headers.get("x-node-count"), "2");
    await h.flush();
  } finally {
    if (descriptor) Object.defineProperty(globalThis, "caches", descriptor);
    else Reflect.deleteProperty(globalThis, "caches");
  }
});

test("status preserves independent source failures and never exposes node credentials", async () => {
  const h = harness();
  const descriptor = Object.getOwnPropertyDescriptor(globalThis, "caches");
  Object.defineProperty(globalThis, "caches", {
    configurable: true,
    value: { default: h.cache },
  });
  mock.method(globalThis, "fetch", async (url: URL) =>
    url.pathname.endsWith("subscribe.txt")
      ? new Response(fixture, {
          headers: { "last-modified": "Mon, 02 Nov 2026 05:40:20 GMT" },
        })
      : new Response("missing", { status: 404 }),
  );
  try {
    const result = await worker.fetch(
      new Request("https://site.example/api/status"),
      {} as Env,
      h.ctx as ExecutionContext,
    );
    assert.equal(result.status, 200);
    const text = await result.text();
    assert.ok(!text.includes("test@example.invalid"));
    const body = JSON.parse(text);
    assert.equal(body.sources.length, 7);
    assert.equal(
      body.sources.find((s: { id: string }) => s.id === "all").nodeCount,
      2,
    );
    assert.equal(
      body.sources.find((s: { id: string }) => s.id === "clash").available,
      false,
    );
    assert.equal(
      body.sources.find((s: { id: string }) => s.id === "clash").nodeCount,
      null,
    );
    await h.flush();
  } finally {
    if (descriptor) Object.defineProperty(globalThis, "caches", descriptor);
    else Reflect.deleteProperty(globalThis, "caches");
  }
});
