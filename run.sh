#!/bin/bash

subscribeUrl="https://pp.dcd.one/clash/proxies?speed=15,30&type=hysteria2,hysteria,vless,vmess,trojan"
subscribeUrl_net="https://v1.mk/keN5oxQ"
subscribeUrl_hy="https://pp.dcd.one/clash/proxies?speed=15,30&type=hysteria2,hysteria"
subscribeUrl_me="https://pp.dcd.one/clash/proxies?speed=15,30&type=hysteria2,hysteria,vless,vmess,trojan"
subscribeUrl_me_bak="https://pp.dcd.one/clash/proxies?speed=15,30&type=hysteria2,hysteria,vless,vmess,trojan&stream=netflix,disney"

echo "start getting the subscribe"
wget $subscribeUrl -O ./subscribe.txt
sed -i '/"name":"NULL"/d' ./subscribe.txt
sed -i '/"server":"NULL"/d' ./subscribe.txt

echo "------------------- subscribe from net -------------------"

wget $subscribeUrl_net -O ./subscribe_net.txt
sed -i '/"name":"NULL"/d' ./subscribe_net.txt
sed -i '/"server":"NULL"/d' ./subscribe_net.txt

echo "------------------- hysteria2 -------------------"

wget $subscribeUrl_hy -O ./hysteriaNode.txt
sed -i '/"name":"NULL"/d' ./hysteriaNode.txt
sed -i '/"server":"NULL"/d' ./hysteriaNode.txt

echo "------------------- my custom -------------------"

wget $subscribeUrl_me -O ./mineNode.txt
sed -i '/"name":"NULL"/d' ./mineNode.txt
sed -i '/"server":"NULL"/d' ./mineNode.txt

mineNodeSize=$(grep -c '"name":' ./mineNode.txt)

if [ $mineNodeSize -gt 0 ]; then
    echo "mineNodeSize:$mineNodeSize"
else
    wget $subscribeUrl_subscribeUrl_me_bak -O ./mineNode.txt
    sed -i '/"name":"NULL"/d' ./mineNode.txt
    sed -i '/"server":"NULL"/d' ./mineNode.txt
fi

echo "getting the subscribe succeed,enjoy it~"
