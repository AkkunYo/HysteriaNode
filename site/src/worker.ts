import { site } from "../site.config.ts";
import { getSubscription, SourceError } from "./subscriptions.ts";

const COMMON_HEADERS = {
  "cache-control": "no-store",
  "x-content-type-options": "nosniff",
  "referrer-policy": "no-referrer",
  "content-security-policy": "default-src 'none'; frame-ancestors 'none'",
};

function json(data: unknown, status = 200): Response {
  return Response.json(data, { status, headers: COMMON_HEADERS });
}

function message(error: unknown): string {
  if (error instanceof SourceError && error.code === "timeout")
    return "源文件响应超时，请稍后重试。";
  if (error instanceof SourceError && error.code === "invalid")
    return "源文件格式异常或暂无节点，请稍后重试。";
  if (error instanceof SourceError && error.code === "too_large")
    return "源文件超出本站大小限制。";
  return "暂时无法获取源文件，可能正在更新，请稍后重试。";
}

export default {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const url = new URL(request.url);
    if (
      !url.pathname.startsWith("/api/") &&
      !url.pathname.startsWith("/sub/")
    ) {
      return env.ASSETS.fetch(request);
    }
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response(null, {
        status: 405,
        headers: { ...COMMON_HEADERS, allow: "GET, HEAD" },
      });
    }
    const head = request.method === "HEAD";
    if (url.pathname === "/api/status") {
      if (head)
        return new Response(null, {
          headers: {
            ...COMMON_HEADERS,
            "content-type": "application/json; charset=utf-8",
          },
        });
      const sources = await Promise.all(
        site.sources.map(async (source) => {
          const info = {
            ...source,
            path: `/sub/${source.id}`,
            available: false,
            nodeCount: null as number | null,
            updatedAt: null as string | null,
            fetchedAt: null as string | null,
            error: null as string | null,
          };
          try {
            const response = await getSubscription(
              source,
              url.origin,
              caches.default,
              ctx,
            );
            info.available = true;
            info.nodeCount = Number(response.headers.get("x-node-count"));
            const modified = response.headers.get("last-modified");
            if (modified && Number.isFinite(Date.parse(modified)))
              info.updatedAt = new Date(modified).toISOString();
            info.fetchedAt = response.headers.get("x-fetched-at");
            if (response.body)
              ctx.waitUntil(response.body.cancel().catch(() => {}));
          } catch (error) {
            info.error = message(error);
            console.warn(
              JSON.stringify({
                event: "source_unavailable",
                source: source.id,
                code: error instanceof SourceError ? error.code : "unknown",
              }),
            );
          }
          return info;
        }),
      );
      return json({
        name: site.name,
        repository: `https://github.com/${site.repository}`,
        release: `https://github.com/${site.repository}/releases/tag/${encodeURIComponent(site.releaseTag)}`,
        cacheSeconds: site.cacheSeconds,
        updateHours: site.updateHours,
        sources,
      });
    }
    const source = site.sources.find(
      (item) => url.pathname === `/sub/${item.id}`,
    );
    if (!source)
      return head
        ? new Response(null, { status: 404, headers: COMMON_HEADERS })
        : json({ error: "订阅地址不存在。" }, 404);
    try {
      const response = await getSubscription(
        source,
        url.origin,
        caches.default,
        ctx,
      );
      const headers = new Headers(response.headers);
      for (const [name, value] of Object.entries(COMMON_HEADERS))
        headers.set(name, value);
      headers.set("content-disposition", `inline; filename="${source.file}"`);
      headers.set("profile-update-interval", String(site.updateHours));
      headers.set("profile-web-page-url", url.origin);
      if (head && response.body)
        ctx.waitUntil(response.body.cancel().catch(() => {}));
      return new Response(head ? null : response.body, { headers });
    } catch (error) {
      const status =
        error instanceof SourceError && error.code === "timeout" ? 504 : 502;
      return head
        ? new Response(null, { status, headers: COMMON_HEADERS })
        : json({ error: message(error) }, status);
    }
  },
} satisfies ExportedHandler<Env>;
