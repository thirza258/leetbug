import pytest

from app.execution import equal, grade


def test_strict_json_equality_and_float_tolerance():
    assert not equal(True, 1)
    assert not equal(0, False)
    assert not equal(2147483649, 2147483648)
    assert not equal({"ok": 1}, {"ok": True})
    assert equal(0.30000000000000004, 0.3)
    assert not equal(float("nan"), 1.2)
    assert not equal({"total": 1, "extra": 2}, {"total": 1})


def test_state_assertions_are_graded_outside_the_process_and_hidden_redacted():
    tests = [
        {"name": "Rollback", "input": {"fail": True}, "expected": {"state": {"balance": 100}}, "hidden": False,
         "assertions": [{"path": "state.balance", "equals": 100}]},
        {"name": "Secret input", "input": {"secret": 31337}, "expected": 4, "hidden": True, "assertions": []},
    ]
    state, results = grade(tests, {"results": [{"status": "ok", "output": {"state": {"balance": 0}}},
                                               {"status": "runtime_error", "stderr": "Secret input was 31337"}]})
    assert state == "runtime_error"
    assert results[0]["assertions"][0]["passed"] is False
    assert set(results[1]) == {"name", "hidden", "status"}
    assert "31337" not in str(results)


@pytest.mark.parametrize("forged", ["passed", "failed", "anything"])
def test_submitted_program_cannot_report_its_own_grade(forged):
    tests = [{"name": "test", "input": {}, "expected": 42, "hidden": False, "assertions": []}]
    status, _ = grade(tests, {"fatal_status": "passed", "results": [{"status": forged, "output": 0}]})
    assert status == "runtime_error"
    status, _ = grade(tests, {"results": []})
    assert status == "runtime_error"

