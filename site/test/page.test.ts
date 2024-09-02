import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { Window } from "happy-dom";
import { site } from "../site.config.ts";

const html = await readFile(new URL("../public/index.html", import.meta.url), "utf8");
const script = await readFile(new URL("../public/app.js", import.meta.url), "utf8");
const fixture = {
  sources: site.sources.map(source => ({
    ...source, available: true, nodeCount: 4, error: null,
    updatedAt: "2026-11-02T05:40:20.000Z", fetchedAt: "2026-11-02T06:00:00.000Z"
  }))
};

async function page(fail = false) {
  const window = new Window({ url: "https://nodes.example", settings: {
    disableCSSFileLoading: true, disableJavaScriptFileLoading: true
  } });
  window.fetch = async () => new window.Response(JSON.stringify(fixture), { status: fail ? 503 : 200 });
  window.document.write(html);
  window.eval(script);
  await window.happyDOM.whenAsyncComplete();
  return window;
}

test("renders server data and switches each tab to the correct stable URL", async () => {
  const window = await page();
  const doc = window.document;
  try {
    assert.equal(doc.getElementById("total-count")!.textContent, "4");
    assert.equal(doc.getElementById("source-status")!.textContent, "文件可获取");
    const install = new URL(doc.getElementById("import")!.getAttribute("href")!);
    assert.equal(install.protocol, "clash:");
    assert.equal(install.searchParams.get("url"), "https://nodes.example/sub/clash");
    for (const source of site.sources) {
      doc.getElementById(`tab-${source.id}`)!.click();
      assert.equal(doc.querySelector<HTMLInputElement>("#subscription-url")!.value, `https://nodes.example/sub/${source.id}`);
      assert.equal(doc.getElementById("source-title")!.textContent, source.name);
      assert.equal(doc.getElementById("import")!.hidden, source.id !== "clash");
      assert.equal(doc.querySelectorAll('[role="tab"][aria-selected="true"]').length, 1);
      assert.equal(doc.getElementById("source-panel")!.getAttribute("aria-labelledby"), `tab-${source.id}`);
    }
    const tab = doc.getElementById("tab-trojan")!;
    tab.focus();
    tab.dispatchEvent(new window.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
    assert.equal(doc.activeElement?.id, "tab-clash");
  } finally { await window.happyDOM.close(); }
});

test("copy writes the stable URL and clipboard rejection selects a manual fallback", async () => {
  const window = await page();
  const doc = window.document;
  let copied = "";
  try {
    Object.defineProperty(window.navigator, "clipboard", { configurable: true,
      value: { async writeText(text: string) { copied = text; } } });
    doc.getElementById("copy")!.click();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(copied, "https://nodes.example/sub/clash");
    assert.equal(doc.getElementById("toast")!.hidden, false);
    Object.defineProperty(window.navigator, "clipboard", { configurable: true,
      value: { async writeText() { throw new Error("permission denied"); } } });
    doc.getElementById("copy")!.click();
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(doc.activeElement?.id, "subscription-url");
    assert.match(doc.getElementById("toast")!.textContent!, /系统复制/);
  } finally { await window.happyDOM.close(); }
});

test("API errors clear statistics, disable unavailable links and leave retry usable", async () => {
  const window = await page(true);
  const doc = window.document;
  try {
    assert.equal(doc.getElementById("load-error")!.hidden, false);
    assert.equal(doc.getElementById("total-count")!.textContent, "—");
    assert.equal(doc.querySelector<HTMLButtonElement>("#copy")!.disabled, true);
    assert.equal(doc.getElementById("import")!.hasAttribute("href"), false);
    assert.equal(doc.querySelector<HTMLButtonElement>("#refresh")!.disabled, false);
    assert.equal(doc.getElementById("source-panel")!.getAttribute("aria-busy"), "false");
    window.fetch = async () => new window.Response(JSON.stringify(fixture));
    doc.getElementById("refresh")!.click();
    await window.happyDOM.whenAsyncComplete();
    assert.equal(doc.getElementById("load-error")!.hidden, true);
    assert.equal(doc.querySelector<HTMLButtonElement>("#copy")!.disabled, false);
    assert.equal(doc.getElementById("total-count")!.textContent, "4");
  } finally { await window.happyDOM.close(); }
});
