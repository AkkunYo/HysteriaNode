#!/usr/bin/env python3
import os
import sys
import re
import json
import math
import base64
import asyncio
import subprocess
import shutil
import tempfile
import urllib.request
import urllib.error
import urllib.parse
import concurrent.futures
import yaml
import socket
import ipaddress
import datetime
from pathlib import Path

try:
    import maxminddb
except ImportError:
    maxminddb = None

# Default Sources (fallback if environment variable is not provided)
DEFAULT_SOURCES = []
SUPPORTED_PROTOCOLS = {"vmess", "vless", "trojan", "hysteria2", "hy2", "tuic"}


class HealthCheckError(RuntimeError):
    """Raised when node health verification cannot establish a safe result."""


def _redacted_source(url):
    """Return a source label that never includes credentials or URL parameters."""
    try:
        parsed = urllib.parse.urlsplit(str(url))
        host = parsed.hostname or "unknown-host"
        return f"{parsed.scheme or 'source'}://{host}"
    except Exception:
        return "source"


def _source_label(url, index=None):
    prefix = f"source #{index}" if index is not None else "source"
    return f"{prefix} ({_redacted_source(url)})"

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
                log(f"Failed to download {_source_label(url)} ({type(e).__name__})")
            else:
                log(f"Retry download {_source_label(url)} ({i+1}/{retries})...")
    return b""

def load_sources():
    # Load sources from secret environment variable if available to prevent URL leaks
    secret_env = os.environ.get("SOURCES_SECRET") or os.environ.get("SUBSCRIBE_SOURCES")
    if secret_env:
        secret_url = secret_env.strip()
        if secret_url.startswith("http"):
            try:
                raw = download_url(secret_url, timeout=15)
                if raw:
                    text = raw.decode('utf-8', errors='replace')
                    urls = [line.strip() for line in text.splitlines() if line.strip().startswith("http")]
                    if urls:
                        log(f"Successfully loaded {len(urls)} subscription sources from secret config")
                        return urls
            except Exception as e:
                log(f"Failed to fetch sources from secret URL ({type(e).__name__})")
        else:
            urls = [u.strip() for u in re.split(r'[\r\n,]+', secret_env) if u.strip().startswith("http")]
            if urls:
                return urls
    return DEFAULT_SOURCES

SOURCES = load_sources()

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
        uuid = urllib.parse.unquote(uuid)
        if ":" not in server_port:
            return None
        server, port = server_port.split(":", 1)

        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
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
            if sec in ("tls", "xtls", "reality"):
                proxy["tls"] = True
            if sec == "reality":
                reality_opts = {}
                if "pbk" in query and query["pbk"][0]:
                    reality_opts["public-key"] = query["pbk"][0]
                if "sid" in query:
                    reality_opts["short-id"] = query["sid"][0]
                if not reality_opts.get("public-key"):
                    return None
                proxy["reality-opts"] = reality_opts
        if "fp" in query:
            proxy["client-fingerprint"] = query["fp"][0]
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
            "password": urllib.parse.unquote(password),
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
            "password": urllib.parse.unquote(auth),
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
        uuid = urllib.parse.unquote(uuid)
        password = urllib.parse.unquote(password)

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

def _optional_mapping(value):
    """YAML null is valid for optional options; other non-mapping values are not."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Protocol options must be a mapping or null")
    return value

def to_link(proxy):
    p_type = proxy.get("type")
    server = proxy.get("server")
    port = proxy.get("port")
    name = urllib.parse.quote(proxy.get("name", ""), safe="")

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
        if proxy.get("network") == "ws":
            ws_opts = _optional_mapping(proxy.get("ws-opts"))
            if "path" in ws_opts:
                data["path"] = ws_opts["path"]
            headers = _optional_mapping(ws_opts.get("headers"))
            if "Host" in headers:
                data["host"] = headers["Host"]
        js = json.dumps(data)
        b64 = base64.b64encode(js.encode('utf-8')).decode('utf-8')
        return f"vmess://{b64}"

    elif p_type == "vless":
        uuid = proxy.get("uuid")
        flow = proxy.get("flow", "")
        sni = proxy.get("sni") or proxy.get("servername", "")
        net = proxy.get("network", "tcp")

        q = {}
        reality = _optional_mapping(proxy.get("reality-opts"))
        if reality:
            q["security"] = "reality"
            q["pbk"] = reality["public-key"]
            if "short-id" in reality:
                q["sid"] = reality["short-id"]
        elif proxy.get("tls"):
            q["security"] = "tls"
        if proxy.get("client-fingerprint"):
            q["fp"] = proxy["client-fingerprint"]
        if flow:
            q["flow"] = flow
        if sni:
            q["sni"] = sni
        if net:
            q["type"] = net
            if net == "ws":
                ws_opts = _optional_mapping(proxy.get("ws-opts"))
                if "path" in ws_opts:
                    q["path"] = ws_opts["path"]
                headers = _optional_mapping(ws_opts.get("headers"))
                if "Host" in headers:
                    q["host"] = headers["Host"]
            elif net == "grpc":
                grpc_opts = _optional_mapping(proxy.get("grpc-opts"))
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
        return f"trojan://{urllib.parse.quote(password, safe='')}@{server}:{port}{suffix}#{name}"

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
        return f"hysteria2://{urllib.parse.quote(password, safe='')}@{server}:{port}{suffix}#{name}"

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
        auth = urllib.parse.quote(uuid, safe="")
        if password:
            auth += ":" + urllib.parse.quote(password, safe="")
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
    """Reject malformed nodes before deduplication and health checking."""
    if not isinstance(proxy, dict):
        return False
    p_type = proxy.get("type")
    if not isinstance(p_type, str) or p_type not in SUPPORTED_PROTOCOLS:
        return False

    server = proxy.get("server")
    port = proxy.get("port")
    if not isinstance(server, str) or not server.strip():
        return False
    server = server.strip()
    if type(port) not in (int, str):
        return False
    try:
        port = int(port)
    except ValueError:
        return False
    if not 0 < port <= 65535:
        return False

    if server.lower() in ("localhost", "0.0.0.0", "broadcasthost"):
        return False
    try:
        ip = ipaddress.ip_address(server)
        if ip.is_loopback or ip.is_private or ip.is_unspecified or ip.is_link_local or ip.is_reserved:
            return False
    except ValueError:
        pass  # Domain name

    credential = "uuid" if p_type in ("vmess", "vless", "tuic") else "password"
    if not isinstance(proxy.get(credential), str) or not proxy[credential].strip():
        return False
    for field in ("name", "uuid", "password", "network", "sni", "servername", "flow",
                  "cipher", "client-fingerprint", "obfs", "obfs-password"):
        if field in proxy and not isinstance(proxy[field], str):
            return False
    for field in ("tls", "udp", "skip-cert-verify"):
        if field in proxy and not isinstance(proxy[field], bool):
            return False
    if "alterId" in proxy and (type(proxy["alterId"]) is not int or proxy["alterId"] < 0):
        return False
    if "alpn" in proxy and (not isinstance(proxy["alpn"], list)
                            or not all(isinstance(value, str) for value in proxy["alpn"])):
        return False

    try:
        for field, string_fields in (
            ("ws-opts", ("path",)),
            ("grpc-opts", ("grpc-service-name",)),
            ("reality-opts", ("public-key", "short-id")),
        ):
            options = _optional_mapping(proxy.get(field))
            if any(key in options and not isinstance(options[key], str) for key in string_fields):
                return False
        headers = _optional_mapping(_optional_mapping(proxy.get("ws-opts")).get("headers"))
        if not all(isinstance(key, str) and isinstance(value, str) for key, value in headers.items()):
            return False
        reality = _optional_mapping(proxy.get("reality-opts"))
        if reality and not reality.get("public-key"):
            return False
    except ValueError:
        return False

    proxy["server"] = server
    proxy["port"] = port
    if p_type == "vmess" and not proxy.get("cipher"):
        proxy["cipher"] = "auto"
    if p_type == "hy2":
        proxy["type"] = "hysteria2"
    return True


def deduplicate_proxies(proxies):
    seen = set()
    deduped = []
    for index, proxy in enumerate(proxies, start=1):
        try:
            configuration = {key: value for key, value in proxy.items()
                             if key not in ("name", "_country", "_iso")}
            key = json.dumps(configuration, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (AttributeError, TypeError, ValueError, RecursionError):
            log(f"Skipping node #{index}: invalid configuration")
            continue
        if key not in seen:
            seen.add(key)
            deduped.append(proxy)
    return deduped

async def _check_single_tcp(p, sem, timeout=2.0):
    # Hysteria2 与 TUIC 为纯 UDP/QUIC 协议，跳过 Stage A TCP 握手避免误杀，由 Stage B 真实 QUIC 测活
    p_type = p.get("type", "").lower()
    if p_type in ("hysteria2", "hy2", "tuic"):
        return p

    async with sem:
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(p['server'], int(p['port'])),
                timeout=timeout
            )
            w.close()
            await w.wait_closed()
            return p
        except Exception:
            return None

async def _tcp_ping_stage_a(proxies, max_concurrency=250, timeout=2.0):
    sem = asyncio.Semaphore(max_concurrency)
    tasks = [_check_single_tcp(p, sem, timeout) for p in proxies]
    results = await asyncio.gather(*tasks)
    return [p for p in results if p]

def find_mihomo_executable():
    which_path = shutil.which("mihomo") or shutil.which("clash-meta")
    if which_path:
        return which_path
    candidates = [
        Path("./mihomo"),
        Path("/tmp/mihomo_bin"),
        Path("/tmp/mihomo_test/mihomo"),
        Path("/usr/local/bin/mihomo")
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None

def _mihomo_delay_stage_b(proxies, mihomo_bin, timeout_ms=3500):
    if not proxies:
        return []
    if not mihomo_bin:
        raise HealthCheckError("Mihomo executable is unavailable")

    named_proxies = []
    for idx, p in enumerate(proxies):
        p_copy = dict(p)
        # Ensure unique ascii name for internal mihomo controller routing
        p_copy['name'] = f"p_{idx}_{p_copy.get('type')}"
        named_proxies.append(p_copy)

    node_names = [p['name'] for p in named_proxies]
    controller_port = 19996
    cfg = {
        'mixed-port': 18886,
        'external-controller': f"127.0.0.1:{controller_port}",
        'mode': 'rule',
        'log-level': 'silent',
        'proxies': named_proxies,
        'proxy-groups': [
            {
                'name': 'check_group',
                'type': 'select',
                'proxies': node_names
            }
        ]
    }

    temp_dir = None
    proc = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="mihomo_probe_")
        cfg_file = os.path.join(temp_dir, "config.yaml")
        with open(cfg_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(cfg, f, allow_unicode=True)

        # Core errors can contain subscription credentials; never forward its output.
        proc = subprocess.Popen(
            [mihomo_bin, '-d', temp_dir, '-f', cfg_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        import time

        controller_ready = False
        for _ in range(16):
            if proc.poll() is not None:
                break
            try:
                with socket.create_connection(("127.0.0.1", controller_port), timeout=0.5):
                    controller_ready = True
                    break
            except OSError:
                time.sleep(0.5)
        if not controller_ready:
            raise HealthCheckError("Mihomo controller did not start")

        url = (
            f"http://127.0.0.1:{controller_port}/group/check_group/delay"
            f"?timeout={timeout_ms}&url=http://cp.cloudflare.com/generate_204"
        )
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                delays = json.loads(res.read().decode('utf-8'))
        except urllib.error.HTTPError as error:
            # Only a 504 with a valid delay map may carry partial successful checks.
            try:
                if error.code != 504:
                    raise HealthCheckError(f"Mihomo controller returned HTTP {error.code}") from None
                delays = json.loads(error.read().decode('utf-8'))
            finally:
                error.close()

        if not isinstance(delays, dict) or any(
            name not in node_names or type(delay) not in (int, float) or not math.isfinite(delay)
            for name, delay in delays.items()
        ):
            raise HealthCheckError("Mihomo controller returned invalid delay data")
        alive_names = {name for name, delay in delays.items() if delay > 0}
        return [orig for orig, named in zip(proxies, named_proxies) if named['name'] in alive_names]
    except HealthCheckError:
        raise
    except Exception as error:
        raise HealthCheckError(f"Mihomo verification failed ({type(error).__name__})") from None
    finally:
        try:
            if proc is not None:
                if proc.poll() is None:
                    proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise HealthCheckError(f"Mihomo cleanup failed ({type(error).__name__})") from None
        finally:
            if temp_dir is not None:
                shutil.rmtree(temp_dir, ignore_errors=True)


def filter_live_nodes(proxies):
    log(f"Stage A: Fast TCP ping check for {len(proxies)} nodes...")
    import time
    t0 = time.time()
    try:
        stage_a_alive = asyncio.run(_tcp_ping_stage_a(proxies))
    except Exception as e:
        raise HealthCheckError(f"Stage A TCP ping failed ({type(e).__name__})") from None

    t1 = time.time()
    log(f"Stage A completed in {t1-t0:.2f}s: {len(stage_a_alive)}/{len(proxies)} reachable.")

    if not stage_a_alive:
        return []

    mihomo_bin = find_mihomo_executable()
    if not mihomo_bin:
        raise HealthCheckError("Mihomo executable is unavailable")

    log(f"Stage B: Mihomo HTTP 204 real handshake check using {mihomo_bin}...")
    t2 = time.time()
    stage_b_alive = _mihomo_delay_stage_b(stage_a_alive, mihomo_bin)
    t3 = time.time()
    log(f"Stage B completed in {t3-t2:.2f}s: {len(stage_b_alive)}/{len(stage_a_alive)} confirmed fully operational.")
    return stage_b_alive

def _get_country_flag(iso_code):
    if not iso_code or len(iso_code) != 2 or iso_code == "UN":
        return "🌐"
    return chr(ord(iso_code[0].upper()) + 127397) + chr(ord(iso_code[1].upper()) + 127397)

def _query_ip_geo(ip, reader):
    if not reader or not ip:
        return "UN", "未知"
    try:
        res = reader.get(ip)
        if not res:
            return "UN", "未知"
        country = res.get("country") or res.get("registered_country") or {}
        iso = country.get("iso_code", "UN")
        names = country.get("names", {})
        zh_name = names.get("zh-CN") or names.get("en") or "未知"
        # Standardize common names
        name_map = {
            "Hong Kong": "香港",
            "Taiwan": "台湾",
            "United States": "美国",
            "Japan": "日本",
            "Singapore": "新加坡",
            "South Korea": "韩国",
            "Korea": "韩国",
            "United Kingdom": "英国",
            "Germany": "德国",
            "France": "法国",
            "Canada": "加拿大",
            "Australia": "澳大利亚",
            "Russia": "俄罗斯",
            "India": "印度",
            "Spain": "西班牙",
            "Mexico": "墨西哥",
            "Brazil": "巴西",
            "Philippines": "菲律宾",
            "Italy": "意大利",
            "Portugal": "葡萄牙",
            "Thailand": "泰国",
            "Indonesia": "印尼",
            "印度尼西亚": "印尼",
            "Netherlands": "荷兰",
            "Romania": "罗马尼亚",
            "Switzerland": "瑞士",
            "Turkey": "土耳其",
        }
        zh_name = name_map.get(zh_name, zh_name)
        return iso, zh_name
    except Exception:
        return "UN", "未知"

def standardize_proxy_names(proxies):
    mmdb_paths = [
        Path("./mmdb/GeoLite2-Country.mmdb"),
        Path("./mmdb/Country.mmdb"),
        Path("/tmp/GeoLite2-Country.mmdb"),
        Path("/tmp/Country.mmdb")
    ]
    mmdb_file = next((p for p in mmdb_paths if p.is_file()), None)

    reader = None
    if maxminddb and mmdb_file:
        try:
            reader = maxminddb.open_database(str(mmdb_file))
            log(f"Loaded GeoIP database from {mmdb_file}")
        except Exception as e:
            log(f"Failed to open GeoIP database: {e}")

    # Resolve server IPs concurrently (skip plain IPs to accelerate)
    dns_cache = {}
    servers = list({p.get("server") for p in proxies if p.get("server")})
    domain_servers = []
    for s in servers:
        try:
            ipaddress.ip_address(s)
            dns_cache[s] = s
        except ValueError:
            domain_servers.append(s)

    def resolve_server(s):
        try:
            return s, socket.gethostbyname(s)
        except Exception:
            return s, None

    if domain_servers:
        with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(resolve_server, s) for s in domain_servers]
            for f in concurrent.futures.as_completed(futures):
                s, ip = f.result()
                if ip:
                    dns_cache[s] = ip

    # Group and number proxies by region, strictly discard unknown regions
    region_counters = {}
    standardized = []
    discarded_unknown = 0

    for p in proxies:
        p_new = dict(p)
        server = p_new.get("server", "")
        ip = dns_cache.get(server, server)
        iso, country_name = _query_ip_geo(ip, reader)

        # 丢弃未知地区节点 (无法定位、非公网或未分配地区)
        if not iso or iso == "UN" or country_name == "未知":
            discarded_unknown += 1
            continue

        flag = _get_country_flag(iso)

        p_type = p_new.get("type", "").upper()
        if p_type == "HY2":
            p_type = "HYSTERIA2"

        region_key = f"{flag} {country_name}"
        region_counters[region_key] = region_counters.get(region_key, 0) + 1
        idx = region_counters[region_key]

        new_name = f"{flag} {country_name} {idx:02d} [{p_type}]"
        p_new["name"] = new_name
        p_new["_country"] = country_name
        p_new["_iso"] = iso
        standardized.append(p_new)

    if reader:
        try:
            reader.close()
        except Exception:
            pass

    log(f"Filtered out {discarded_unknown} unknown region nodes.")
    log(f"Standardized {len(standardized)} node names across {len(region_counters)} regions.")
    return standardized

def main():
    log("Starting local subscription aggregator...")
    all_proxies = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(download_url, url): _source_label(url, index)
                   for index, url in enumerate(SOURCES, start=1)}
        for future in concurrent.futures.as_completed(futures):
            source = futures[future]
            try:
                data = future.result()
                if data:
                    proxies = parse_content(data)
                    log(f"Fetched {source}: found {len(proxies)} nodes")
                    all_proxies.extend(proxies)
                else:
                    log(f"Fetched {source}: empty or failed")
            except Exception as e:
                log(f"Error fetching/parsing {source} ({type(e).__name__})")

    log(f"Total fetched nodes: {len(all_proxies)}")
    valid_proxies = []
    for index, proxy in enumerate(all_proxies, start=1):
        if validate_proxy(proxy):
            valid_proxies.append(proxy)
        else:
            log(f"Skipping node #{index}: invalid or unsupported configuration")
    log(f"Valid nodes after validation: {len(valid_proxies)}")
    valid_proxies = deduplicate_proxies(valid_proxies)
    log(f"Total nodes after deduplication: {len(valid_proxies)}")

    if not valid_proxies:
        log("No valid nodes found! Exiting.")
        sys.exit(1)

    # Health check pipeline: Stage A (TCP ping) + Stage B (Mihomo HTTP 204 real handshake)
    try:
        valid_proxies = filter_live_nodes(valid_proxies)
    except HealthCheckError as e:
        log(f"Health checks failed: {e}; keeping previous outputs.")
        sys.exit(1)
    if not valid_proxies:
        log("No verified live nodes; keeping previous outputs.")
        sys.exit(1)
    log(f"Retaining {len(valid_proxies)} verified live nodes.")

    # Standardize node names using GeoIP + Country Code + Protocol
    valid_proxies = standardize_proxy_names(valid_proxies)

    # Write share links to subscribe.txt
    lines = []
    export_proxies = []
    for index, p in enumerate(valid_proxies, start=1):
        try:
            link = to_link(p)
        except Exception as e:
            # Do not log node credentials or exception messages containing input data.
            log(f"Skipping node #{index}: link conversion failed ({type(e).__name__})")
            continue
        if link:
            export_proxies.append(p)
            lines.append(link)

    # Exclude failed conversions from selected/type/Clash exports as well.
    valid_proxies = export_proxies
    if not lines:
        log("No share links generated; refusing to publish empty subscriptions.")
        sys.exit(1)

    Path('./subscribe.txt').write_text("\n".join(lines) + "\n")
    log(f"Generated subscribe.txt with {len(lines)} nodes")

    # Extract Hysteria2 links
    hy2_links = [l for l in lines if l.startswith("hysteria2://")]
    Path('./hysteriaNode.txt').write_text("\n".join(hy2_links) + "\n")
    log(f"Generated hysteriaNode.txt with {len(hy2_links)} hysteria2 nodes")

    # Generate special selected countries node list (max 2 per country)
    target_countries = [
        ("西班牙", "ES", r"(?i)(西班牙|Spain|\bES\b|Espana)"),
        ("墨西哥", "MX", r"(?i)(墨西哥|\bMX\b|Mexico)"),
        ("巴西", "BR", r"(?i)(巴西|Brazil|\bBR\b)"),
        ("英国", "GB", r"(?i)(英国|Great Britain|\bGB\b|\bUK\b)"),
        ("菲律宾", "PH", r"(?i)(菲律宾|\bPH\b|Philippines|Manila|马尼拉)"),
        ("印度", "IN", r"(?i)(印度(?!尼西亚)|India|\bIN\b)"),
        ("日本", "JP", r"(?i)(日本|Japan|\bJP\b|川日|东京|大阪|泉日|埼玉|沪日|深日)"),
        ("新加坡", "SG", r"(?i)(新加坡|Singapore|\bSG\b|狮城)"),
        ("法国", "FR", r"(?i)(法国|\bFR\b|France|Paris|巴黎)"),
        ("加拿大", "CA", r"(?i)(加拿大|\bCA\b|Canada|Toronto|Vancouver|多伦多|温哥华)"),
        ("澳大利亚", "AU", r"(?i)(澳大利亚|澳洲|\bAU\b|Australia|Sydney|Melbourne|悉尼|墨尔本)"),
        ("意大利", "IT", r"(?i)(意大利|\bIT\b|Italy|Milan|Rome|米兰|罗马(?!尼亚))"),
        ("葡萄牙", "PT", r"(?i)(葡萄牙|\bPT\b|Portugal|Lisbon|里斯本)"),
        ("泰国", "TH", r"(?i)(泰国|泰|\bTH\b|Thailand|Bangkok|曼谷)"),
        ("印尼", "ID", r"(?i)(印尼|印度尼西亚|\bID\b|Indonesia|Jakarta|雅加达)"),
        ("荷兰", "NL", r"(?i)(荷兰|\bNL\b|Netherlands|Amsterdam|阿姆斯特丹)"),
    ]
    selected_proxies = []
    selected_keys = set()
    for c_name, iso, regex in target_countries:
        pattern = re.compile(regex)
        matched = []
        for p in valid_proxies:
            p_key = (p.get("server"), p.get("port"), p.get("type"))
            if p_key in selected_keys:
                continue
            # 严格依据真实出口 GeoIP 国家/ISO 匹配，若不匹配再用无歧义正则兜底，杜绝跨国误判
            if p.get("_country") == c_name or p.get("_iso") == iso:
                matched.append(p)
                if len(matched) == 2:
                    break
            elif pattern.search(p.get("name", "")):
                if not p.get("_country") or p.get("_country") == c_name:
                    matched.append(p)
                    if len(matched) == 2:
                        break
        for p in matched:
            selected_keys.add((p.get("server"), p.get("port"), p.get("type")))
            selected_proxies.append(p)

    selected_links = [to_link(p) for p in selected_proxies]
    selected_links = [l for l in selected_links if l]
    Path('./selected.txt').write_text("\n".join(selected_links) + "\n")
    log(f"Generated selected.txt with {len(selected_links)} nodes across target countries")

    # Classify nodes into type/
    type_dir = Path('./type')
    type_dir.mkdir(exist_ok=True)
    # Clear existing
    for f in type_dir.glob("*.txt"):
        f.unlink()

    for proto in ["vmess", "vless", "trojan"]:
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

        # 用函数式替换：替换串里的 \x 等序列不会被当成正则转义解析
        replacement = "proxies:\n" + proxies_yaml_part
        result_clash = re.sub(r'^proxies:.*?(?=^proxy-groups:)', lambda _: replacement, template_str, flags=re.MULTILINE | re.DOTALL)

        # 验证生成的 YAML
        try:
            yaml.safe_load(result_clash)
            (yaml_dir / 'clash.yaml').write_text(result_clash)
            log(f"Generated yaml/clash.yaml with {len(clash_proxies)} proxies")
        except yaml.YAMLError as e:
            log(f"⚠ Generated clash.yaml failed YAML validation ({type(e).__name__})")
            log("Skipping clash.yaml generation")
    else:
        log("⚠ Template file not found: ./template/clash_template.yaml")

    # Write release_note.md for GitHub Releases
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    note_content = (
        f"## 🚀 节点自动更新 ({now_str} CST)\n\n"
        f"- **可用总节点数**: `{len(lines)}`\n"
        f"- **特选指定国家数**: `{len(selected_links)}` (16个指定国家，每国至多2个)\n"
        f"- **Hysteria2 节点数**: `{len(hy2_links)}`\n\n"
        "### 📦 包含附件\n"
        "- `subscribe.txt` (全量聚合订阅)\n"
        "- `selected.txt` (特选指定国家精选)\n"
        "- `hysteriaNode.txt` (仅 Hysteria2)\n"
        "- `clash.yaml` (Clash 格式配置)\n"
        "- 协议分类: `vmess.txt`, `vless.txt`, `trojan.txt`\n\n"
        "> ⚠️ **免责提示**: 公共节点出入口流量存在安全隐患，严禁用于高敏账户、密码登录与金融操作。\n"
    )
    Path('./release_note.md').write_text(note_content, encoding='utf-8')
    log("Generated release_note.md")

if __name__ == "__main__":
    main()
