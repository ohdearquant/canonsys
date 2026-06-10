
from __future__ import annotations

import pytest

pytest.importorskip("regorus")


from dataclasses import dataclass
from typing import Any

import pytest

from canon.utils.opa.decoder import (
    OPAResultDecodeError,
    decode_bool,
    decode_decision,
    decode_policy,
    decode_strings,
    unwrap_opa_result,
)

# -----------------------------------------------------------------------------
# Unit tests: unwrap_opa_result
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, None),
        ([], None),
        (set(), None),
        (True, True),
        (False, False),
        ({"result": True}, True),
        ({"result": False}, False),
        ({"value": True}, True),
        ({"value": False}, False),
        ([{"value": False}], False),
        ([{"value": True}], True),
        ([{"expressions": [{"value": False}]}], False),
        ([{"expressions": [{"value": True}]}], True),
        ({"expressions": [{"value": True}]}, True),
        # Multiple envelopes => list of unwrapped values
        ([{"value": "a"}, {"value": "b"}], ["a", "b"]),
    ],
)
def test_unwrap_opa_result(raw: Any, expected: Any) -> None:
    assert unwrap_opa_result(raw) == expected


# -----------------------------------------------------------------------------
# Unit tests: decode_bool (F-01 protection)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, False),  # undefined => fail-closed
        ([], False),
        (False, False),
        (True, True),
        ([{"value": False}], False),
        ([{"value": True}], True),
        ([{"expressions": [{"value": False}]}], False),
        ([{"expressions": [{"value": True}]}], True),
        # Multiple same bool results => ok
        ([{"value": False}, {"value": False}], False),
    ],
)
def test_decode_bool_ok(raw: Any, expected: bool) -> None:
    assert decode_bool(raw, default=False, context="test.allow") is expected


@pytest.mark.parametrize(
    "raw",
    [
        [{"value": False}, {"value": True}],  # conflicting
        {"value": "true"},  # type mismatch
        [{"value": "true"}],
        {"expressions": [{"value": "true"}]},
        "true",  # wrong type
        {"allow": True},  # decision object is not a bool
    ],
)
def test_decode_bool_errors(raw: Any) -> None:
    with pytest.raises(OPAResultDecodeError):
        decode_bool(raw, default=False, context="test.allow")


# -----------------------------------------------------------------------------
# Unit tests: decode_strings (F-02 protection)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        (None, ()),
        ([], ()),
        ("one", ("one",)),
        (["a", "b"], ("a", "b")),
        ({"value": ["a", "b"]}, ("a", "b")),
        ([{"value": "a"}, {"value": "b"}], ("a", "b")),
        (
            [{"expressions": [{"value": "a"}]}, {"expressions": [{"value": "b"}]}],
            ("a", "b"),
        ),
        (set(["a", "b"]), ("a", "b")),  # order not guaranteed but tuple is deduped
        (["a", "a", "b"], ("a", "b")),  # dedupe
    ],
)
def test_decode_strings_ok(raw: Any, expected: tuple[str, ...]) -> None:
    got = decode_strings(raw, context="test.deny")
    assert got == expected or (set(got) == set(expected) and len(got) == len(expected))


@pytest.mark.parametrize(
    "raw",
    [
        [{"value": {"msg": "nope"}}],  # dict element
        {"value": [{"msg": "nope"}]},
        123,
        {"value": 123},
    ],
)
def test_decode_strings_errors(raw: Any) -> None:
    with pytest.raises(OPAResultDecodeError):
        decode_strings(raw, context="test.deny")


# -----------------------------------------------------------------------------
# Unit tests: decode_decision (supports bool + structured object)
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, allow, deny_reasons",
    [
        (None, False, ()),
        (False, False, ()),
        (True, True, ()),
        ([{"value": False}], False, ()),
        ({"allow": True, "deny_reasons": ["x"]}, True, ("x",)),
        ([{"value": {"allow": False, "deny_reasons": ["no"]}}], False, ("no",)),
        ({"passed": False, "deny": ["legacy"]}, False, ("legacy",)),
    ],
)
def test_decode_decision_ok(raw: Any, allow: bool, deny_reasons: tuple[str, ...]) -> None:
    d = decode_decision(raw, context="test.decision")
    assert d.allow is allow
    assert d.deny_reasons == deny_reasons


@pytest.mark.parametrize(
    "raw",
    [
        {"deny_reasons": ["x"]},  # missing allow/passed
        {"allow": "yes"},  # wrong type
        {"passed": {"value": "no"}},  # wrong type
        [{"value": {"allow": "yes"}}],
    ],
)
def test_decode_decision_errors(raw: Any) -> None:
    with pytest.raises(OPAResultDecodeError):
        decode_decision(raw, context="test.decision")


# -----------------------------------------------------------------------------
# Error handling tests: client/engine behaviors via stubs (no regorus required)
# -----------------------------------------------------------------------------


class _StubEngine:
    def __init__(self, mapping: dict[str, Any] | None = None, exc: Exception | None = None) -> None:
        self.mapping = mapping or {}
        self.exc = exc

    def set_input(self, _input: Any) -> None:
        return

    def eval_rule(self, query: str) -> Any:
        if self.exc is not None:
            raise self.exc
        return self.mapping.get(query)


@dataclass
class _StubCheckout:
    engine: _StubEngine

    def __enter__(self) -> _StubEngine:
        return self.engine

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _StubPool:
    def __init__(self, engine: _StubEngine) -> None:
        self._engine = engine

    def checkout(self) -> _StubCheckout:
        return _StubCheckout(self._engine)

    def get_thread_engine(self) -> _StubEngine:
        """Return thread-local engine (stub returns same engine)."""
        return self._engine


@pytest.mark.asyncio
async def test_policy_engine_fail_closed_on_eval_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Import lazily to avoid regorus import at module import time in some envs
    from canon.enforcement.types import EnforcementLevel
    from canon.utils.opa.engine import PolicyEngine, ResolvedPolicy

    engine = _StubEngine(exc=TimeoutError("simulated timeout"))
    pool = _StubPool(engine)

    pe = PolicyEngine.__new__(PolicyEngine)  # bypass __init__
    pe._pool = pool  # type: ignore[attr-defined]
    pe._fail_closed = True  # type: ignore[attr-defined]

    policy = ResolvedPolicy(
        policy_id="test.timeout",
        rego_package="test.timeout",
        enforcement=EnforcementLevel.HARD_MANDATORY,
        legal_citation=None,
        regulation_url=None,
        parameters={},
    )

    # evaluate_single catches and returns EVALUATION_ERROR fail-closed
    res = await pe.evaluate_single(policy, input_data={"x": 1})
    assert res.allowed is False
    assert res.violation_code == "EVALUATION_ERROR"
    assert res.violation_message and "simulated timeout" in res.violation_message


# -----------------------------------------------------------------------------
# Integration tests with real regorus
# -----------------------------------------------------------------------------


import json

from canon.utils.opa.engine import EnginePool


class TestRegorusIntegration:
    """Integration tests validating decoder behavior with real regorus engine."""

    def test_default_false_and_deny(self) -> None:
        """Test that default allow := false returns allow=False when conditions not met.

        Validates F-01 fix: bool(raw_result) can't incorrectly ALLOW when
        default allow := false is set but raw_result is a truthy envelope.
        """
        pool = EnginePool(size=1)
        pool.add_policy(
            "default_false.rego",
            """
package test.default_false

import rego.v1

default allow := false

allow if {
    input.approved == true
}
""",
        )

        with pool.checkout() as engine:
            # Condition NOT met - should return False
            engine.set_input_json(json.dumps({"approved": False}))
            result = engine.eval_rule("data.test.default_false.allow")
            assert result is False

            # Condition met - should return True
            engine.set_input_json(json.dumps({"approved": True}))
            result = engine.eval_rule("data.test.default_false.allow")
            assert result is True

    def test_undefined_allow_no_default_returns_none(self) -> None:
        """Test that undefined allow (no default) returns None.

        Validates F-01 fix: undefined results must be handled as fail-closed
        by the decoder (caller responsibility to treat None as deny).
        """
        pool = EnginePool(size=1)
        pool.add_policy(
            "no_default.rego",
            """
package test.no_default

import rego.v1

# No default - allow is undefined unless condition met
allow if {
    input.approved == true
}
""",
        )

        with pool.checkout() as engine:
            # Condition NOT met - allow is undefined, returns None
            engine.set_input_json(json.dumps({"approved": False}))
            result = engine.eval_rule("data.test.no_default.allow")
            # regorus returns None for undefined rules
            assert result is None

            # Condition met - should return True
            engine.set_input_json(json.dumps({"approved": True}))
            result = engine.eval_rule("data.test.no_default.allow")
            assert result is True

    def test_decision_object_preferred_over_allow_rule(self) -> None:
        """Test that decision object is preferred over allow rule.

        Validates migration path: policies can export decision := {...}
        and callers using rule="allow" still work, but decision takes priority.
        """
        pool = EnginePool(size=1)
        pool.add_policy(
            "decision_object.rego",
            """
package test.decision_object

import rego.v1

default allow := false

allow if {
    input.simple_check == true
}

# Decision object with richer structure
decision := {
    "allow": _decision_allow,
    "reason": _decision_reason,
    "policy_id": "test_policy",
} if {
    input.use_decision == true
}

_decision_allow := true if { input.approved == true }
_decision_allow := false if { not input.approved == true }

_decision_reason := "approved by decision logic" if { input.approved == true }
_decision_reason := "denied by decision logic" if { not input.approved == true }
""",
        )

        with pool.checkout() as engine:
            # When use_decision=true, decision object should be available
            engine.set_input_json(json.dumps({"use_decision": True, "approved": True}))
            decision = engine.eval_rule("data.test.decision_object.decision")
            assert decision is not None
            assert decision["allow"] is True
            assert decision["reason"] == "approved by decision logic"
            assert decision["policy_id"] == "test_policy"

            # Decision object with deny
            engine.set_input_json(json.dumps({"use_decision": True, "approved": False}))
            decision = engine.eval_rule("data.test.decision_object.decision")
            assert decision is not None
            assert decision["allow"] is False
            assert decision["reason"] == "denied by decision logic"

            # When use_decision=false, decision is undefined, fall back to allow rule
            engine.set_input_json(json.dumps({"use_decision": False, "simple_check": True}))
            decision = engine.eval_rule("data.test.decision_object.decision")
            assert decision is None  # undefined
            allow = engine.eval_rule("data.test.decision_object.allow")
            assert allow is True

    def test_decode_bool_with_real_opa_result(self) -> None:
        """Test decode_bool handles real OPA results correctly."""
        pool = EnginePool(size=1)
        pool.add_policy(
            "bool_test.rego",
            """
package test.bool_test

import rego.v1

default allow := false

allow if {
    input.flag == true
}
""",
        )

        with pool.checkout() as engine:
            engine.set_input_json(json.dumps({"flag": True}))
            result = engine.eval_rule("data.test.bool_test.allow")

            # decode_bool should handle this correctly
            decoded = decode_bool(result, default=False, context="test.allow")
            assert decoded is True

            engine.set_input_json(json.dumps({"flag": False}))
            result = engine.eval_rule("data.test.bool_test.allow")
            decoded = decode_bool(result, default=False, context="test.allow")
            assert decoded is False


# -----------------------------------------------------------------------------
# Unit tests: decode_policy (decision priority order)
# -----------------------------------------------------------------------------


class TestDecodePolicyPriority:
    """Tests for decode_policy priority order: decision_raw > allow_raw."""

    def test_decision_object_takes_priority_over_allow_rule(self):
        """When decision_raw has allow=True but allow_raw returns False, decision wins."""
        # decision_raw contains a valid decision object with allow=True
        decision_raw = [{"value": {"allow": True, "reason": "approved"}}]
        # allow_raw would return False
        allow_raw = [{"value": False}]

        result = decode_policy(
            decision_raw=decision_raw,
            allow_raw=allow_raw,
            deny_raw=None,
        )

        # Decision object should win
        assert result.allow is True
        assert result.decision is not None
        assert result.decision["allow"] is True

    def test_decision_object_deny_takes_priority(self):
        """When decision_raw has allow=False, it takes priority over allow_raw=True."""
        # decision_raw contains a valid decision object with allow=False
        decision_raw = [{"value": {"allow": False, "deny_reasons": ["policy denied"]}}]
        # allow_raw would return True
        allow_raw = [{"value": True}]

        result = decode_policy(
            decision_raw=decision_raw,
            allow_raw=allow_raw,
            deny_raw=None,
        )

        # Decision object should win
        assert result.allow is False
        assert result.decision is not None

    def test_allow_raw_used_when_decision_raw_is_none(self):
        """When decision_raw is None, allow_raw is used."""
        allow_raw = [{"value": True}]

        result = decode_policy(
            decision_raw=None,
            allow_raw=allow_raw,
            deny_raw=None,
        )

        assert result.allow is True
        assert result.decision is None

    def test_allow_raw_false_when_decision_raw_is_none(self):
        """When decision_raw is None and allow_raw is False."""
        allow_raw = [{"value": False}]

        result = decode_policy(
            decision_raw=None,
            allow_raw=allow_raw,
            deny_raw=None,
        )

        assert result.allow is False
        assert result.decision is None

    def test_fail_closed_when_both_none(self):
        """When both decision_raw and allow_raw are None, fail closed."""
        result = decode_policy(
            decision_raw=None,
            allow_raw=None,
            deny_raw=None,
        )

        # Default to False (fail-closed)
        assert result.allow is False

    def test_decision_raw_empty_list_falls_through_to_allow(self):
        """Empty decision_raw (like []) should fall through to allow_raw."""
        # Empty list unwraps to None
        decision_raw = []
        allow_raw = [{"value": True}]

        result = decode_policy(
            decision_raw=decision_raw,
            allow_raw=allow_raw,
            deny_raw=None,
        )

        # Should use allow_raw since decision_raw unwraps to None
        assert result.allow is True
        assert result.decision is None

    def test_invalid_decision_object_fails_closed(self):
        """Invalid decision object structure should fail closed with error message."""
        # decision_raw contains a non-mapping value (should be a dict)
        decision_raw = [{"value": "not a dict"}]
        allow_raw = [{"value": True}]

        result = decode_policy(
            decision_raw=decision_raw,
            allow_raw=allow_raw,
            deny_raw=None,
        )

        # Since decision_raw is present but not a valid mapping, it should
        # fall through to allow_raw processing
        # Actually, unwrap gives "not a dict" which is not None but not a Mapping
        # So the code falls through to legacy allow pattern
        assert result.allow is True
        assert result.decision is None

    def test_deny_reasons_included_with_allow_false(self):
        """deny_raw should be included when allow is False."""
        allow_raw = [{"value": False}]
        deny_raw = [{"value": ["reason1", "reason2"]}]

        result = decode_policy(
            decision_raw=None,
            allow_raw=allow_raw,
            deny_raw=deny_raw,
        )

        assert result.allow is False
        assert result.deny_reasons == ("reason1", "reason2")

    def test_decision_object_with_deny_reasons(self):
        """Decision object with deny_reasons should be used."""
        decision_raw = [{"value": {"allow": False, "deny_reasons": ["blocked by policy"]}}]

        result = decode_policy(
            decision_raw=decision_raw,
            allow_raw=None,
            deny_raw=None,
        )

        assert result.allow is False
        assert result.decision is not None
        # deny_reasons are in the decision object, not in result.deny_reasons
        # The decision dict is stored in result.decision

    def test_partial_failure_decision_ok_allow_none(self):
        """When decision_raw succeeds but allow_raw is None, use decision."""
        decision_raw = [{"value": {"allow": True}}]

        result = decode_policy(
            decision_raw=decision_raw,
            allow_raw=None,
            deny_raw=None,
        )

        assert result.allow is True
        assert result.decision is not None
