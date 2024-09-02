# HysteriaNode 订阅网站

连接 [HysteriaNode 仓库](https://github.com/AkkunYo/HysteriaNode) 的独立订阅网站。静态页面与订阅接口一同部署到 Cloudflare Workers，不需要数据库、GitHub Token 或第三方订阅转换服务。

**已部署站点：** <https://hysterianode-site.blue-shadow-9cb5.workers.dev>

网站源码保存在本仓库的 `site/` 目录，部署到 Cloudflare Worker `hysterianode-site`。静态页面与订阅接口一起发布。

## 已接入的数据

上游 GitHub Actions 计划每 6 小时运行，覆盖 `prerelease` 的附件。本站提供固定 URL；访问时读取附件并在当前 Cloudflare 数据中心缓存 5 分钟。客户端更新同一个链接即可同步，无需随发布更换地址，也无需在每次节点更新后重新部署网站。

| 网站路径 | 上游附件 | 格式 |
| --- | --- | --- |
| `/sub/clash` | `clash.yaml` | 完整 Clash / Mihomo YAML |
| `/sub/all` | `subscribe.txt` | 全量节点 URI 列表 |
| `/sub/selected` | `selected.txt` | 精选地区 URI 列表 |
| `/sub/hysteria2` | `hysteriaNode.txt` | Hysteria2 URI 列表 |
| `/sub/vless` | `vless.txt` | VLESS URI 列表 |
| `/sub/vmess` | `vmess.txt` | VMess URI 列表 |
| `/sub/trojan` | `trojan.txt` | Trojan URI 列表 |

例如，部署后的完整链接为 `https://你的域名/sub/clash`。网页自动使用访问时的域名生成链接，因此绑定自定义域名后不需要修改页面。

`GET /api/status` 返回每个文件的获取状态、解析出的节点数、GitHub 附件的 `Last-Modified` 时间和最近获取时间。不同格式的节点数可能不同；例如上游转换为 Clash 时可能略过不支持的节点，页面按各文件分别统计。

页面提供订阅类型切换、复制链接、Clash 一键导入、原文件查看、刷新状态、手机布局、键盘操作和使用教程。其余 URI 订阅采用手动导入。仓库目前没有 sing-box JSON，本项目也不做格式转换。

## 本地运行

使用 Node.js 22.18+ 或较新 LTS 版本：

```bash
cd site
npm ci
npm run types
npm run dev
```

打开 <http://127.0.0.1:8787>。首次加载会请求 GitHub 附件，需要本机能够访问 GitHub。`wrangler dev` 在本地模拟 Worker 和缓存，不会创建公网服务。

## 验证

```bash
npm test
npm run check
npm run build
```

- 自动测试覆盖格式解析、Release 重定向限制、字节保真、缓存命中及过期、超时、文件大小上限、错误响应不缓存、HTTP 方法与路径、访客参数隔离和状态接口的局部失败。
- 页面交互在 DOM 测试环境中检查：订阅切换、键盘导航、Clash 导入地址、复制及手动回退、请求失败与重试。此类测试不代替浏览器视觉验收。
- `check` 检查生成的绑定类型、TypeScript 和浏览器脚本语法。
- `build` 是 Wrangler 部署预检（`--dry-run`），仅产出本地构建文件。

`.github/workflows/site.yml` 在网站源码或该工作流发生变更时执行这些检查。CI 会先运行 `npm ci` 和 `npm run types`，生成未纳入 Git 的 Worker 类型文件，再运行测试、类型检查和部署预检。网站检查与每 6 小时的节点聚合任务分开执行。

## 部署到 Cloudflare

在项目目录下执行：

```bash
npx wrangler login
npm run deploy
```

本仓库维护已上线的 `hysterianode-site` Worker。在其所属 Cloudflare 账号下使用此名称部署，会更新现有网站并保留其 `workers.dev` 地址。若 fork 本项目用于其他网站，请先在 `wrangler.jsonc` 中修改 Worker 名称。部署会一起上传 `public/` 页面和 Worker，终端会显示公网地址。

绑定域名：进入 Cloudflare Dashboard → Workers & Pages → `hysterianode-site` → Settings → Domains & Routes → Add → Custom Domain，选择你在该账号管理的域名。也可继续使用部署生成的 `workers.dev` 地址。确保站点通过 HTTPS 访问，以便浏览器使用剪贴板功能。

本实现无需 KV、R2 或付费数据库。实际运行仍受所选 Workers 套餐的请求量、CPU 和资源限制约束。

## 修改源与维护

- `site.config.ts`：仓库、固定 Release tag、7 个源文件、描述、缓存时长和客户端建议更新间隔。
- `public/index.html`：品牌文案、订阅选项和使用指南；增删订阅时同步调整页面选项。
- `public/style.css`、`public/app.js`：样式与交互。
- `src/subscriptions.ts`：受限下载、内容解析及缓存。
- `src/worker.ts`：公开的状态与订阅路由。
- `wrangler.jsonc`：Worker 名称、资源绑定和日志采样。

改动代码、文件名或源配置后，在 `site/` 中运行 `npm run deploy`；上游仅更新现有附件内容时无需重新部署。目前 GitHub Actions 负责网站验证，不持有 Cloudflare 部署凭据。若需要网站源码自动部署，可在 Cloudflare Workers Builds 中连接本 GitHub 仓库，将根目录设为 `site/`，并将部署触发范围限定为网站源码；节点数据同步不依赖此步骤。

## 数据与错误行为

“文件可获取”只表示本站成功下载、解析了附件。节点数量由 URI 行数或 YAML `proxies` 数组计算，属于文件条目数；本站不做节点实时测活、去重或测速，也不生成虚构的通过率和时延。最新更新时间指当前缓存中的 GitHub 文件时间，缺失时显示 `—`。

GitHub 替换附件期间可能短暂出现 404；源超时、格式异常或超过 2 MiB 时，订阅接口返回 502/504，状态接口对对应源单独报错。失败响应不缓存，已有成功缓存按原 5 分钟期限继续使用；到期后不会悄悄回退到过期内容。页面的“刷新状态”会读取当前边缘缓存，不强制绕过 5 分钟缓存。

订阅按原始字节分发，不修改原配置。服务只读取配置中的公开 GitHub 附件，重定向限于 GitHub 官方下载域名；访客不能指定上游 URL，Cookie 和 Authorization 不会转发。页面不使用外部脚本、字体或广告追踪。

部分自动化客户端的 User-Agent 可能受到 `workers.dev` 访问策略限制，返回 HTTP 403 / 1010。接入时应确认实际客户端能够访问站点；绑定自定义域名后，可在域名设置中管理相应访问规则。
