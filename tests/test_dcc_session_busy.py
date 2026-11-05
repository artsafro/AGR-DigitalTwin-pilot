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
