const $ = (id) => document.getElementById(id);
let sources = [];
let active = "clash";
let loading = false;
let toastTimer;

function formatTime(value, options = {}) {
  if (!value || !Number.isFinite(Date.parse(value))) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    ...options,
  }).format(new Date(value));
}

function notify(message) {
  clearTimeout(toastTimer);
  $("toast").textContent = message;
  $("toast").hidden = false;
  toastTimer = setTimeout(() => {
    $("toast").hidden = true;
  }, 4000);
}

function setLink(element, href) {
  element.classList.toggle("disabled", !href);
  element.setAttribute("aria-disabled", String(!href));
  if (href) {
    element.href = href;
    element.removeAttribute("tabindex");
  } else {
    element.removeAttribute("href");
    element.tabIndex = -1;
  }
}

function renderSource() {
  const source = sources.find((item) => item.id === active);
  const tab = document.querySelector(`[data-source="${active}"]`);
  for (const button of document.querySelectorAll("[data-source]")) {
    button.setAttribute("aria-selected", String(button === tab));
    button.tabIndex = button === tab ? 0 : -1;
  }
  $("source-panel").setAttribute("aria-labelledby", `tab-${active}`);
  $("source-title").textContent =
    source?.name ?? tab.childNodes[0].textContent.trim();
  $("format-label").textContent =
    active === "clash" ? "YAML CONFIG" : "NODE URI LIST";
  $("source-description").textContent =
    source?.description ?? "正在读取订阅信息…";
  $("source-clients").textContent = source?.clients ?? "—";
  $("source-count").textContent =
    source?.nodeCount?.toLocaleString("zh-CN") ?? "—";
  $("source-status").textContent = !source
    ? "等待获取"
    : source.available
      ? "文件可获取"
      : "暂时不可用";
  $("source-status").className =
    `status-badge ${!source ? "pending" : source.available ? "" : "failed"}`;
  $("source-error").hidden = !source?.error;
  $("source-error").textContent = source?.error ?? "";
  $("fetched-at").textContent = source?.fetchedAt
    ? `最近获取 ${formatTime(source.fetchedAt)} (UTC+8)`
    : "暂无获取记录";
  // Only the server's known source IDs determine addresses; no arbitrary URL is inserted.
  const link = source ? new URL(`/sub/${active}`, location.origin).href : "";
  $("subscription-url").value = link;
  $("copy").disabled = !link;
  setLink($("download"), link);
  $("download").target = "_blank";
  $("download").rel = "noopener noreferrer";
  $("import").hidden = active !== "clash";
  setLink(
    $("import"),
    link && active === "clash"
      ? `clash://install-config?url=${encodeURIComponent(link)}&name=${encodeURIComponent("HysteriaNode")}`
      : "",
  );
  $("link-help").textContent =
    active === "clash"
      ? "一键导入需要已安装支持 clash:// 协议的客户端；也可以复制链接手动添加。"
      : "在客户端的订阅管理中添加此链接。文件为原始节点 URI 列表，请确认客户端支持对应格式及协议。";
}

async function refresh() {
  if (loading) return;
  loading = true;
  $("refresh").disabled = true;
  $("refresh").textContent = "读取中…";
  $("source-panel").setAttribute("aria-busy", "true");
  $("load-error").hidden = true;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 25000);
  try {
    const response = await fetch("/api/status", {
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) throw new Error("status_unavailable");
    const data = await response.json();
    if (!Array.isArray(data.sources)) throw new Error("invalid_status");
    sources = data.sources;
    for (const [id, field] of [
      ["all", "total-count"],
      ["hysteria2", "hy-count"],
      ["selected", "selected-count"],
    ]) {
      $(field).textContent =
        sources
          .find((source) => source.id === id)
          ?.nodeCount?.toLocaleString("zh-CN") ?? "—";
    }
    const all = sources.find((source) => source.id === "all");
    $("updated-at").textContent = formatTime(all?.updatedAt);
    $("update-note").textContent = all?.updatedAt
      ? "全量文件 · 北京时间 (UTC+8)"
      : "上游未提供可用更新时间";
    renderSource();
  } catch {
    $("load-error").textContent =
      "暂时无法读取订阅状态，请稍后点击刷新重试。你也可以前往 GitHub 查看最新发布。";
    $("load-error").hidden = false;
    sources = [];
    for (const id of [
      "total-count",
      "hy-count",
      "selected-count",
      "updated-at",
    ])
      $(id).textContent = "—";
    $("update-note").textContent = "状态获取失败";
    renderSource();
  } finally {
    clearTimeout(timeout);
    loading = false;
    $("refresh").disabled = false;
    $("refresh").textContent = "↻ 刷新状态";
    $("source-panel").setAttribute("aria-busy", "false");
  }
}

$("source-tabs").addEventListener("click", (event) => {
  const tab = event.target.closest("[data-source]");
  if (!tab) return;
  active = tab.dataset.source;
  renderSource();
});
$("source-tabs").addEventListener("keydown", (event) => {
  const tabs = [...document.querySelectorAll("[data-source]")];
  const index = tabs.indexOf(document.activeElement);
  if (
    index < 0 ||
    !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
  )
    return;
  event.preventDefault();
  const next =
    event.key === "Home"
      ? 0
      : event.key === "End"
        ? tabs.length - 1
        : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
          tabs.length;
  active = tabs[next].dataset.source;
  renderSource();
  tabs[next].focus();
});
$("copy").addEventListener("click", async () => {
  const input = $("subscription-url");
  if (!input.value) return;
  try {
    await navigator.clipboard.writeText(input.value);
    notify("订阅链接已复制，去客户端添加即可。");
  } catch {
    input.focus();
    input.select();
    notify("已选中链接，请使用系统复制功能或 Ctrl / ⌘ + C。");
  }
});
$("subscription-url").addEventListener("click", (event) =>
  event.target.select(),
);
$("refresh").addEventListener("click", refresh);
void refresh();
