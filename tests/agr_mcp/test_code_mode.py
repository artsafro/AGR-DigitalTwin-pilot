"""new-case: synthetic Max Code Mode protocol fixtures; never connects to a live DCC."""
import importlib.util
import copy
import sys
import subprocess

import pytest

import anyio
from mcp import types


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
