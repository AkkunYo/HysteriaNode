export interface Subscription {
  id: string;
  name: string;
  file: string;
  format: "clash" | "uri";
  description: string;
  clients: string;
}

// Releases 的附件会覆盖更新；固定 tag 保证客户端订阅地址长期不变。
export const site = {
  name: "HysteriaNode",
  repository: "AkkunYo/HysteriaNode",
  releaseTag: "prerelease",
  cacheSeconds: 300,
  updateHours: 6,
  sources: [
    {
      id: "clash",
      name: "Clash / Mihomo",
      file: "clash.yaml",
      format: "clash",
      description:
        "完整 Clash 配置，包含节点、地区策略组与分流规则。适合直接导入 Mihomo 内核客户端。",
      clients: "Clash Verge Rev · FlClash · Stash",
    },
    {
      id: "all",
      name: "全量订阅",
      file: "subscribe.txt",
      format: "uri",
      description:
        "汇聚 Hysteria2、VLESS、VMess 与 Trojan 等协议，保留上游发布的全部节点。",
      clients: "v2rayN · v2rayNG · Shadowrocket（需支持相应协议）",
    },
    {
      id: "selected",
      name: "精选地区",
      file: "selected.txt",
      format: "uri",
      description:
        "按上游指定的国家与地区筛选，每个国家至多保留 2 个节点，便于快速选择。",
      clients: "v2rayN · v2rayNG · Shadowrocket（需支持相应协议）",
    },
    {
      id: "hysteria2",
      name: "Hysteria2",
      file: "hysteriaNode.txt",
      format: "uri",
      description:
        "仅保留 Hysteria2 协议节点。使用前请确认客户端支持 Hysteria2，且网络允许 UDP。",
      clients: "支持 Hysteria2 的 v2rayN · v2rayNG · Shadowrocket",
    },
    {
      id: "vless",
      name: "VLESS",
      file: "vless.txt",
      format: "uri",
      description: "仅包含 VLESS 协议节点的独立订阅。",
      clients: "支持 VLESS 的 v2rayN · v2rayNG · Shadowrocket",
    },
    {
      id: "vmess",
      name: "VMess",
      file: "vmess.txt",
      format: "uri",
      description: "仅包含 VMess 协议节点的独立订阅。",
      clients: "支持 VMess 的 v2rayN · v2rayNG · Shadowrocket",
    },
    {
      id: "trojan",
      name: "Trojan",
      file: "trojan.txt",
      format: "uri",
      description: "仅包含 Trojan 协议节点的独立订阅。",
      clients: "支持 Trojan 的 v2rayN · v2rayNG · Shadowrocket",
    },
  ] satisfies Subscription[],
};
