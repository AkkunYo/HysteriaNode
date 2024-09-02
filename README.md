# HysteriaNode

[![GitHub Release](https://img.shields.io/github/v/release/AkkunYo/HysteriaNode?include_prereleases&label=release&color=blue&logo=github)](https://github.com/AkkunYo/HysteriaNode/releases/tag/prerelease)
[![Workflow Status](https://img.shields.io/github/actions/workflow/status/AkkunYo/HysteriaNode/main.yml?label=auto-update&logo=githubactions)](https://github.com/AkkunYo/HysteriaNode/actions)
[![License](https://img.shields.io/github/license/AkkunYo/HysteriaNode?color=green)](LICENSE)

自动化多协议代理节点聚合、双阶段测活与标准化订阅转换工具。

## 特性

- **多协议聚合**：支持 Hysteria2、VLESS、VMess、Trojan 等主流协议。
- **双阶段测活保障**：
  - **Stage A**：高并发异步探测，毫秒级剔除离线断连节点（针对 Hysteria2 等 UDP 协议智能放行，避免误杀）。
  - **Stage B**：进行真实网络延迟探测，过滤握手失败及假活节点，确保节点高可用。
- **标准化地区命名**：基于 GeoIP 离线数据库自动识别节点真实出口 IP 归属地，规范化输出国旗 Emoji、中文地区名称与协议类型标签（如 `🇯🇵 日本 01 [VLESS]`）。
- **定期自动更新**：GitHub Actions 每 6 小时自动聚合校验并发布至 Releases (Pre-release)，源码仓库保持干净零提交。

## 订阅链接一览

所有成品文件均自动发布在 [Releases (Pre-release)](https://github.com/AkkunYo/HysteriaNode/releases/tag/prerelease) 中，每次构建自动覆盖更新：

| 订阅类型 | 包含协议 / 说明 | 官方源地址 (GitHub Direct) | 镜像加速地址 (推荐) |
|---|---|---|---|
| **全类型聚合（推荐）** | 所有通过测活的有效节点集合 | [下载 / 导入](https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/subscribe.txt) | [点击复制 / 导入](https://hk.gh-proxy.org/https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/subscribe.txt) |
| **特选指定国家** | 西班牙/墨西哥/巴西/英国/菲律宾/印度/日本/新加坡 (每国至多2个) | [下载 / 导入](https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/selected.txt) | [点击复制 / 导入](https://hk.gh-proxy.org/https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/selected.txt) |
| **仅 Hysteria2** | 仅 Hysteria2 高速节点 | [下载 / 导入](https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/hysteriaNode.txt) | [点击复制 / 导入](https://hk.gh-proxy.org/https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/hysteriaNode.txt) |
| **Clash 配置文件** | 包含自动分流、地区策略组与规则集的完整 YAML | [下载 / 导入](https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/clash.yaml) | [点击复制 / 导入](https://hk.gh-proxy.org/https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/clash.yaml) |
| **VLESS 独立** | 仅 VLESS 协议 | [下载 / 导入](https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/vless.txt) | [点击复制 / 导入](https://hk.gh-proxy.org/https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/vless.txt) |
| **VMess 独立** | 仅 VMess 协议 | [下载 / 导入](https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/vmess.txt) | [点击复制 / 导入](https://hk.gh-proxy.org/https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/vmess.txt) |
| **Trojan 独立** | 仅 Trojan 协议 | [下载 / 导入](https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/trojan.txt) | [点击复制 / 导入](https://hk.gh-proxy.org/https://github.com/AkkunYo/HysteriaNode/releases/download/prerelease/trojan.txt) |

## 客户端支持与使用说明

1. **兼容客户端推荐**：
   - **Windows / macOS / Linux**：[Clash Verge Rev](https://github.com/clash-verge-rev/clash-verge-rev)、[Mihomo Party](https://github.com/mihomo-party-org/mihomo-party)、[NekoRay](https://github.com/MatsuriDayo/nekoray)、[v2rayN](https://github.com/2dust/v2rayN)
   - **Android**：[NekoBox for Android](https://github.com/MatsuriDayo/NekoBoxForAndroid)、[Clash Meta for Android](https://github.com/MetaCubeX/ClashMetaForAndroid)、[v2rayNG](https://github.com/2dust/v2rayNG)
   - **iOS**：Shadowrocket、Loon、Stash、Sing-box
2. **导入步骤**：
   - 复制上方所需格式的订阅链接（网络受限环境建议使用加速地址）。
   - 在客户端中新建订阅并更新节点。
   - 建议将客户端的**定时自动更新**间隔设置为 6 小时或 12 小时，以同步最新的测活可用节点。

## 免责声明与风险提示 (Disclaimer & Security Warning)

### 1. 节点安全性与隐私风险
本项目自动收集、探测与整理的所有节点数据均抓取自互联网公开渠道。
- **严禁传输敏感隐私数据**：公开节点的出入口流量存在被第三方镜像、监听、记录日志或中间人劫持的潜在风险。切勿通过公共免费节点登录网上银行、个人邮箱、输入账号密码等进行任何高敏操作。
- **不保证连通稳定性与可用性**：本项目不对节点的网络延迟、传输速率、长效可用性作任何明示或暗示的保证。

### 2. 合规使用与法律界限
- 本项目开源代码仅供计算机网络协议研究、网络编程实践及自动化运维技术交流学习使用。
- 任何个人或组织在使用本项目提供的代码或节点数据时，必须严格遵守所在国家与地区的法律法规。
- 严禁将本项目用于任何违法犯罪、商业倒卖、未授权渗透攻击或违反网络安全规定的行为。因使用或滥用本项目产生的任何直接或间接法律责任、行政处罚或财产损失，均由使用者自行承担，与本项目开发者及贡献者无关。

## 开源协议

本项目采用 [MIT License](LICENSE) 授权。
