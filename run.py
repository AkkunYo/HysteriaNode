#!/usr/bin/env python3
import sys
import re
import json
import base64
import urllib.request
import urllib.parse
import concurrent.futures
import yaml
from pathlib import Path

# Sources listed in run.sh
SOURCES = [
    "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml",
    "https://cdn.jsdelivr.net/gh/vxiaov/free_proxies@main/clash/clash.provider.yaml",
    "https://freenode.openrunner.net/uploads/20240807-clash.yaml",
    "https://raw.githubusercontent.com/Misaka-blog/chromego_merge/main/sub/merged_proxies_new.yaml",
    "https://raw.githubusercontent.com/NiceVPN123/NiceVPN/main/Clash.yaml",
    "https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml",
    "https://raw.githubusercontent.com/ermaozi01/free_clash_vpn/main/subscribe/clash.yml",
    "https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.yml",
    "https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml",
    "https://raw.githubusercontent.com/ronghuaxueleng/get_v2/main/pub/combine.yaml",
    "https://raw.githubusercontent.com/ts-sf/fly/main/clash",
    "https://raw.githubusercontent.com/yaney01/Yaney01/main/temporary",
    "https://raw.githubusercontent.com/zhangkaiitugithub/passcro/main/speednodes.yaml",
    "https://tt.vg/freeclash",
    "https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/v.txt",
    "https://raw.githubusercontent.com/Pawdroid/Free-servers/main/sub",
    "https://raw.githubusercontent.com/snakem982/proxypool/main/source/v2ray-2.txt",
    "https://raw.githubusercontent.com/chengaopan/AutoMergePublicNodes/master/list.txt",
    "https://raw.githubusercontent.com/tglaoshiji/nodeshare/main/2026/v2ray.txt",
    "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/v2ray-base64.txt"
]

def log(msg):
    print(f"[*] {msg}")

def download_url(url, timeout=15, retries=2):
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return res.read()
        except Exception as e:
            if i == retries:
                log(f"Failed to download {url}: {e}")
            else:
                log(f"Retry download {url} ({i+1}/{retries})...")
    return b""

def safe_b64decode(s):
    # Strip spaces and remove non-base64 chars
    s = re.sub(r'[^a-zA-Z0-9+/=]', '', s.strip())
    # Add padding
    missing_padding = len(s) % 4
    if missing_padding:
        s += '=' * (4 - missing_padding)
    try:
        return base64.b64decode(s)
    except Exception:
        return b""

def parse_vmess(link):
    # vmess://<base64_json>
    try:
        payload = link[8:]
        decoded = safe_b64decode(payload).decode('utf-8', errors='ignore')
        data = json.loads(decoded)
        # Convert to Clash dict
        proxy = {
            "name": data.get("ps", "VMess"),
            "type": "vmess",
            "server": data.get("add"),
            "port": int(data.get("port", 443)),
            "uuid": data.get("id"),
            "alterId": int(data.get("aid", 0)),
            "cipher": data.get("scy", "auto"),
            "udp": True
        }
        if data.get("net"):
            proxy["network"] = data.get("net")
            if data.get("net") == "ws" and data.get("path"):
                proxy["ws-opts"] = {"path": data.get("path")}
                if data.get("host"):
                    proxy["ws-opts"]["headers"] = {"Host": data.get("host")}
        if data.get("tls") == "tls":
            proxy["tls"] = True
            if data.get("sni"):
                proxy["sni"] = data.get("sni")
        return proxy
    except Exception:
        return None

def parse_vless(link):
    # vless://uuid@server:port?query#name
    try:
        parsed = urllib.parse.urlparse(link)
        netloc = parsed.netloc
        if "@" not in netloc:
            return None
        uuid, server_port = netloc.split("@", 1)
        if ":" not in server_port:
            return None
        server, port = server_port.split(":", 1)

        query = urllib.parse.parse_qs(parsed.query)
        name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else "VLESS"

        proxy = {
            "name": name,
            "type": "vless",
            "server": server,
            "port": int(port),
            "uuid": uuid,
            "udp": True
        }

        # Parse queries
        if "tls" in query or "security" in query:
            sec = query.get("security", query.get("tls", [""]))[0]
            if sec in ("tls", "xtls"):
                proxy["tls"] = True
        if "sni" in query:
            proxy["sni"] = query["sni"][0]
        if "flow" in query:
            proxy["flow"] = query["flow"][0]
        if "network" in query or "type" in query:
            net = query.get("network", query.get("type", [""]))[0]
            proxy["network"] = net
            if net == "ws" and "path" in query:
                proxy["ws-opts"] = {"path": query["path"][0]}
                if "host" in query:
                    proxy["ws-opts"]["headers"] = {"Host": query["host"][0]}
            elif net == "grpc" and "serviceName" in query:
                proxy["grpc-opts"] = {"grpc-service-name": query["serviceName"][0]}
        return proxy
    except Exception:
        return None

def parse_trojan(link):
    # trojan://password@server:port?query#name
    try:
        parsed = urllib.parse.urlparse(link)
        netloc = parsed.netloc
        if "@" not in netloc:
            return None
        password, server_port = netloc.split("@", 1)
        if ":" not in server_port:
            return None
        server, port = server_port.split(":", 1)

        query = urllib.parse.parse_qs(parsed.query)
        name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else "Trojan"

        proxy = {
            "name": name,
            "type": "trojan",
            "server": server,
            "port": int(port),
            "password": password,
            "udp": True
        }
        if "sni" in query:
            proxy["sni"] = query["sni"][0]
        return proxy
    except Exception:
        return None

def parse_hysteria2(link):
    # hysteria2://auth@server:port?query#name
    # hy2://auth@server:port?query#name
    try:
        parsed = urllib.parse.urlparse(link)
        netloc = parsed.netloc
        if "@" not in netloc:
            return None
        auth, server_port = netloc.split("@", 1)
        if ":" not in server_port:
            return None
        server, port = server_port.split(":", 1)

        query = urllib.parse.parse_qs(parsed.query)
        name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else "Hysteria2"

        proxy = {
            "name": name,
            "type": "hysteria2",
            "server": server,
            "port": int(port),
            "password": auth,
            "udp": True
        }
        if "insecure" in query:
            proxy["skip-cert-verify"] = query["insecure"][0] in ("1", "true")
        if "sni" in query:
            proxy["sni"] = query["sni"][0]
        if "obfs" in query:
            proxy["obfs"] = query["obfs"][0]
            if "obfs-password" in query:
                proxy["obfs-password"] = query["obfs-password"][0]
        return proxy
    except Exception:
        return None

def parse_tuic(link):
    # tuic://uuid:password@server:port?query#name
    try:
        parsed = urllib.parse.urlparse(link)
        netloc = parsed.netloc
        if "@" not in netloc:
            return None
        auth, server_port = netloc.split("@", 1)
        if ":" not in server_port:
            return None
        server, port = server_port.split(":", 1)

        uuid = auth
        password = ""
        if ":" in auth:
            uuid, password = auth.split(":", 1)

        query = urllib.parse.parse_qs(parsed.query)
        name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else "TUIC"

        proxy = {
            "name": name,
            "type": "tuic",
            "server": server,
            "port": int(port),
            "uuid": uuid,
            "password": password,
            "udp": True
        }
        if "sni" in query:
            proxy["sni"] = query["sni"][0]
        if "alpn" in query:
            proxy["alpn"] = query["alpn"][0].split(",")
        return proxy
    except Exception:
        return None

def parse_ss(link):
    # ss://method:password@server:port#name
    # ss://base64_encoded_method_password@server:port#name
    try:
        parsed = urllib.parse.urlparse(link)
        netloc = parsed.netloc
        name = urllib.parse.unquote(parsed.fragment) if parsed.fragment else "SS"

        if "@" in netloc:
            auth_part, server_port = netloc.split("@", 1)
            if ":" not in server_port:
                return None
            server, port = server_port.split(":", 1)

            if ":" in auth_part:
                method, password = auth_part.split(":", 1)
            else:
                decoded_auth = safe_b64decode(auth_part).decode('utf-8', errors='ignore')
                if ":" in decoded_auth:
                    method, password = decoded_auth.split(":", 1)
                else:
                    return None
        else:
            # Maybe the whole netloc except port is base64 encoded
            if ":" in netloc:
                parts = netloc.split(":", 1)
                try:
                    int(parts[1])
                    auth_part = parts[0]
                    decoded_auth = safe_b64decode(auth_part).decode('utf-8', errors='ignore')
                    if "@" in decoded_auth:
                        auth_info, server_info = decoded_auth.split("@", 1)
                        if ":" in auth_info and ":" in server_info:
                            method, password = auth_info.split(":", 1)
                            server, port = server_info.split(":", 1)
                        else:
                            return None
                    else:
                        return None
                except ValueError:
                    decoded_netloc = safe_b64decode(netloc).decode('utf-8', errors='ignore')
                    if "@" in decoded_netloc:
                        auth_part, server_port = decoded_netloc.split("@", 1)
                        if ":" in auth_part and ":" in server_port:
                            method, password = auth_part.split(":", 1)
                            server, port = server_port.split(":", 1)
                        else:
                            return None
                    else:
                        return None
            else:
                decoded_netloc = safe_b64decode(netloc).decode('utf-8', errors='ignore')
                if "@" in decoded_netloc:
                    auth_part, server_port = decoded_netloc.split("@", 1)
                    if ":" in auth_part and ":" in server_port:
                        method, password = auth_part.split(":", 1)
                        server, port = server_port.split(":", 1)
                    else:
                        return None
                else:
                    return None

        return {
            "name": name,
            "type": "ss",
            "server": server,
            "port": int(port),
            "cipher": method,
            "password": password,
            "udp": True
        }
    except Exception:
        return None

def parse_link(link):
    link = link.strip()
    if not link:
        return None
    if link.startswith("vmess://"):
        return parse_vmess(link)
    elif link.startswith("vless://"):
        return parse_vless(link)
    elif link.startswith("trojan://"):
        return parse_trojan(link)
    elif link.startswith("hysteria2://") or link.startswith("hy2://"):
        return parse_hysteria2(link)
    elif link.startswith("tuic://"):
        return parse_tuic(link)
    elif link.startswith("ss://"):
        return parse_ss(link)
    return None

def to_link(proxy):
    p_type = proxy.get("type")
    server = proxy.get("server")
    port = proxy.get("port")
    name = urllib.parse.quote(proxy.get("name", ""))

    if p_type == "vmess":
        data = {
            "v": "2",
            "ps": proxy.get("name"),
            "add": server,
            "port": port,
            "id": proxy.get("uuid"),
            "aid": proxy.get("alterId", 0),
            "scy": proxy.get("cipher", "auto"),
            "net": proxy.get("network", "tcp"),
            "type": "none",
            "host": "",
            "path": "",
            "tls": "tls" if proxy.get("tls") else ""
        }
        if proxy.get("network") == "ws" and "ws-opts" in proxy:
            ws_opts = proxy["ws-opts"]
            if "path" in ws_opts:
                data["path"] = ws_opts["path"]
            if "headers" in ws_opts and "Host" in ws_opts["headers"]:
                data["host"] = ws_opts["headers"]["Host"]
        js = json.dumps(data)
        b64 = base64.b64encode(js.encode('utf-8')).decode('utf-8')
        return f"vmess://{b64}"

    elif p_type == "vless":
        uuid = proxy.get("uuid")
        flow = proxy.get("flow", "")
        sni = proxy.get("sni", "")
        net = proxy.get("network", "tcp")

        q = {}
        if proxy.get("tls"):
            q["security"] = "tls"
        if flow:
            q["flow"] = flow
        if sni:
            q["sni"] = sni
        if net:
            q["type"] = net
            if net == "ws" and "ws-opts" in proxy:
                ws_opts = proxy["ws-opts"]
                if "path" in ws_opts:
                    q["path"] = ws_opts["path"]
                if "headers" in ws_opts and "Host" in ws_opts["headers"]:
                    q["host"] = ws_opts["headers"]["Host"]
            elif net == "grpc" and "grpc-opts" in proxy:
                grpc_opts = proxy["grpc-opts"]
                if "grpc-service-name" in grpc_opts:
                    q["serviceName"] = grpc_opts["grpc-service-name"]

        q_str = urllib.parse.urlencode(q)
        return f"vless://{uuid}@{server}:{port}?{q_str}#{name}"

    elif p_type == "trojan":
        password = proxy.get("password")
        sni = proxy.get("sni", "")
        q = {}
        if sni:
            q["sni"] = sni
        q_str = urllib.parse.urlencode(q)
        suffix = f"?{q_str}" if q_str else ""
        return f"trojan://{password}@{server}:{port}{suffix}#{name}"

    elif p_type == "hysteria2" or p_type == "hy2":
        password = proxy.get("password")
        sni = proxy.get("sni", "")
        obfs = proxy.get("obfs", "")
        obfs_pwd = proxy.get("obfs-password", "")
        skip_cert = proxy.get("skip-cert-verify")

        q = {}
        if skip_cert:
            q["insecure"] = "1"
        if sni:
            q["sni"] = sni
        if obfs:
            q["obfs"] = obfs
            if obfs_pwd:
                q["obfs-password"] = obfs_pwd
        q_str = urllib.parse.urlencode(q)
        suffix = f"?{q_str}" if q_str else ""
        return f"hysteria2://{password}@{server}:{port}{suffix}#{name}"

    elif p_type == "tuic":
        uuid = proxy.get("uuid")
        password = proxy.get("password", "")
        sni = proxy.get("sni", "")
        alpn = proxy.get("alpn", [])

        q = {}
        if sni:
            q["sni"] = sni
        if alpn:
            q["alpn"] = ",".join(alpn)
        q_str = urllib.parse.urlencode(q)
        suffix = f"?{q_str}" if q_str else ""
        auth = f"{uuid}:{password}" if password else uuid
        return f"tuic://{auth}@{server}:{port}{suffix}#{name}"

    elif p_type == "ss":
        cipher = proxy.get("cipher")
        password = proxy.get("password")
        auth = f"{cipher}:{password}"
        b64_auth = base64.b64encode(auth.encode('utf-8')).decode('utf-8')
        return f"ss://{b64_auth}@{server}:{port}#{name}"

    return None

def parse_content(content_bytes):
    proxies = []
    content_str = content_bytes.decode('utf-8', errors='ignore')

    # Try as YAML (Clash style)
    try:
        if "proxies:" in content_str:
            data = yaml.safe_load(content_str)
            if isinstance(data, dict) and "proxies" in data:
                for item in data["proxies"]:
                    if isinstance(item, dict) and "type" in item and "server" in item:
                        # 过滤 http, ss, socks 类型节点
                        if item.get("type") in ("http", "ss", "socks", "socks5"):
                            continue
                        item["udp"] = True
                        proxies.append(item)
                if proxies:
                    return proxies
    except Exception:
        pass

    # Try base64 decoding (many subscribe feeds are base64 encoded txt)
    try:
        decoded = safe_b64decode(content_str).decode('utf-8', errors='ignore')
        if decoded.strip():
            lines = [l.strip() for l in decoded.splitlines() if l.strip()]
            for line in lines:
                p = parse_link(line)
                if p and p.get("type") not in ("http", "ss", "socks", "socks5"):
                    proxies.append(p)
            if proxies:
                return proxies
    except Exception:
        pass

    # Try parsing line by line directly (plain text list of links)
    try:
        lines = [l.strip() for l in content_str.splitlines() if l.strip()]
        for line in lines:
            p = parse_link(line)
            if p and p.get("type") not in ("http", "ss", "socks", "socks5"):
                proxies.append(p)
    except Exception:
        pass

    return proxies

def validate_proxy(proxy):
    """验证节点必需字段"""
    p_type = proxy.get("type")
    if not p_type:
        return False

    # 验证通用字段
    server = proxy.get("server", "").strip()
    port = proxy.get("port")

    # 确保 port 是整数
    try:
        port = int(port) if port else 0
    except (ValueError, TypeError):
        return False

    if not server or port <= 0 or port > 65535:
        return False

    # 验证协议特定字段
    if p_type == "vmess":
        if not proxy.get("uuid"):
            return False
    elif p_type == "vless":
        if not proxy.get("uuid"):
            return False
    elif p_type == "trojan":
        if not proxy.get("password"):
            return False
    elif p_type in ("hysteria2", "hy2"):
        if not proxy.get("password"):
            return False
    elif p_type == "tuic":
        if not proxy.get("uuid"):
            return False

    return True

def deduplicate_proxies(proxies):
    seen = set()
    deduped = []
    for p in proxies:
        p_type = p.get("type")
        server = p.get("server")
        port = p.get("port")

        cred = ""
        if p_type == "vmess":
            cred = p.get("uuid", "")
        elif p_type in ("vless", "tuic"):
            cred = p.get("uuid", "")
        elif p_type in ("trojan", "hysteria2", "hy2"):
            cred = p.get("password", "")
        elif p_type == "ss":
            cred = f"{p.get('cipher','')}:{p.get('password','')}"

        key = (p_type, server, port, cred)
        if key not in seen and server and port:
            seen.add(key)
            deduped.append(p)
    return deduped

def main():
    log("Starting local subscription aggregator...")
    all_proxies = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_url, url): url for url in SOURCES}
        for future in concurrent.futures.as_completed(futures):
            url = futures[future]
            try:
                data = future.result()
                if data:
                    proxies = parse_content(data)
                    log(f"Fetched {url}: found {len(proxies)} nodes")
                    all_proxies.extend(proxies)
                else:
                    log(f"Fetched {url}: empty or failed")
            except Exception as e:
                log(f"Error fetching/parsing {url}: {e}")

    log(f"Total nodes before deduplication: {len(all_proxies)}")
    deduped = deduplicate_proxies(all_proxies)
    log(f"Total nodes after deduplication: {len(deduped)}")

    # 验证节点有效性
    valid_proxies = [p for p in deduped if validate_proxy(p)]
    log(f"Valid nodes after validation: {len(valid_proxies)}")

    if not valid_proxies:
        log("No valid nodes found! Exiting.")
        sys.exit(1)

    # Write share links to subscribe.txt
    lines = []
    for p in valid_proxies:
        link = to_link(p)
        if link:
            lines.append(link)

    Path('./subscribe.txt').write_text("\n".join(lines) + "\n")
    log(f"Generated subscribe.txt with {len(lines)} nodes")

    # Extract Hysteria2 links
    hy2_links = [l for l in lines if l.startswith("hysteria2://")]
    Path('./hysteriaNode.txt').write_text("\n".join(hy2_links) + "\n")
    log(f"Generated hysteriaNode.txt with {len(hy2_links)} hysteria2 nodes")

    # Classify nodes into type/
    type_dir = Path('./type')
    type_dir.mkdir(exist_ok=True)
    # Clear existing
    for f in type_dir.glob("*.txt"):
        f.unlink()

    for proto in ["vmess", "vless", "trojan", "tuic"]:
        proto_proxies = [p for p in valid_proxies if p.get("type") == proto or (proto == "hysteria2" and p.get("type") == "hy2")]
        proto_links = [to_link(p) for p in proto_proxies]
        proto_links = [l for l in proto_links if l]
        if proto_links:
            (type_dir / f"{proto}.txt").write_text("\n".join(proto_links) + "\n")
            log(f"Generated type/{proto}.txt with {len(proto_links)} nodes")

    # Prepare yaml directory
    yaml_dir = Path('./yaml')
    yaml_dir.mkdir(exist_ok=True)

    # Filter proxies for clash configuration (no vmess or ss)
    clash_proxies = [p for p in valid_proxies if p.get("type") not in ("vmess", "ss")]

    # Build clash.yaml
    template_path = Path('./template/clash_template.yaml')
    if template_path.exists():
        template_str = template_path.read_text()

        direct_node = {
            "name": "🟢 直连",
            "type": "direct",
            "udp": True
        }

        yaml_proxies = [direct_node] + clash_proxies
        # Ensure all names are unique for Clash
        names_seen = {}
        for p in yaml_proxies:
            name = p.get("name", "Proxy")
            if name in names_seen:
                names_seen[name] += 1
                p["name"] = f"{name} {names_seen[name]}"
            else:
                names_seen[name] = 1

        proxies_yaml_part = yaml.dump({"proxies": yaml_proxies}, allow_unicode=True, sort_keys=False)
        if proxies_yaml_part.startswith("proxies:\n"):
            proxies_yaml_part = proxies_yaml_part[9:]

        result_clash = re.sub(r'^proxies:.*?(?=^proxy-groups:)', "proxies:\n" + proxies_yaml_part, template_str, flags=re.MULTILINE | re.DOTALL)

        # 验证生成的 YAML
        try:
            yaml.safe_load(result_clash)
            (yaml_dir / 'clash.yaml').write_text(result_clash)
            log(f"Generated yaml/clash.yaml with {len(clash_proxies)} proxies")
        except yaml.YAMLError as e:
            log(f"⚠ Generated clash.yaml failed YAML validation: {e}")
            log("Skipping clash.yaml generation")
    else:
        log("⚠ Template file not found: ./template/clash_template.yaml")

if __name__ == "__main__":
    main()
