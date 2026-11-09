"""A held DCC session lock skips the caller; every other dcc_batch result fails (#986)."""
import pytest

from tests.dcc_session import skip_if_dcc_session_busy

BUSY = '{"status": "busy", "lock": "C:/tmp/agr-3dsmax-session.lock", "held_by": "manual"}'


def test_explicit_busy_skips_with_holder_and_every_other_result_fails():
    with pytest.raises(pytest.skip.Exception, match="manual"):
        skip_if_dcc_session_busy(3, BUSY, "")
    with pytest.raises(pytest.skip.Exception, match="manual"):
        skip_if_dcc_session_busy(3, "noise before\n" + BUSY, "")
    with pytest.raises(pytest.skip.Exception, match="manual"):
        skip_if_dcc_session_busy(3, "", BUSY)

    with pytest.raises(pytest.fail.Exception):
        skip_if_dcc_session_busy(1, '{"status": "error", "exit_code": 1}', "")
    with pytest.raises(pytest.fail.Exception):
        skip_if_dcc_session_busy(1, "not json", "")
    with pytest.raises(pytest.fail.Exception):
        skip_if_dcc_session_busy(2, "", "")
    with pytest.raises(pytest.fail.Exception):
        skip_if_dcc_session_busy(1, '{"status": "Busy", "held_by": "manual"}', "")
    with pytest.raises(pytest.fail.Exception):
        skip_if_dcc_session_busy(1, "status is busy held_by manual", "")

    skip_if_dcc_session_busy(0, BUSY, BUSY)


def _outcome(returncode, stdout, stderr):
    """Run the helper and report skip/fail/ok, so a wrong skip fails the test instead of skipping it."""
    try:
        skip_if_dcc_session_busy(returncode, stdout, stderr)
    except pytest.skip.Exception as exc:
        return ("skip", str(exc))
    except pytest.fail.Exception as exc:
        return ("fail", str(exc).split(":", 1)[0])
    return ("ok", None)


TOP_BUSY = '{"status":"busy","held_by":"x"}'


def test_a_exit3_top_level_busy_skips_with_holder():
    assert _outcome(3, TOP_BUSY, "") == ("skip", "DCC session lock is busy, held_by='x'")


def test_b_busy_answer_with_other_exit_code_fails():
    assert _outcome(1, TOP_BUSY, "") == ("fail", "dcc batch exited 1")
    assert _outcome(5, "", TOP_BUSY) == ("fail", "dcc batch exited 5")


def test_c_exit3_with_only_nested_busy_fails():
    assert _outcome(3, '{"result":{"status":"busy"}}', "") == ("fail", "dcc batch exited 3")
    assert _outcome(3, '[{"status":"busy","held_by":"x"}]', "") == ("fail", "dcc batch exited 3")
    assert _outcome(3, 'log: {"status":"busy","held_by":"x"}', "") == ("fail", "dcc batch exited 3")


def test_d_exit0_with_busy_answer_neither_skips_nor_fails():
    assert _outcome(0, TOP_BUSY, TOP_BUSY) == ("ok", None)


def test_e_exit3_without_json_fails():
    assert _outcome(3, "not json", "") == ("fail", "dcc batch exited 3")
    assert _outcome(3, "", "") == ("fail", "dcc batch exited 3")
    assert _outcome(3, '{"status":"busy"', "") == ("fail", "dcc batch exited 3")


def _max_adapter(monkeypatch, returncode, stdout):
    import importlib.util
    from pathlib import Path

    review = Path(__file__).resolve().parents[1] / "tools" / "review"
    monkeypatch.syspath_prepend(str(review))
    spec = importlib.util.spec_from_file_location("review_max_adapter_busy", review / "max_adapter.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Proc:
        pass

    proc = Proc()
    proc.returncode, proc.stdout, proc.stderr = returncode, stdout, ""
    monkeypatch.setattr(module, "_call", lambda args: proc)
    return module


@pytest.mark.parametrize("returncode, expected", [
    (3, ("skip", "DCC session lock is busy, held_by='x'")),
    (1, ("fail", "dcc batch exited 1")),
])
def test_max_adapter_error_carries_exit_code_to_the_busy_skip(monkeypatch, tmp_path, returncode, expected):
    module = _max_adapter(monkeypatch, returncode, TOP_BUSY + "\n")
    with pytest.raises(module.MaxAdapterError) as info:
        module.LiveAdapter().selftest(tmp_path / "work", tmp_path / "scene.max", tmp_path / "p.png")
    exc = info.value
    assert isinstance(exc, RuntimeError) and exc.returncode == returncode
    assert _outcome(getattr(exc, "returncode", 1), str(exc), "") == expected
