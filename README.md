# HysteriaNode

自动化多协议代理节点聚合、双阶段测活与标准化订阅转换工具。

## 特性

- **多协议聚合**：支持 Hysteria2、VLESS、VMess、Trojan、TUIC 等主流协议。
- **双阶段测活保障**：
  - **Stage A**：高并发异步 TCP 端口快速探测，毫秒级剔除离线断连节点。
  - **Stage B**：进行真实网络延迟探测，过滤握手失败及假活节点，确保节点高可用。
- **标准化地区命名**：基于 GeoIP 离线数据库自动识别节点真实出口 IP 归属地，规范化输出国旗 Emoji、中文地区名称与协议类型标签（如 `🇯🇵 日本 01 [VLESS]`）。
- **定期自动更新**：GitHub Actions 每 6 小时自动聚合校验并发布最新订阅。

## 目录结构

```
.
├── subscribe.txt          # 所有协议可用节点（推荐）
├── hysteriaNode.txt       # 仅 Hysteria2 节点
├── type/                  # 按协议分类
│   ├── vmess.txt
│   ├── vless.txt
│   ├── trojan.txt
│   └── tuic.txt
└── yaml/
    └── clash.yaml         # Clash 配置文件
```

## 订阅链接（Nekoray/Nekobox/Clash 等客户端可直接导入使用）

### 仅 Hysteria2 类型
- 源地址：`https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/hysteriaNode.txt`
- 加速地址：`https://hk.gh-proxy.org/https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/hysteriaNode.txt`

### 全类型聚合（推荐）
- 源地址：`https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/subscribe.txt`
- 加速地址：`https://hk.gh-proxy.org/https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/subscribe.txt`

### Clash 配置文件
- 源地址：`https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/yaml/clash.yaml`
- 加速地址：`https://hk.gh-proxy.org/https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/yaml/clash.yaml`

## 使用说明

1. 复制上方所需格式的订阅链接（网络受限环境可选用加速地址）。
2. 在客户端中添加订阅链接并更新节点。
3. 建议设置客户端的定时更新机制，以及时获取最新测活结果。

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
