import base64
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.parse

import yaml

with patch.dict(os.environ, {"SOURCES_SECRET": "", "SUBSCRIBE_SOURCES": ""}):
    import run


ROOT = Path(__file__).resolve().parents[1]


def node(**overrides):
    return {
        "name": "Japan sample",
        "type": "vless",
        "server": "example.invalid",
        "port": 443,
        "uuid": "11111111-1111-4111-8111-111111111111",
        "network": "ws",
        "_iso": "JP",
        **overrides,
    }


class LinkConversionTests(unittest.TestCase):
    def test_reality_round_trip(self):
        for short_id in ("012345abcdef", ""):
            with self.subTest(short_id=short_id):
                original = node(network="tcp", tls=True, sni="example.invalid",
                                flow="xtls-rprx-vision", **{
                                    "client-fingerprint": "chrome",
                                    "reality-opts": {"public-key": "example-public-key", "short-id": short_id},
                                })
                link = run.to_link(original)
                query = urllib.parse.parse_qs(urllib.parse.urlparse(link).query, keep_blank_values=True)
                self.assertEqual(query["security"], ["reality"])
                self.assertEqual(query["pbk"], ["example-public-key"])
                self.assertEqual(query["sid"], [short_id])
                restored = run.parse_vless(link)
                for field in ("tls", "sni", "flow", "client-fingerprint", "reality-opts"):
                    self.assertEqual(restored[field], original[field])
                self.assertEqual(run.parse_vless(run.to_link(restored)), restored)

    def test_plain_tls_stays_tls(self):
        link = run.to_link(node(tls=True, sni="example.invalid"))
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlparse(link).query)["security"], ["tls"])
        self.assertTrue(run.parse_vless(link)["tls"])

    def test_reality_preserves_clash_servername(self):
        proxy = node(tls=True, servername="example.invalid", **{
            "reality-opts": {"public-key": "example-public-key"},
        })
        self.assertEqual(run.parse_vless(run.to_link(proxy))["sni"], "example.invalid")

    def test_reality_without_public_key_is_rejected(self):
        self.assertIsNone(run.parse_vless(
            "vless://11111111-1111-4111-8111-111111111111@example.invalid:443?security=reality&sid="))

    def test_password_and_name_round_trip(self):
        for protocol in ("trojan", "hysteria2", "hy2", "tuic"):
            with self.subTest(protocol=protocol):
                original = node(type=protocol, password="example@?:#/%+ 中文", name="Japan /?#% 中文")
                link = run.to_link(original)
                restored = run.parse_link(link)
                self.assertIsNotNone(restored)
                self.assertEqual(restored["password"], original["password"])
                self.assertEqual(restored["name"], original["name"])

    def test_null_websocket_options_and_headers(self):
        for protocol in ("vless", "vmess"):
            for options, expected_path in ((None, ""), ({}, ""), ({"path": "/ws", "headers": None}, "/ws")):
                with self.subTest(protocol=protocol, options=options):
                    link = run.to_link(node(type=protocol, **{"ws-opts": options}))
                    self.assertTrue(link.startswith(f"{protocol}://"))
                    if protocol == "vmess":
                        payload = json.loads(base64.b64decode(link.removeprefix("vmess://")))
                        self.assertEqual(payload["net"], "ws")
                        self.assertEqual(payload["path"], expected_path)
                        self.assertEqual(payload["host"], "")
                    else:
                        query = urllib.parse.parse_qs(urllib.parse.urlparse(link).query)
                        self.assertEqual(query["type"], ["ws"])
                        self.assertEqual(query.get("path", [""]), [expected_path])
                        self.assertNotIn("host", query)

    def test_null_grpc_options(self):
        link = run.to_link(node(network="grpc", **{"grpc-opts": None}))
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlparse(link).query), {"type": ["grpc"]})


class ExportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        original_cwd = Path.cwd()
        os.chdir(temp.name)
        self.addCleanup(os.chdir, original_cwd)
        shutil.copytree(ROOT / "template", Path("template"))
        self.logs = io.StringIO()

    def run_aggregator(self, proxies, health_check=lambda nodes: nodes, sources=None):
        payload = yaml.safe_dump({"proxies": proxies}).encode()
        with patch.object(run, "SOURCES", sources or ["https://source.invalid"]), \
                patch.object(run, "download_url", return_value=payload), \
                patch.object(run, "filter_live_nodes", side_effect=health_check), \
                patch.object(run, "standardize_proxy_names", side_effect=lambda nodes: nodes), \
                contextlib.redirect_stdout(self.logs):
            run.main()

    def test_bad_node_is_skipped_in_all_exports(self):
        bad = node(name="bad", uuid="bad-node-credential", **{"ws-opts": {"headers": 123}})
        good = node(**{"ws-opts": None})
        self.run_aggregator([bad, good])
        expected = (
            "vless://11111111-1111-4111-8111-111111111111@example.invalid:443"
            "?type=ws#Japan%20sample\n"
        )
        for filename in ("subscribe.txt", "selected.txt", "type/vless.txt"):
            self.assertEqual(Path(filename).read_text(), expected)
        clash = yaml.safe_load(Path("yaml/clash.yaml").read_text())
        self.assertEqual([p["name"] for p in clash["proxies"]], ["🟢 直连", good["name"]])
        self.assertTrue(Path("release_note.md").exists())
        self.assertIn("Skipping node", self.logs.getvalue())
        self.assertNotIn("bad-node-credential", self.logs.getvalue())

    def test_all_bad_nodes_abort_before_overwriting_outputs(self):
        previous = "previous subscription\n"
        filenames = ("subscribe.txt", "selected.txt", "hysteriaNode.txt", "release_note.md")
        for filename in filenames:
            Path(filename).write_text(previous)
        with self.assertRaises(SystemExit) as raised:
            self.run_aggregator([node(**{"ws-opts": 123})])
        self.assertEqual(raised.exception.code, 1)
        for filename in filenames:
            self.assertEqual(Path(filename).read_text(), previous)

    def test_health_failure_preserves_all_outputs(self):
        filenames = ("subscribe.txt", "selected.txt", "hysteriaNode.txt", "release_note.md",
                     "type/vless.txt", "yaml/clash.yaml")
        for filename in filenames:
            path = Path(filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("previous subscription\n")
        for result in (run.HealthCheckError("checker unavailable"), lambda nodes: []):
            with self.subTest(result=result):
                with self.assertRaises(SystemExit) as raised:
                    self.run_aggregator([node()], health_check=result)
                self.assertEqual(raised.exception.code, 1)
                for filename in filenames:
                    self.assertEqual(Path(filename).read_text(), "previous subscription\n")

    def test_malformed_and_unknown_nodes_never_reach_checker_or_exports(self):
        good = node()
        bad = [node(type="ssr"), node(server=None), node(uuid=["invalid"]), node(server=123)]
        def check(nodes):
            self.assertEqual(len(nodes), 1)
            self.assertEqual(nodes[0]["uuid"], good["uuid"])
            return nodes
        self.run_aggregator(bad + [good], health_check=check)
        clash = yaml.safe_load(Path("yaml/clash.yaml").read_text())
        self.assertEqual(len(clash["proxies"]), 2)
        self.assertEqual(len(Path("subscribe.txt").read_text().splitlines()), 1)

    def test_none_link_is_excluded_from_clash(self):
        original_to_link = run.to_link
        skipped = node(name="unsupported", server="other.invalid")
        with patch.object(run, "to_link", side_effect=lambda p: None if p["name"] == "unsupported" else original_to_link(p)):
            self.run_aggregator([skipped, node()])
        clash = yaml.safe_load(Path("yaml/clash.yaml").read_text())
        self.assertNotIn("unsupported", [p["name"] for p in clash["proxies"]])

    def test_conversion_exception_skips_node_without_exposing_input(self):
        original_to_link = run.to_link
        def convert(proxy):
            if proxy["name"] == "bad":
                raise ValueError("example-private-credential")
            return original_to_link(proxy)
        with patch.object(run, "to_link", side_effect=convert):
            self.run_aggregator([node(name="bad", server="other.invalid"), node()])
        self.assertEqual(len(Path("subscribe.txt").read_text().splitlines()), 1)
        clash = yaml.safe_load(Path("yaml/clash.yaml").read_text())
        self.assertNotIn("bad", [p["name"] for p in clash["proxies"]])
        self.assertIn("link conversion failed", self.logs.getvalue())
        self.assertNotIn("example-private-credential", self.logs.getvalue())

    def test_tuic_is_in_combined_and_clash_exports(self):
        self.run_aggregator([node(type="tuic", password="example-password")])
        self.assertTrue(Path("subscribe.txt").read_text().startswith("tuic://"))
        clash = yaml.safe_load(Path("yaml/clash.yaml").read_text())
        self.assertEqual(clash["proxies"][1]["type"], "tuic")

    def test_fetch_success_and_failure_logs_hide_source_secrets(self):
        url = "https://example-user:example-pass@source.invalid/path-secret?token=query-secret#fragment-secret"
        self.run_aggregator([node()], sources=[url])
        with patch.object(run, "SOURCES", [url]), \
                patch.object(run, "download_url", side_effect=ValueError(url)), \
                contextlib.redirect_stdout(self.logs), self.assertRaises(SystemExit):
            run.main()
        for secret in ("example-user", "example-pass", "path-secret", "query-secret", "fragment-secret"):
            self.assertNotIn(secret, self.logs.getvalue())
        self.assertIn("source #1", self.logs.getvalue())


class ValidationTests(unittest.TestCase):
    def test_malformed_fields_are_rejected(self):
        for field, values in {
            "server": (None, 123, [], ""), "port": (None, [], True, 1.5, "bad", 65536),
            "uuid": (None, [], 123, ""), "type": ([], "ssr", "unknown"),
            "name": ([], 123), "network": ([], 123), "alpn": ("h3", [1]),
            "ws-opts": (123, {"path": []}, {"headers": 123}),
            "grpc-opts": ({"grpc-service-name": []},),
            "reality-opts": (123, {"public-key": []}),
        }.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assertFalse(run.validate_proxy(node(**{field: value})))
        for value in (None, [], 123):
            self.assertFalse(run.validate_proxy(value))
        for protocol in ("trojan", "hysteria2", "hy2", "tuic"):
            self.assertFalse(run.validate_proxy(node(type=protocol, password=["invalid"])))

    def test_numeric_ports_and_null_options_are_normalized(self):
        proxy = node(server=" example.invalid ", port="443", **{"ws-opts": None})
        self.assertTrue(run.validate_proxy(proxy))
        self.assertEqual(proxy["server"], "example.invalid")
        self.assertEqual(proxy["port"], 443)

    def test_dedup_keeps_transport_and_tls_differences(self):
        variants = [node(**fields) for fields in (
            {"ws-opts": {"path": "/a", "headers": {"Host": "a.invalid"}}},
            {"ws-opts": {"path": "/b", "headers": {"Host": "a.invalid"}}},
            {"ws-opts": {"path": "/a", "headers": {"Host": "b.invalid"}}},
            {"grpc-opts": {"grpc-service-name": "a"}},
            {"grpc-opts": {"grpc-service-name": "b"}},
            {"reality-opts": {"public-key": "key-a"}},
            {"reality-opts": {"public-key": "key-b"}},
            {"sni": "a.invalid"}, {"sni": "b.invalid"},
            {"obfs-password": "example-a"}, {"obfs-password": "example-b"},
        )]
        duplicate = dict(reversed(list(variants[0].items())))
        duplicate.update(name="different display name", _country="Japan", _iso="UN")
        self.assertEqual(run.deduplicate_proxies(variants + [duplicate]), variants)


class LoggingTests(unittest.TestCase):
    def test_download_retries_hide_url_and_exception_content(self):
        url = "https://example-user:example-pass@source.invalid/path-secret?token=query-secret#fragment-secret"
        logs = io.StringIO()
        with patch.object(run.urllib.request, "urlopen", side_effect=ValueError(url)), contextlib.redirect_stdout(logs):
            self.assertEqual(run.download_url(url), b"")
        self.assertIn("Retry", logs.getvalue())
        self.assertIn("ValueError", logs.getvalue())
        for secret in ("example-user", "example-pass", "path-secret", "query-secret", "fragment-secret"):
            self.assertNotIn(secret, logs.getvalue())

    def test_source_config_exception_is_redacted(self):
        logs = io.StringIO()
        with patch.dict(os.environ, {"SOURCES_SECRET": "https://source.invalid/example-secret"}), \
                patch.object(run, "download_url", side_effect=ValueError("example-secret")), \
                contextlib.redirect_stdout(logs):
            self.assertEqual(run.load_sources(), run.DEFAULT_SOURCES)
        self.assertNotIn("example-secret", logs.getvalue())


class HealthCheckTests(unittest.TestCase):
    def test_missing_checker_and_stage_a_error_fail_closed(self):
        for outcome in ([node()], RuntimeError("example-secret")):
            with self.subTest(outcome=outcome), \
                    patch.object(run, "_tcp_ping_stage_a", side_effect=outcome if isinstance(outcome, Exception) else None,
                                 return_value=outcome), \
                    patch.object(run, "find_mihomo_executable", return_value=None), \
                    self.assertRaises(run.HealthCheckError) as raised:
                run.filter_live_nodes([node()])
            self.assertNotIn("example-secret", str(raised.exception))

    def test_stage_a_empty_does_not_fall_back(self):
        with patch.object(run, "_tcp_ping_stage_a", return_value=[]), \
                patch.object(run, "_mihomo_delay_stage_b") as stage_b:
            self.assertEqual(run.filter_live_nodes([node()]), [])
            stage_b.assert_not_called()

    def run_stage_b(self, payload=None, error=None, exited=False, popen_error=None,
                    controller_error=None, shutdown_timeout=False):
        process = MagicMock()
        process.poll.return_value = 1 if exited else None
        if shutdown_timeout:
            process.wait.side_effect = [subprocess.TimeoutExpired("mihomo", 5), 0]
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        with tempfile.TemporaryDirectory() as parent:
            probe_dir = Path(parent) / "probe"
            probe_dir.mkdir()
            with patch.object(run.tempfile, "mkdtemp", return_value=str(probe_dir)), \
                    patch.object(run.subprocess, "Popen", return_value=process, side_effect=popen_error) as start, \
                    patch.object(run.socket, "create_connection", return_value=MagicMock(), side_effect=controller_error), \
                    patch("time.sleep"), \
                    patch.object(run.urllib.request, "urlopen", return_value=response, side_effect=error):
                try:
                    return run._mihomo_delay_stage_b([node(), node(server="other.invalid")], "mihomo")
                finally:
                    self.assertFalse(probe_dir.exists())
                    if not popen_error:
                        process.wait.assert_called()
                        self.assertEqual(start.call_args.kwargs["stdout"], subprocess.DEVNULL)
                        self.assertEqual(start.call_args.kwargs["stderr"], subprocess.DEVNULL)
                    if shutdown_timeout:
                        process.kill.assert_called_once()
                        self.assertEqual(process.wait.call_count, 2)

    def test_stage_b_returns_only_verified_nodes(self):
        result = self.run_stage_b({"p_0_vless": 120, "p_1_vless": 0})
        self.assertEqual(result, [node()])
        self.assertEqual(self.run_stage_b({}), [])

    def test_stage_b_failure_is_not_a_successful_empty_result(self):
        cases = ({"exited": True}, {"popen_error": OSError("example-secret")},
                 {"controller_error": OSError("example-secret")},
                 {"error": TimeoutError("example-secret")}, {"payload": []},
                 {"payload": {"message": "example-secret"}}, {"payload": {"p_0_vless": True}},
                 {"error": urllib.error.HTTPError("http://localhost", 500, "example-secret", {}, io.BytesIO(b'{}'))})
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(run.HealthCheckError) as raised:
                self.run_stage_b(**kwargs)
            self.assertNotIn("example-secret", str(raised.exception))

    def test_stage_b_504_accepts_only_valid_partial_delays(self):
        error = urllib.error.HTTPError("http://localhost", 504, "timeout", {},
                                       io.BytesIO(b'{"p_0_vless":120}'))
        self.assertEqual(self.run_stage_b(error=error), [node()])

    def test_unresponsive_process_is_killed_and_reaped(self):
        self.assertEqual(self.run_stage_b({"p_0_vless": 120}, shutdown_timeout=True), [node()])


if __name__ == "__main__":
    unittest.main()
