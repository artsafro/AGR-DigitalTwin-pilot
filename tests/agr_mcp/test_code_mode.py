"""new-case: synthetic Max Code Mode protocol fixtures; never connects to a live DCC."""
import importlib.util
import copy
import sys
import subprocess

import pytest

import anyio
from mcp import types
from test_agr_mcp_v2 import fake_max, isolated  # shared synthetic pymxs/installed-runtime fixtures


def test_fixture_batch():
    from agr_mcp.code_mode import CodeMode
    calls = []

    class FixtureClient:
        async def call_tool(self, name, arguments):
            calls.append((name, arguments))
            return types.CallToolResult(content=[], structuredContent={
                "status": "pass", "result": {"objects": [{"handle": 101, "name": "SyntheticBox"}]}})

    async def run():
        mode = CodeMode(FixtureClient())
        request = {"request_id": "fixture-1", "steps": [
            {"id": str(i), "tool": "agr_check_run", "arguments": {
                "scene": "synthetic.max", "handles": [101], "check_ids": ["qa.xview"]}}
            for i in range(2)]}
        result = await mode.execute(request)
        assert result["status"] == "ok"
        assert [r["id"] for r in result["receipts"]] == ["0", "1"]
        assert all(r["request_id"] == "fixture-1" for r in result["receipts"])
        assert len(calls) == 2
    anyio.run(run)


def test_prototype_exists():
    assert importlib.util.find_spec("agr_mcp.code_mode") is not None, "safe Code Mode is missing"


def program(n=1, tool="agr_check_run"):
    args = ({"preview_id": "a" * 64} if tool == "agr_op_apply" else
            {"scene": "synthetic.max", "handles": [101], "check_ids": ["qa.xview"]})
    return {"request_id": "r1", "steps": [
        {"id": str(i), "tool": tool, "arguments": copy.deepcopy(args)} for i in range(n)]}


class SceneClient:
    """Synthetic scene with one stable handle; unknown write commits before timeout."""
    def __init__(self, status="pass", timeout=False):
        self.calls = []
        self.names = {101: "SyntheticBox"}
        self.status, self.timeout = status, timeout

    async def call_tool(self, name, arguments):
        self.calls.append((name, copy.deepcopy(arguments)))
        if name == "agr_op_apply":
            self.names[101] = "RenamedBox"
            if self.timeout:
                raise TimeoutError("response lost after commit")
        return types.CallToolResult(content=[], structuredContent={
            "status": self.status, "result": {"names": dict(self.names)}})


@pytest.mark.parametrize("bad", [None, {}, {"steps": []}, {"request_id": "r", "steps": []},
    {"request_id": "r", "steps": [{}]}, {"request_id": "", "steps": []},
    *[{"request_id": "r", "steps": [{"id": "x", "tool": name, "arguments": {}}]}
      for name in ["agr_exec_unsafe", "execute_maxscript", "eval", "agr_handoff_import", "unknown"]],
    *[{"request_id": "r", "steps": [{"id": "x", "tool": "agr_check_run", "arguments": {
        "scene": "s", "handles": [101], "check_ids": ["qa.xview"], "extra": v}}]}
      for v in [float("nan"), float("inf"), -float("inf"), 32]],
])
def test_invalid_program(bad):
    from agr_mcp.code_mode import CodeMode
    client = SceneClient()
    async def run():
        with pytest.raises(ValueError):
            await CodeMode(client).execute(bad)
        assert client.calls == []
    anyio.run(run)


@pytest.mark.parametrize("count", [0, 1, 31, 32, 33])
def test_bounds(count):
    from agr_mcp.code_mode import CodeMode
    client = SceneClient()
    async def run():
        if 1 <= count <= 32:
            assert (await CodeMode(client).execute(program(count)))["status"] == "ok"
            assert len(client.calls) == count
        else:
            with pytest.raises(ValueError):
                await CodeMode(client).execute(program(count))
            assert not client.calls
    anyio.run(run)


def test_write_default():
    from agr_mcp.code_mode import CodeMode
    client = SceneClient()
    async def run():
        with pytest.raises(ValueError, match="write"):
            await CodeMode(client).execute(program(tool="agr_op_apply"))
        assert client.names[101] == "SyntheticBox" and not client.calls
    anyio.run(run)


def test_partial_and_duplicate_preflight():
    from agr_mcp.code_mode import CodeMode
    async def run():
        for mutation in ["partial", "duplicate", "unknown"]:
            client = SceneClient()
            p = program(2)
            if mutation == "partial":
                del p["steps"][1]["arguments"]
            elif mutation == "duplicate":
                p["steps"][1]["id"] = "0"
            else:
                p["steps"][1]["arguments"]["check_ids"] = ["not.mapped"]
            with pytest.raises(ValueError):
                await CodeMode(client).execute(p)
            assert not client.calls
    anyio.run(run)


def test_request_reuse():
    from agr_mcp.code_mode import CodeMode
    async def run():
        client = SceneClient()
        mode = CodeMode(client)
        await mode.execute(program())
        for p in [program(), program(2)]:
            with pytest.raises(ValueError, match="request_id"):
                await mode.execute(p)
        assert len(client.calls) == 1
    anyio.run(run)


@pytest.mark.parametrize("status", ["fail", "review", "not_run", "unknown", "needs_human", None, "rolled_back"])
def test_statuses(status):
    from agr_mcp.code_mode import CodeMode
    async def run():
        client = SceneClient(status=status)
        result = await CodeMode(client).execute(program(2))
        assert result["status"] != "ok"
        assert len(client.calls) == 1
        assert result["receipts"][1]["status"] == "skipped"
    anyio.run(run)


def test_unknown_write():
    from agr_mcp.code_mode import CodeMode
    async def run():
        client = SceneClient(timeout=True)
        mode = CodeMode(client)
        p = program(2, "agr_op_apply")
        p["allow_write"] = True
        result = await mode.execute(p)
        assert result["status"] == "unknown"
        assert client.names[101] == "RenamedBox" and len(client.calls) == 1
        assert result["receipts"][1]["status"] == "skipped"
        p["request_id"] = "r2"
        with pytest.raises(ValueError, match="reconcil"):
            await mode.execute(p)
        read = program()
        read["request_id"] = "readback"
        out = await mode.execute(read)
        assert out["receipts"][0]["result"]["result"]["names"][101] == "RenamedBox"
        assert len(client.calls) == 2
    anyio.run(run)


def test_write_receipt():
    from agr_mcp.code_mode import CodeMode
    async def run():
        p = program(tool="agr_op_apply")
        p["allow_write"] = True
        out = await CodeMode(SceneClient()).execute(p)
        assert out["status"] == "committed_unverified"
        assert out["receipts"][0]["status"] == "committed_unverified"
    anyio.run(run)


def test_existing_guard(tmp_path, monkeypatch):
    from agr_mcp import server
    from agr_mcp.code_mode import build_server
    from mcp.shared.memory import create_connected_server_and_client_session as connect
    for key, child in [("AGR_MCP_LOCK_DIR", "locks"), ("AGR_MCP_AUDIT", "audit.jsonl"),
                       ("AGR_JOURNAL_DIR", "journal"), ("AGR_MCP_DATA_DIR", "data")]:
        monkeypatch.setenv(key, str(tmp_path / child))
    async def run():
        async with connect(server.build_server(env={})) as backend:
            async with connect(build_server(backend)) as frontend:
                names = [t.name for t in (await frontend.list_tools()).tools]
                assert names == ["agr_code_search", "agr_code_run"]
                found = await frontend.call_tool("agr_code_search", {"query": "agr_op_apply"})
                assert "agr_op_apply" in [s["name"] for s in found.structuredContent["operations"]]
                assert "agr_exec_unsafe" not in [s["name"] for s in found.structuredContent["operations"]]
                p = program(tool="agr_op_apply")
                p["allow_write"] = True
                out = await frontend.call_tool("agr_code_run", p)
                assert out.isError
                receipt = out.structuredContent["receipts"][0]
                assert receipt["result"]["error_code"] == "stale_preview"
                assert receipt["status"] == "unknown"
    anyio.run(run)


def test_real_guarded_fixture(fake_max, monkeypatch):
    from agr_mcp import server
    from agr_mcp.code_mode import build_server
    from mcp.shared.memory import create_connected_server_and_client_session as connect
    monkeypatch.setenv("AGR_MCP_MAX_PID", "1292")
    async def run():
        async with connect(server.build_server(max_transport=fake_max.transport)) as backend:
            async with connect(build_server(backend)) as frontend:
                p = program(2)
                for step in p["steps"]:
                    step["arguments"].update(scene="live", handles=[1, 2])
                out = await frontend.call_tool("agr_code_run", p)
                assert not out.isError, out
                assert out.structuredContent["status"] == "ok"
                assert len(out.structuredContent["receipts"]) == 2
                assert len(fake_max.sent) == 2
                assert fake_max.rt.selection == [fake_max.nodes[2]]
                assert all(r["result"]["counts"]["objects"] == 2 for r in out.structuredContent["receipts"])
    anyio.run(run)


def test_generated_unsafe_names(monkeypatch):
    from agr_mcp.code_mode import CodeMode
    monkeypatch.setenv("AGR_MCP_UNSAFE", "1")
    async def run():
        client = SceneClient()
        mode = CodeMode(client)
        for name in ["agr_exec_unsafe"] + [f"agr_exec_unsafe_{i}" for i in range(64)]:
            p = program()
            p["steps"][0]["tool"] = name
            with pytest.raises(ValueError, match="unsupported"):
                await mode.execute(p)
        assert not client.calls
    anyio.run(run)


def test_state_change_and_concurrent_duplicate():
    from agr_mcp.code_mode import CodeMode
    async def run():
        p = program(2)
        entered, release = anyio.Event(), anyio.Event()
        class Delayed(SceneClient):
            async def call_tool(self, name, arguments):
                if not self.calls:
                    entered.set()
                    await release.wait()
                return await super().call_tool(name, arguments)
        client = Delayed()
        mode = CodeMode(client)
        results = []
        async def first():
            results.append(await mode.execute(p))
        async with anyio.create_task_group() as group:
            group.start_soon(first)
            await entered.wait()
            with pytest.raises(ValueError, match="request_id"):
                await mode.execute(p)
            p["steps"][1]["tool"] = "agr_exec_unsafe"
            release.set()
        assert len(client.calls) == 2
        assert all(n == "agr_check_run" for n, _ in client.calls)
        assert results[0]["status"] == "ok"
    anyio.run(run)


def test_cancelled_write_keeps_reconcile_latch():
    from agr_mcp.code_mode import CodeMode
    async def run():
        entered = anyio.Event()
        class Cancelled(SceneClient):
            async def call_tool(self, name, arguments):
                entered.set()
                await anyio.sleep_forever()
        mode = CodeMode(Cancelled())
        p = program(tool="agr_op_apply")
        p["allow_write"] = True
        async with anyio.create_task_group() as group:
            group.start_soon(mode.execute, p)
            await entered.wait()
            group.cancel_scope.cancel()
        p["request_id"] = "after-cancel"
        with pytest.raises(ValueError, match="reconcile"):
            await mode.execute(p)
    anyio.run(run)


def test_search_schema_copy_and_error_flag():
    from agr_mcp.code_mode import CodeMode
    async def run():
        class ErrorFlag(SceneClient):
            async def call_tool(self, name, arguments):
                r = await super().call_tool(name, arguments)
                r.isError = True
                return r
        client = ErrorFlag()
        mode = CodeMode(client)
        found = mode.search("agr_check_run")
        found[0]["inputSchema"].clear()
        assert (await mode.execute(program(2)))["status"] == "failed"
        assert len(client.calls) == 1
        p = program()
        p["request_id"] = "new"
        del p["steps"][0]["arguments"]["scene"]
        with pytest.raises(ValueError):
            await mode.execute(p)
    anyio.run(run)


def test_fresh_process():
    completed = subprocess.run([sys.executable, "-c", "from agr_mcp.code_mode import CodeMode; "
        "print([s['name'] for s in CodeMode(None).search('agr_')])"], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "agr_op_apply" in completed.stdout and "agr_exec_unsafe" not in completed.stdout
