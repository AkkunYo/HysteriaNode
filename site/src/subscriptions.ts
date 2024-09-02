import { parse } from "yaml";
import { site, type Subscription } from "../site.config.ts";

export const MAX_BYTES = 2 * 1024 * 1024;
const TIMEOUT_MS = 15_000;
const DOWNLOAD_HOSTS = new Set([
  "github.com",
  "release-assets.githubusercontent.com",
  "objects.githubusercontent.com",
]);
const URI_LINE =
  /^(?:hysteria2|hy2|hysteria|vless|vmess|trojan|ss|ssr|tuic):\/\/\S+$/;

export class SourceError extends Error {
  code: "unavailable" | "invalid" | "too_large" | "timeout";
  constructor(code: SourceError["code"]) {
    super(code);
    this.code = code;
  }
}

export function sourceUrl(source: Subscription): string {
  const repository = site.repository
    .split("/")
    .map(encodeURIComponent)
    .join("/");
  return `https://github.com/${repository}/releases/download/${encodeURIComponent(site.releaseTag)}/${encodeURIComponent(source.file)}`;
}

export function countNodes(
  text: string,
  format: Subscription["format"],
): number {
  try {
    if (format === "clash") {
      const document = parse(text, { maxAliasCount: 100 });
      if (
        !document ||
        !Array.isArray(document.proxies) ||
        document.proxies.length === 0 ||
        !document.proxies.every(
          (proxy: unknown) =>
            proxy &&
            typeof proxy === "object" &&
            "type" in proxy &&
            "name" in proxy,
        )
      ) {
        throw new SourceError("invalid");
      }
      return document.proxies.length;
    }
    const lines = text
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
    if (lines.length === 0 || !lines.every((line) => URI_LINE.test(line)))
      throw new SourceError("invalid");
    return lines.length;
  } catch {
    throw new SourceError("invalid");
  }
}

async function readLimited(
  response: Response,
): Promise<Uint8Array<ArrayBuffer>> {
  if (Number(response.headers.get("content-length")) > MAX_BYTES) {
    await response.body?.cancel();
    throw new SourceError("too_large");
  }
  if (!response.body) throw new SourceError("invalid");
  const reader = response.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > MAX_BYTES) {
        await reader.cancel();
        throw new SourceError("too_large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return bytes;
}

async function download(source: Subscription): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    let url = new URL(sourceUrl(source));
    for (let redirects = 0; redirects <= 3; redirects++) {
      // Only configured release files and GitHub's attachment hosts are reachable.
      if (
        url.protocol !== "https:" ||
        !DOWNLOAD_HOSTS.has(url.hostname) ||
        url.username ||
        url.password ||
        url.port
      ) {
        throw new SourceError("unavailable");
      }
      const response = await fetch(url, {
        redirect: "manual",
        signal: controller.signal,
        cache: "no-store",
        headers: {
          Accept: "application/octet-stream",
          "User-Agent": "HysteriaNode-Subscription-Site",
        },
      });
      if ([301, 302, 303, 307, 308].includes(response.status)) {
        await response.body?.cancel();
        const location = response.headers.get("location");
        if (!location) throw new SourceError("unavailable");
        url = new URL(location, url);
        continue;
      }
      if (response.status !== 200) {
        await response.body?.cancel();
        throw new SourceError("unavailable");
      }
      const bytes = await readLimited(response);
      const count = countNodes(
        new TextDecoder("utf-8", { fatal: true, ignoreBOM: false }).decode(
          bytes,
        ),
        source.format,
      );
      const headers = new Headers({
        "content-type": "text/plain; charset=utf-8",
        "content-length": String(bytes.byteLength),
        "cache-control": `public, max-age=${site.cacheSeconds}`,
        "x-node-count": String(count),
        "x-fetched-at": new Date().toISOString(),
      });
      for (const name of ["etag", "last-modified"]) {
        const value = response.headers.get(name);
        if (value) headers.set(name, value);
      }
      return new Response(bytes, { headers });
    }
    throw new SourceError("unavailable");
  } catch (error) {
    if (controller.signal.aborted) throw new SourceError("timeout");
    if (error instanceof SourceError) throw error;
    throw new SourceError("unavailable");
  } finally {
    clearTimeout(timeout);
  }
}

export async function getSubscription(
  source: Subscription,
  origin: string,
  cache: Pick<Cache, "match" | "put">,
  ctx: Pick<ExecutionContext, "waitUntil">,
): Promise<Response> {
  // The source URL is part of the key so changing configuration cannot serve a previous source.
  // Visitor queries and headers never enter the upstream request or cache key.
  const key = new Request(
    `${origin}/__subscription_cache/v1/${encodeURIComponent(sourceUrl(source))}`,
  );
  try {
    const cached = await cache.match(key);
    if (cached) return cached;
  } catch {
    console.warn(
      JSON.stringify({ event: "cache_read_failed", source: source.id }),
    );
  }
  const response = await download(source);
  ctx.waitUntil(
    cache.put(key, response.clone()).catch(() => {
      console.warn(
        JSON.stringify({ event: "cache_write_failed", source: source.id }),
      );
    }),
  );
  return response;
}
