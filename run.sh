#!/bin/bash

subscribeUrl="https://pp.dcd.one/clash/proxies?speed=15,30&type=hysteria2,hysteria,vless,vmess,trojan"
subscribeUrl_net="https://pub-api-1.bianyuan.xyz/sub?target=clash&url=https%3A%2F%2Fsub.0664.net%2Fclash%2Fproxies%3Fspeed%3D10%26nc%3DCN%26type%3Dvmess%2Ctrojan%7Chttps%3A%2F%2Fpp.dcd.one%2Fclash%2Fproxies%3Fspeed%3D10%26nc%3DCN%26type%3Dhysteria2%2Chysteria%2Cvless%2Cvmess%2Ctrojan%7Chttps%3A%2F%2Fraw.kkgithub.com%2Ffree18%2Fv2ray%2Frefs%2Fheads%2Fmain%2Fv.txt%7Chttps%3A%2F%2Fraw.kkgithub.com%2Fchengaopan%2FAutoMergePublicNodes%2Frefs%2Fheads%2Fmaster%2Flist.meta.yml&insert=false&config=https%3A%2F%2Fraw.githubusercontent.com%2F9bingyin%2Froutes-info%2Frefs%2Fheads%2Fmain%2Fprofile_min.ini&filename=sub0664.yaml&emoji=true&list=true&scv=true&fdn=true&expand=true&sort=true&new_name=true"
subscribeUrl_hy="https://pp.dcd.one/clash/proxies?speed=15,30&type=hysteria2,hysteria"
subscribeUrl_me="https://pp.dcd.one/clash/proxies?speed=15,30&type=hysteria2,hysteria,vless,vmess,trojan"
subscribeUrl_me_bak="https://pp.dcd.one/clash/proxies?speed=15,30&type=hysteria2,hysteria,vless,vmess,trojan&stream=netflix,disney"

echo "start getting the subscribe"
wget $subscribeUrl -O ./subscribe.txt
sed -i '/"name":"NULL"/d' ./subscribe.txt
sed -i '/"server":"NULL"/d' ./subscribe.txt

echo "------------------- subscribe from net -------------------"

wget $subscribeUrl_hy -O ./subscribe_net.txt
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
