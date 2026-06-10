"""OPA / regorus result decoding.

Why this exists
---------------
Regorus (and some OPA evaluation paths) may return *result envelopes* rather than
direct Python primitives. Critically:

    bool(<envelope containing false>) == True

So naive patterns like `allow = bool(raw_result)` are unsafe (F-01).

This module provides a single, defensive decoder that:
  - Unwraps common OPA/regorus envelopes
  - Treats undefined/empty results as deny (fail-closed)
  - Enforces type expectations (type mismatch => raise)
  - Supports both boolean entrypoints and structured decision objects
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from canon.exceptions import DecodeError


class OPAResultDecodeError(DecodeError):
    """OPA/regorus result cannot be decoded safely.

    Subclass of DecodeError for OPA-specific decode failures.
    """

    def __init__(self, message: str):
        # Extract source context from message if possible
        super().__init__(source="opa_result", reason=message)


@dataclass(frozen=True, slots=True)
class DecodedDecision:
    """Normalized decision output.

    - allow: final allow/deny
    - deny_reasons: tuple[str, ...] (never dicts)
    - decision: the unwrapped decision object (if the entrypoint returned one)
    """

    allow: bool
    deny_reasons: tuple[str, ...] = ()
    decision: dict[str, Any] | None = None


def _stable_sort(values: list[Any]) -> list[Any]:
    """Deterministically sort values for stable outputs (mainly set->list)."""
    try:
        return sorted(values)
    except Exception:
        return sorted(values, key=lambda v: json.dumps(v, sort_keys=True, default=str))


def _try_convert_unknown_to_python(value: Any) -> Any | None:
    """Try to convert unknown regorus/PyO3 objects to Python types.

    Different regorus versions/bindings may expose helper methods.
    We try a small set of common names and parse JSON when needed.
    """
    # Common JSON-ish methods in bindings / wrappers
    candidates = (
        "to_json",
        "to_json_str",
        "to_json_string",
        "json",
        "model_dump",
        "dict",
    )
    for name in candidates:
        fn = getattr(value, name, None)
        if not callable(fn):
            continue
        try:
            out = fn()
        except Exception:
            continue

        # If a method returns a JSON string, try parsing it.
        if isinstance(out, (str, bytes, bytearray)):
            try:
                s = out.decode("utf-8") if isinstance(out, (bytes, bytearray)) else out
                s = s.strip()
                if s and s[0] in "{[":
                    return json.loads(s)
            except Exception:
                # Treat as plain string/bytes
                return out
        else:
            return out
    return None


def unwrap_opa_result(raw: Any, *, max_depth: int = 12) -> Any | None:
    """Unwrap common OPA/regorus envelope shapes into a Python value.

    Handles (non-exhaustive):
      - OPA REST envelope: {"result": <value>}
      - regorus/OPA eval envelope: [{"value": <value>}]
      - regorus/OPA expressions: [{"expressions": [{"value": <value>}]}]
      - singleton nesting: [[{"value": false}]] -> false
      - undefined: None / [] / empty set -> None
    """
    value: Any = raw

    for depth in range(max_depth):
        if value is None:
            return None

        # Primitives: already unwrapped
        if isinstance(value, (bool, int, float, str)):
            return value

        # Mapping (dict-like) envelopes
        if isinstance(value, Mapping):
            # OPA REST API: {"result": ...}
            if "result" in value:
                value = value.get("result")
                continue

            # Common "value" envelope: {"value": ...}
            if "value" in value:
                value = value.get("value")
                continue

            # OPA eval-style: {"expressions": [{"value": ...}, ...]}
            exprs = value.get("expressions")
            if isinstance(exprs, list):
                if not exprs:
                    return None
                if len(exprs) == 1:
                    value = exprs[0]
                    continue
                # Multiple expressions => unwrap each (caller must validate)
                return [unwrap_opa_result(e, max_depth=max_depth - depth - 1) for e in exprs]

            # Otherwise treat as final object value (copy to plain dict)
            return dict(value)

        # Sequence envelopes
        if isinstance(value, (list, tuple)):
            if len(value) == 0:
                return None
            if len(value) == 1:
                value = value[0]
                continue
            return [unwrap_opa_result(v, max_depth=max_depth - depth - 1) for v in value]

        # Set envelopes (rego sets often map here)
        if isinstance(value, (set, frozenset)):
            if len(value) == 0:
                return None
            items = [unwrap_opa_result(v, max_depth=max_depth - depth - 1) for v in value]
            return _stable_sort(items)

        # Unknown PyO3/regorus Value types: attempt conversion
        converted = _try_convert_unknown_to_python(value)
        if converted is not None:
            value = converted
            continue

        # Give up: return as-is (caller will type-check and likely error)
        return value

    # Depth exceeded: return best-effort
    return value


def decode_bool(raw: Any, *, default: bool = False, context: str = "opa.bool") -> bool:
    """Decode a boolean decision from an OPA/regorus result.

    Fail-closed:
      - undefined/empty => `default` (caller should pass default=False)

    Strict:
      - non-bool => raise OPAResultDecodeError
      - multiple differing bool results => raise (non-deterministic)
    """
    val = unwrap_opa_result(raw)
    if val is None:
        return default

    if isinstance(val, bool):
        return val

    if isinstance(val, (list, tuple)):
        bools: list[bool] = []
        for item in val:
            item_val = unwrap_opa_result(item)
            if item_val is None:
                continue
            if isinstance(item_val, bool):
                bools.append(item_val)
                continue
            raise OPAResultDecodeError(
                f"{context}: expected boolean results, got element "
                f"{type(item_val).__name__}: {item_val!r}"
            )
        if not bools:
            return default
        if len(set(bools)) == 1:
            return bools[0]
        raise OPAResultDecodeError(f"{context}: non-deterministic boolean results: {bools!r}")

    raise OPAResultDecodeError(f"{context}: expected boolean, got {type(val).__name__}: {val!r}")


def decode_strings(raw: Any, *, context: str = "opa.strings") -> tuple[str, ...]:
    """Decode a set/list of strings from an OPA/regorus result.

    Fail-closed:
      - undefined/empty => ()

    Strict:
      - any non-string element => raise OPAResultDecodeError
    """
    val = unwrap_opa_result(raw)
    if val is None:
        return ()

    if isinstance(val, str):
        return (val,)

    if isinstance(val, (list, tuple, set, frozenset)):
        out: list[str] = []
        for item in val:
            item_val = unwrap_opa_result(item)
            if item_val is None:
                continue
            if isinstance(item_val, str):
                out.append(item_val)
                continue
            raise OPAResultDecodeError(
                f"{context}: expected string elements, got {type(item_val).__name__}: {item_val!r}"
            )

        # De-dupe while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for s in out:
            if s not in seen:
                deduped.append(s)
                seen.add(s)
        return tuple(deduped)

    raise OPAResultDecodeError(
        f"{context}: expected string collection, got {type(val).__name__}: {val!r}"
    )


def decode_object(raw: Any, *, context: str = "opa.object") -> dict[str, Any] | None:
    """Decode a dict/object from an OPA/regorus result (or None if undefined)."""
    val = unwrap_opa_result(raw)
    if val is None:
        return None
    if isinstance(val, Mapping):
        return dict(val)
    raise OPAResultDecodeError(f"{context}: expected object, got {type(val).__name__}: {val!r}")


def decode_decision(raw: Any, *, context: str = "opa.decision") -> DecodedDecision:
    """Decode either:
      - a boolean allow/deny entrypoint, OR
      - a structured decision object containing allow/passed and deny reasons.

    Supported decision object keys:
      - allow: bool
      - passed: bool (gate_output compatibility)
      - deny_reasons: list/set of strings
      - deny: list/set of strings (legacy compatibility)
    """
    val = unwrap_opa_result(raw)
    if val is None:
        return DecodedDecision(allow=False)

    # Boolean entrypoint
    if isinstance(val, bool):
        return DecodedDecision(allow=val)

    # Structured decision object
    if isinstance(val, Mapping):
        obj = dict(val)

        if "allow" in obj:
            allow = decode_bool(obj["allow"], default=False, context=f"{context}.allow")
        elif "passed" in obj:
            allow = decode_bool(obj["passed"], default=False, context=f"{context}.passed")
        else:
            raise OPAResultDecodeError(
                f"{context}: decision object missing 'allow' or 'passed' keys; "
                f"keys={list(obj.keys())!r}"
            )

        deny_reasons: tuple[str, ...] = ()
        if "deny_reasons" in obj:
            deny_reasons = decode_strings(obj["deny_reasons"], context=f"{context}.deny_reasons")
        elif "deny" in obj:
            deny_reasons = decode_strings(obj["deny"], context=f"{context}.deny")

        return DecodedDecision(allow=allow, deny_reasons=deny_reasons, decision=obj)

    # Sometimes unwrap can yield a list of values for multiple results.
    if isinstance(val, (list, tuple)):
        # If this is really boolean results, decode_bool handles consistency checks.
        if all(isinstance(unwrap_opa_result(v), bool) or unwrap_opa_result(v) is None for v in val):
            return DecodedDecision(allow=decode_bool(val, default=False, context=context))

        # If multiple decision objects are returned, require consistent allow and merge deny reasons.
        decoded: list[DecodedDecision] = []
        for v in val:
            v_unwrapped = unwrap_opa_result(v)
            if v_unwrapped is None:
                continue
            decoded.append(decode_decision(v_unwrapped, context=context))
        if not decoded:
            return DecodedDecision(allow=False)
        allows = {d.allow for d in decoded}
        if len(allows) != 1:
            raise OPAResultDecodeError(f"{context}: non-deterministic decision objects")
        merged: list[str] = []
        for d in decoded:
            merged.extend(d.deny_reasons)
        # De-dupe
        seen: set[str] = set()
        uniq: list[str] = []
        for r in merged:
            if r not in seen:
                uniq.append(r)
                seen.add(r)
        return DecodedDecision(allow=decoded[0].allow, deny_reasons=tuple(uniq))

    raise OPAResultDecodeError(
        f"{context}: expected boolean or object decision, got {type(val).__name__}: {val!r}"
    )


def decode_policy(
    *,
    decision_raw: Any | None,
    allow_raw: Any | None,
    deny_raw: Any | None = None,
    deny_field_name: str = "deny_reasons",
) -> DecodedDecision:
    """Unified policy decoding entrypoint.

    Decoding priority:
    1) If `decision_raw` yields a valid decision object -> use it (fail-closed if invalid)
    2) Else decode `allow_raw` and optionally decode deny reasons from `deny_raw`

    This is the main entry point for OPA result parsing in opa.py.
    """
    # 1) Structured decision object (preferred)
    if decision_raw is not None:
        try:
            val = unwrap_opa_result(decision_raw)
            if val is not None and isinstance(val, Mapping):
                dec = decode_decision(decision_raw, context="opa.decision")
                return dec
        except OPAResultDecodeError as e:
            # Contract present but invalid -> fail closed & surface error as deny reason
            return DecodedDecision(
                allow=False,
                deny_reasons=(f"OPA decision contract error: {e}",),
                decision=None,
            )

    # 2) Legacy allow + deny pattern
    try:
        allow = decode_bool(allow_raw, default=False, context="opa.allow")
    except OPAResultDecodeError as e:
        # Parse error on allow -> fail closed
        return DecodedDecision(
            allow=False,
            deny_reasons=(f"OPA allow parse error: {e}",),
            decision=None,
        )

    deny_reasons: tuple[str, ...] = ()
    if deny_raw is not None:
        try:
            deny_reasons = decode_strings(deny_raw, context=f"opa.{deny_field_name}")
        except OPAResultDecodeError as e:
            # Parse error on deny_reasons -> continue but add error as deny reason
            deny_reasons = (f"OPA deny_reasons parse error: {e}",)

    return DecodedDecision(
        allow=allow,
        deny_reasons=deny_reasons,
        decision=None,
    )


__all__ = [
    "DecodedDecision",
    "OPAResultDecodeError",
    "decode_bool",
    "decode_decision",
    "decode_object",
    "decode_policy",
    "decode_strings",
    "unwrap_opa_result",
]
