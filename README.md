# HysteriaNode

## 简介
> 聚合多个 GitHub 开源订阅源的 Hysteria2 和多协议类型
- 每 6 小时自动更新
- 多源聚合、自动去重、错误容错
- 支持 Hysteria2/VMess/VLESS/Trojan/TUIC
- 过滤 SS/HTTP/SOCKS 协议节点

## 目录结构

```
.
├── subscribe.txt          # 所有协议节点（推荐）
├── hysteriaNode.txt       # 仅 Hysteria2 节点
├── type/                  # 按协议分类
│   ├── vmess.txt
│   ├── vless.txt
│   ├── trojan.txt
│   └── tuic.txt
└── yaml/
    └── clash.yaml         # Clash 配置文件
```

## 订阅链接（Nekoray/Nekobox 可直接导入订阅使用）

### 仅 Hysteria2 类型
- 源地址：[https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/hysteriaNode.txt](https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/hysteriaNode.txt)
- 加速地址：[https://hk.gh-proxy.org/https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/hysteriaNode.txt](https://hk.gh-proxy.org/https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/hysteriaNode.txt)

### 全类型
- 源地址：[https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/subscribe.txt](https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/subscribe.txt)
- 加速地址：[https://hk.gh-proxy.org/https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/subscribe.txt](https://hk.gh-proxy.org/https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/subscribe.txt)

### Clash 配置
- 源地址：[https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/yaml/clash.yaml](https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/yaml/clash.yaml)
- 加速地址：[https://hk.gh-proxy.org/https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/yaml/clash.yaml](https://hk.gh-proxy.org/https://raw.githubusercontent.com/AkkunYo/HysteriaNode/main/yaml/clash.yaml)

## 使用方法

1. 复制链接
2. 添加到客户端的订阅管理器
3. 更新订阅

## 免责声明

本代码仅用于学习，下载后24h内删除，请勿用于商业用途
