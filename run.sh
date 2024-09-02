#!/bin/bash

# ================================
SUBLINK_BASE_URL="https://app.sublink.works"

# GitHub 订阅源配置
sources=(
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt"
    "https://cdn.jsdelivr.net/gh/vxiaov/free_proxies@main/clash/clash.provider.yaml"
    "https://freenode.openrunner.net/uploads/20240807-clash.yaml"
    "https://raw.githubusercontent.com/Misaka-blog/chromego_merge/main/sub/merged_proxies_new.yaml"
    "https://raw.githubusercontent.com/NiceVPN123/NiceVPN/main/Clash.yaml"
    "https://raw.githubusercontent.com/anaer/Sub/main/clash.yaml"
    "https://raw.githubusercontent.com/chengaopan/AutoMergePublicNodes/master/list.yml"
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml"
    "https://raw.githubusercontent.com/ermaozi01/free_clash_vpn/main/subscribe/clash.yml"
    "https://raw.githubusercontent.com/lagzian/SS-Collector/main/mix_clash.yaml"
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.yml"
    "https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml"
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml"
    "https://raw.githubusercontent.com/ronghuaxueleng/get_v2/main/pub/combine.yaml"
    "https://raw.githubusercontent.com/ts-sf/fly/main/clash"
    "https://raw.githubusercontent.com/yaney01/Yaney01/main/temporary"
    "https://raw.githubusercontent.com/zhangkaiitugithub/passcro/main/speednodes.yaml"
    "https://tt.vg/freeclash"
    "https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/v.txt"
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub"
    "https://raw.githubusercontent.com/snakem982/proxypool/main/source/v2ray-2.txt"
    "https://raw.githubusercontent.com/chengaopan/AutoMergePublicNodes/master/list.txt"
    "https://raw.githubusercontent.com/tglaoshiji/nodeshare/main/2026/v2ray.txt"
    "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/v2ray-base64.txt"
)

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

# ==================== 2. 使用远端 sublink 服务 ====================
if ! curl -sf -m 15 -o /dev/null "$SUBLINK_BASE_URL"; then
    log "✗ Remote sublink service unavailable"
    exit 1
fi

log "✓ Using remote sublink service"

# ==================== 3. 聚合并转换订阅源 ====================
log "Aggregating sources..."

# 拼接所有源（用 %0A 分隔，URL 编码的换行）
url_list=""
for url in "${sources[@]}"; do
    if [ -z "$url_list" ]; then
        url_list="$url"
    else
        url_list="${url_list}%0A${url}"
    fi
done

# ==================== 4. 使用 sublink-worker 转换 ====================

fetch_with_retry() {
    local url="$1" out="$2" label="$3"
    local attempt=0 max=3 wait=30
    while [ $attempt -lt $max ]; do
        curl -sL -m 180 "$url" -o "$out"
        local first
        first=$(head -c 20 "$out" 2>/dev/null || echo "")
        if [ -s "$out" ] && ! echo "$first" | grep -q 'error code'; then
            return 0
        fi
        attempt=$((attempt + 1))
        if [ $attempt -lt $max ]; then
            log "⚠ $label failed (attempt $attempt), retry in ${wait}s..."
            sleep $wait
            wait=$((wait * 2))
        fi
    done
    return 1
}

log "Generating mixed subscribe and clash YAML..."

# sublink-worker 用 config 参数传订阅源
mixed_url="$SUBLINK_BASE_URL/xray?config=${url_list}"
clash_conv_url="$SUBLINK_BASE_URL/clash?config=${url_list}"

fetch_with_retry "$mixed_url" ./subscribe.raw "xray subscribe"
sleep 15
fetch_with_retry "$clash_conv_url" ./clash.full.yaml "clash YAML"

if [ -s ./subscribe.raw ]; then
    if python3 - <<'PY'
from base64 import b64decode
from pathlib import Path
source = Path('./subscribe.raw').read_text().strip()
try:
    decoded = b64decode(source, validate=True).decode('utf-8')
except Exception:
    decoded = source
Path('./subscribe.txt').write_text(decoded if decoded.endswith('\n') else decoded + '\n')
PY
    then
        rm -f ./subscribe.raw
        if [ -s ./subscribe.txt ] && ! grep -Eq '^(error code:|<!DOCTYPE|<html)' ./subscribe.txt; then
            # 过滤错误行，只保留合法协议链接
            grep -E '^(vmess|vless|trojan|hysteria|hysteria2|tuic|hy2)://' ./subscribe.txt > ./subscribe.tmp || true
            if [ -s ./subscribe.tmp ]; then
                mv ./subscribe.tmp ./subscribe.txt
                log "✓ Generated subscribe.txt"
            else
                log "✗ No valid nodes in subscribe.txt"
                rm -f ./subscribe.tmp
                exit 1
            fi
        else
            log "✗ Failed to generate subscribe.txt"
            exit 1
        fi
    else
        log "✗ Failed to decode subscribe.txt"
        exit 1
    fi
else
    log "✗ Failed to generate subscribe.txt"
    exit 1
fi

log "Generating clash.txt from subscribe.txt..."
mkdir -p ./yaml
grep -Ev '^(vmess|ss)://' ./subscribe.txt > ./yaml/clash.txt || true

if [ -s ./yaml/clash.txt ]; then
    clash_count=$(wc -l < ./yaml/clash.txt)
    log "✓ Generated yaml/clash.txt ($clash_count nodes)"
else
    log "✗ No non-vmess/ss nodes found"
    exit 1
fi

log "Extracting Hysteria2 links from subscribe.txt..."
grep -E '^hysteria2://[^[:space:]]+' ./subscribe.txt | awk '!seen[$0]++' > ./hysteriaNode.txt || true

hy2_count=$(grep -c '^hysteria2://' ./hysteriaNode.txt 2>/dev/null || true)
hy2_count=${hy2_count:-0}
log "✓ Hysteria2 nodes: $hy2_count"

log "Classifying nodes into type/..."
mkdir -p ./type
for proto in vmess vless trojan hysteria2 hy2 tuic; do
    out="./type/${proto}.txt"
    grep -E "^${proto}://" ./subscribe.txt > "$out" || true
    if [ -s "$out" ]; then
        count=$(wc -l < "$out")
        log "✓ type/${proto}.txt ($count nodes)"
    else
        rm -f "$out"
    fi
done

log "Generating clash.yaml from template + clash conversion..."
if [ -s ./clash.full.yaml ] && ! grep -Eq '^(error code:|<!DOCTYPE|<html)' ./clash.full.yaml; then
    python3 - <<'PY'
from pathlib import Path
import re

full = Path('./clash.full.yaml').read_text()

m = re.search(r'^proxies:\n(.*?)(?=^\S)', full, re.MULTILINE | re.DOTALL)
if not m:
    exit(1)

entries_raw = m.group(1)
nodes = re.split(r'(?=^  - name:)', entries_raw, flags=re.MULTILINE)
nodes = [n for n in nodes if n.strip()]

# 过滤 vmess 和 ss
filtered = [n for n in nodes if not re.search(r'^\s+type:\s+(vmess|ss)\b', n, re.MULTILINE)]
if not filtered:
    exit(1)

proxies_yaml = 'proxies:\n  - name: "🟢 直连"\n    type: direct\n    udp: true\n' + ''.join(filtered)

template = Path('./template/clash_template.yaml').read_text()
result = re.sub(r'^proxies:.*?(?=^\S)', proxies_yaml + '\n', template, flags=re.MULTILINE | re.DOTALL)
Path('./yaml/clash.yaml').write_text(result)
PY
    if [ -s ./yaml/clash.yaml ]; then
        yaml_count=$(grep -c '^  - name:' ./yaml/clash.yaml || true)
        log "✓ Generated yaml/clash.yaml ($yaml_count nodes)"
    else
        log "✗ Failed to generate clash.yaml"
        exit 1
    fi
else
    log "✗ Failed to fetch clash conversion"
    exit 1
fi

log "Generating mihomo configs from templates..."
if [ -s ./clash.full.yaml ] && ! grep -Eq '^(error code:|<!DOCTYPE|<html)' ./clash.full.yaml; then
    python3 - <<'PY'
from pathlib import Path
import re

full = Path('./clash.full.yaml').read_text()

m = re.search(r'^proxies:\n(.*?)(?=^\S)', full, re.MULTILINE | re.DOTALL)
if not m:
    exit(1)

entries_raw = m.group(1)
nodes = re.split(r'(?=^  - name:)', entries_raw, flags=re.MULTILINE)
nodes = [n for n in nodes if n.strip()]

# 过滤 vmess 和 ss
filtered = [n for n in nodes if not re.search(r'^\s+type:\s+(vmess|ss)\b', n, re.MULTILINE)]
if not filtered:
    exit(1)

proxies_yaml = 'proxies:\n  - name: "🟢 直连"\n    type: direct\n    udp: true\n' + ''.join(filtered)

# 生成 AX3000T 配置
template_ax3000t = Path('./template/mihomo_template_ax3000t.yaml').read_text()
result_ax3000t = re.sub(r'^proxies:.*?(?=^proxy-groups:)', proxies_yaml + '\n', template_ax3000t, flags=re.MULTILINE | re.DOTALL)
Path('./yaml/mihomo_ax3000t.yaml').write_text(result_ax3000t)

# 生成 AX6000 配置
template_ax6000 = Path('./template/mihomo_template_ax6000.yaml').read_text()
result_ax6000 = re.sub(r'^proxies:.*?(?=^proxy-groups:)', proxies_yaml + '\n', template_ax6000, flags=re.MULTILINE | re.DOTALL)
Path('./yaml/mihomo_ax6000.yaml').write_text(result_ax6000)
PY
    if [ -s ./yaml/mihomo_ax3000t.yaml ] && [ -s ./yaml/mihomo_ax6000.yaml ]; then
        ax3000t_count=$(grep -c '^  - name:' ./yaml/mihomo_ax3000t.yaml || true)
        ax6000_count=$(grep -c '^  - name:' ./yaml/mihomo_ax6000.yaml || true)
        log "✓ Generated yaml/mihomo_ax3000t.yaml ($ax3000t_count nodes)"
        log "✓ Generated yaml/mihomo_ax6000.yaml ($ax6000_count nodes)"
    else
        log "✗ Failed to generate mihomo configs"
        exit 1
    fi
else
    log "✗ clash.full.yaml unavailable for mihomo generation"
    exit 1
fi

# 清理临时文件
rm -f ./clash.full.yaml

log "✓ Output files ready"

echo "getting the subscribe succeed, enjoy it~"
