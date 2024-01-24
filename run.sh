subscribeUrl="https://pp.dcd.one/clash/proxies?speed=10"


echo "start getting the subscribe"
wget $subscribeUrl -O ./hysteria2NodeTmp.txt

echo "------------------- hysteria2 -------------------"
echo "proxies:" > ./hysteria2Node.txt
sed -n '/type":"hysteria2/p' ./hysteria2NodeTmp.txt >> ./hysteria2Node.txt

echo "------------------- vmess -------------------"
echo "proxies:" > ./vmessNode.txt
sed -n '/type":"vmess/p' ./hysteria2NodeTmp.txt >> ./vmessNode.txt

rm -rf ./hysteria2NodeTmp.txt
echo "getting the subscribe succeed,enjoy it~"
