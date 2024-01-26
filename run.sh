#!/bin/bash

subscribeUrl="https://pp.dcd.one/clash/proxies?speed=10"

echo "start getting the subscribe"
wget $subscribeUrl -O ./subscribeTmp.txt
echo "proxies:" > ./allNodes.txt

# 读取文本文件
while IFS= read -r line
do
  # 将IP地址提取出来
  ip=$(echo "$line" | awk -F '"' '{print $8}')

  # 检查IP地址是否已经存在于去重列表中
  if [[ ! " ${unique_ips[@]} " =~ " $ip " ]]; then
    # 如果不在列表中，则添加到去重列表中
    unique_ips+=("$ip")
    echo "$line" >> ./allNodes.txt
  fi
done < "./subscribeTmp.txt"
totalNodeSize=$(grep -c '"type":' "./subscribeTmp.txt")
leaveNodeSize=$(grep -c '"type":' "./allNodes.txt")
echo "totalNodeSize:$totalNodeSize,remove duplicates leaveNodeSize:$leaveNodeSize"
rm -rf ./subscribe*.txt
mv ./allNodes.txt ./subscribe.txt

echo "------------------- hysteria2 -------------------"
echo "proxies:" > ./hysteriaNode.txt
sed -n '/type":"hysteria/p' ./subscribe.txt >> ./hysteriaNode.txt
hysteria2NodeSize=$(grep -c '"type":' "./hysteriaNode.txt")
echo "hysteria2NodeSize:$hysteria2NodeSize"

echo "getting the subscribe succeed,enjoy it~"
