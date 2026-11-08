"""The toolkit's own MCP server: read-only, three tools, no writers.

The boundary these tests defend: an MCP tool call has no diff, no dry run and no
explicit --yes, so no config writer may live behind one. This server exposes
status, diff and validate only, each a thin wrapper around the same cmd_*
function the CLI runs - if the two surfaces ever drift apart, the output
comparisons here fail.
"""

import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mock_station
from test_runsheet import load_tool

runsheet = load_tool()
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "station.json"
SCRIPT = ROOT / "scripts" / "runsheet.py"

READ_ONLY_NAMES = ["runsheet_status", "runsheet_diff", "runsheet_validate"]
WRITER_WORDS = ("apply", "character", "blocklist", "skills", "backup", "restore",
                "onair", "pull", "prune", "edit")


class McpServerTestCase(unittest.TestCase):
    def setUp(self):
        self.server = mock_station.start_mock()
        self.addCleanup(self.server.stop)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)

        self._saved_environ = dict(os.environ)
        self.addCleanup(self._restore_environ)
        for key in ("SUBWAVE_HOST", "SUBWAVE_STATE_DIR"):
            os.environ.pop(key, None)
        os.environ.update({
            "SUBWAVE_BASE_URL": self.server.url,
            "SUBWAVE_ADMIN_USER": "mock-admin",
            "SUBWAVE_ADMIN_PASS": "mock-pass",
        })

        self._saved_instance = runsheet.INSTANCE_DIR
        runsheet.INSTANCE_DIR = self.tmp / "instance"
        self.addCleanup(lambda: setattr(runsheet, "INSTANCE_DIR", self._saved_instance))

        document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        model = runsheet.build_live_model(document["settings"], document["schedule"])
        runsheet.write_instance(model, {}, capture={
            "tier": 2, "at": "2026-10-31T00:00:00Z", "lossy": False, "lost": []})

    def _restore_environ(self):
        os.environ.clear()
        os.environ.update(self._saved_environ)

    # -- helpers -----------------------------------------------------------
    def rpc(self, method, params=None, identifier=1):
        message = {"jsonrpc": "2.0", "id": identifier, "method": method}
        if params is not None:
            message["params"] = params
        return runsheet.mcp_handle(message)

    def call_tool(self, name, arguments=None):
        return self.rpc("tools/call", {"name": name, "arguments": arguments or {}})

    def text(self, response):
        blocks = response["result"]["content"]
        self.assertTrue(blocks, response)
        self.assertEqual(blocks[0]["type"], "text")
        return blocks[0]["text"]

    def run_cli(self, func, args=None):
        """Run a cmd_* function exactly as the CLI does and capture its stdout."""
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = func(runsheet.Config(), args or argparse.Namespace())
        return code, buffer.getvalue()

    def mutations(self):
        return [request for request in self.server.station.requests
                if request["method"] != "GET"]


class ToolListTests(McpServerTestCase):
    def test_exposes_exactly_three_tools(self):
        response = self.rpc("tools/list")
        tools = response["result"]["tools"]
        self.assertEqual([tool["name"] for tool in tools], READ_ONLY_NAMES)

    def test_every_tool_is_annotated_read_only(self):
        for tool in self.rpc("tools/list")["result"]["tools"]:
            with self.subTest(tool=tool["name"]):
                annotations = tool.get("annotations") or {}
                self.assertIs(annotations.get("readOnlyHint"), True)
                self.assertIs(annotations.get("destructiveHint"), False)

    def test_no_writer_tool_is_exposed(self):
        for tool in self.rpc("tools/list")["result"]["tools"]:
            with self.subTest(tool=tool["name"]):
                for word in WRITER_WORDS:
                    self.assertNotIn(word, tool["name"].lower(),
                                     "%r looks like a writer" % tool["name"])
                # Descriptions may say what the server does not do; the name must
                # still be one of the three read-only verbs.
                self.assertIn(tool["name"], READ_ONLY_NAMES)
                self.assertEqual(tool["inputSchema"]["type"], "object")

    def test_initialize_advertises_three_tools(self):
        response = self.rpc("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"}})
        result = response["result"]
        self.assertEqual(result["protocolVersion"], "2025-06-18")
        self.assertIn("tools", result["capabilities"])
        self.assertEqual(result["serverInfo"]["name"], runsheet.MCP_SERVER_NAME)


class ToolCallTests(McpServerTestCase):
    def test_status_matches_the_cli(self):
        code, expected = self.run_cli(runsheet.cmd_status)
        response = self.call_tool("runsheet_status")
        self.assertEqual(self.text(response), expected)
        self.assertEqual(response["result"]["structuredContent"]["exitCode"], code)
        self.assertIs(response["result"]["isError"], False)
        self.assertIn("tier      1", expected)

    def test_diff_matches_the_cli(self):
        code, expected = self.run_cli(runsheet.cmd_diff)
        response = self.call_tool("runsheet_diff")
        self.assertEqual(self.text(response), expected)
        self.assertEqual(response["result"]["structuredContent"]["exitCode"], code)
        # Drift (exit 1) is a report, not a tool failure.
        self.assertIs(response["result"]["isError"], False)
        self.assertIn("tier      1", expected)

    def test_validate_matches_the_cli(self):
        code, expected = self.run_cli(runsheet.cmd_validate,
                                      argparse.Namespace(dir=None))
        response = self.call_tool("runsheet_validate")
        self.assertEqual(self.text(response), expected)
        self.assertEqual(response["result"]["structuredContent"]["exitCode"], code)
        self.assertIn("result    ok", expected)
        self.assertIs(response["result"]["isError"], False)

    def test_validate_accepts_a_directory(self):
        demo = str(ROOT / "examples" / "demo")
        response = self.call_tool("runsheet_validate", {"dir": demo})
        self.assertEqual(response["result"]["structuredContent"]["exitCode"], 0)
        self.assertIn("ok", self.text(response))

    def test_unknown_tool_is_rejected_and_the_server_survives(self):
        response = self.call_tool("runsheet_apply")
        self.assertEqual(response["error"]["code"], -32602)
        self.assertIn("only", response["error"]["message"])
        # The next message is still answered: a bad call must not kill the server.
        self.assertEqual([tool["name"] for tool in self.rpc("tools/list", identifier=2)
                          ["result"]["tools"]], READ_ONLY_NAMES)

    def test_the_three_tools_never_write_to_the_station(self):
        for name in READ_ONLY_NAMES:
            with self.subTest(tool=name):
                response = self.call_tool(name)
                self.assertNotIn("error", response)
        self.assertEqual(self.mutations(), [],
                         "a read-only tool must only ever GET")
        self.assertEqual(self.server.station.mcp_calls, [],
                         "the toolkit's MCP server must not touch the station's own MCP")


class StdioTransportTests(unittest.TestCase):
    """Run the real entry point: `runsheet.py mcp-server` over stdin/stdout."""

    def test_stdio_session_speaks_only_json_on_stdout(self):
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "runsheet_validate",
                        "arguments": {"dir": "examples/demo"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "ping"},
        ]
        stdin = "".join(json.dumps(message) + "\n" for message in messages)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "mcp-server"],
            input=stdin, cwd=ROOT, capture_output=True, text=True, timeout=60,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(ROOT)})

        self.assertEqual(result.returncode, 0, result.stderr)
        # stdout is the protocol channel: every line must be one JSON response,
        # and the notification must produce no line at all.
        responses = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual([response["id"] for response in responses], [1, 2, 3, 4])
        self.assertEqual(result.stdout.count("\n"), 4, result.stdout)

        self.assertEqual([tool["name"] for tool in responses[1]["result"]["tools"]],
                         READ_ONLY_NAMES)
        validate = responses[2]["result"]
        self.assertEqual(validate["structuredContent"]["exitCode"], 0)
        self.assertIn("result    ok", validate["content"][0]["text"])
        self.assertEqual(responses[3]["result"], {})


if __name__ == "__main__":
    unittest.main()
