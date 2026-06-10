"""Runtime-checkable protocols and @implements decorator.

Protocols define structural interfaces (duck typing) with isinstance() support.
Use @implements(Protocol) to declare and validate protocol implementations.

Example:
    @implements(Serializable, Invocable)
    class MyClass:
        def to_dict(self, **kwargs): ...
        async def invoke(self): ...
"""

import inspect
import warnings
from typing import Any, Literal, Protocol, runtime_checkable
from uuid import UUID

__all__ = (
    "Allowable",
    "Communicatable",
    "Containable",
    "Deserializable",
    "Hashable",
    "Invocable",
    "Observable",
    "Serializable",
    "SignatureMismatchError",
    "implements",
)


class SignatureMismatchError(TypeError):
    """@implements detected incompatible method signature."""

    pass


@runtime_checkable
class ObservableProto(Protocol):
    """Has unique UUID identity. Check: isinstance(obj, Observable)."""

    @property
    def id(self) -> UUID:
        """Unique identifier for this instance."""
        ...


@runtime_checkable
class Serializable(Protocol):
    """Can serialize to dict. Implement to_dict(**kwargs) -> dict."""

    def to_dict(self, **kwargs: Any) -> dict[str, Any]:
        """Serialize to dict. kwargs: mode, format, etc."""
        ...


@runtime_checkable
class Deserializable(Protocol):
    """Can deserialize from dict. Implement classmethod from_dict(data, **kwargs)."""

    @classmethod
    def from_dict(cls, data: dict[str, Any], **kwargs: Any) -> Any:
        """Create instance from dict."""
        ...


@runtime_checkable
class Containable(Protocol):
    """Supports 'in' operator. Implement __contains__(item) -> bool."""

    def __contains__(self, item: Any) -> bool:
        """Check membership (by UUID or instance)."""
        ...


@runtime_checkable
class Invocable(Protocol):
    """Async executable. Implement async invoke() -> Any."""

    async def invoke(self) -> Any:
        """Execute and return result."""
        ...


@runtime_checkable
class Hashable(Protocol):
    """Hashable for sets/dicts. Implement __hash__() -> int."""

    def __hash__(self) -> int:
        """Hash value (typically based on immutable id)."""
        ...


@runtime_checkable
class Allowable(Protocol):
    """Has defined allowed values. Implement allowed() -> set[str]."""

    def allowed(self) -> set[str]:
        """Set of allowed keys/values."""
        ...


@runtime_checkable
class Communicatable(Protocol):
    """Entity with mailbox for message exchange.

    Enables multi-agent communication. Higher layers define Agent, Branch, etc.
    """

    @property
    def id(self) -> UUID:
        """Entity identifier for routing."""
        ...

    @property
    def mailbox(self) -> Any:
        """Mailbox for send/receive operations."""
        ...


Observable = ObservableProto
"""Alias: Observable = ObservableProto."""


def _get_signature_params(func: Any) -> dict[str, inspect.Parameter] | None:
    """Extract params from callable, excluding self/cls. Returns None if not introspectable."""
    if isinstance(func, (classmethod, staticmethod)):
        func = func.__func__

    if isinstance(func, property):
        return None

    if not callable(func):
        return None

    try:
        sig = inspect.signature(func)
    except (ValueError, TypeError):
        return None

    params = {}
    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        params[name] = param

    return params


def _check_signature_compatibility(
    protocol_params: dict[str, inspect.Parameter],
    impl_params: dict[str, inspect.Parameter],
) -> list[str]:
    """Check impl signature compatibility with protocol. Returns error messages.

    Rules: impl must accept required protocol params; may have extra optionals;
    *args/**kwargs can satisfy protocol params; if protocol has **kwargs, impl must too.
    """
    errors = []

    impl_has_var_positional = any(
        p.kind == inspect.Parameter.VAR_POSITIONAL for p in impl_params.values()
    )
    impl_has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in impl_params.values()
    )

    # Check if protocol has *args or **kwargs
    proto_has_var_positional = any(
        p.kind == inspect.Parameter.VAR_POSITIONAL for p in protocol_params.values()
    )
    proto_has_var_keyword = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in protocol_params.values()
    )

    # If protocol accepts **kwargs, implementation must also accept them
    # Otherwise callers passing kwargs (allowed by protocol) will fail
    if proto_has_var_keyword and not impl_has_var_keyword:
        errors.append("  - 'kwargs': protocol accepts **kwargs but implementation doesn't")

    # If protocol accepts *args, implementation must also accept them
    if proto_has_var_positional and not impl_has_var_positional:
        errors.append("  - 'args': protocol accepts *args but implementation doesn't")

    # For each protocol parameter, verify implementation can accept it
    for param_name, proto_param in protocol_params.items():
        # Skip VAR_POSITIONAL and VAR_KEYWORD in protocol (handled above)
        if proto_param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        # Check if implementation has this parameter
        if param_name in impl_params:
            impl_param = impl_params[param_name]

            # Check parameter kind compatibility
            # Implementation can be more flexible (e.g., POSITIONAL_OR_KEYWORD
            # can accept POSITIONAL_ONLY)
            proto_kind = proto_param.kind
            impl_kind = impl_param.kind

            # VAR_POSITIONAL/VAR_KEYWORD in impl can accept anything
            if impl_kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            # Required in protocol but has default in impl is OK
            # (implementation is more lenient)

            # If protocol param is required, impl param should not require
            # something the protocol doesn't provide
            if proto_param.default is inspect.Parameter.empty:
                # Protocol requires this param
                # Implementation can either:
                # 1. Also require it (empty default)
                # 2. Make it optional (has default) - this is fine

                # Check if impl param is keyword-only but protocol is positional
                if impl_kind == inspect.Parameter.KEYWORD_ONLY and proto_kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                ):
                    errors.append(
                        f"  - '{param_name}': protocol allows positional, "
                        f"but implementation requires keyword-only"
                    )
            else:
                # Protocol param is optional (has default)
                # Implementation should NOT make it required (tightening contract)
                if impl_param.default is inspect.Parameter.empty:
                    errors.append(
                        f"  - '{param_name}': protocol makes this optional, "
                        f"but implementation requires it"
                    )

        else:
            # Parameter not in implementation by name
            # Check if it can be satisfied by *args or **kwargs
            proto_kind = proto_param.kind

            if proto_kind in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            ):
                # Can be satisfied by *args or **kwargs
                if not (impl_has_var_positional or impl_has_var_keyword):
                    errors.append(
                        f"  - '{param_name}': required by protocol but not in implementation"
                    )
            elif proto_kind == inspect.Parameter.KEYWORD_ONLY:
                # Can only be satisfied by **kwargs
                if not impl_has_var_keyword:
                    errors.append(
                        f"  - '{param_name}': keyword-only param required by protocol "
                        f"but not in implementation"
                    )

    # Check if implementation has required parameters that protocol doesn't provide
    for param_name, impl_param in impl_params.items():
        # Skip *args and **kwargs
        if impl_param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        # If implementation requires a parameter (no default)
        if impl_param.default is inspect.Parameter.empty:
            # Protocol must also have this parameter
            if param_name not in protocol_params:
                # Check if protocol has *args or **kwargs that could provide it
                proto_has_var_positional = any(
                    p.kind == inspect.Parameter.VAR_POSITIONAL for p in protocol_params.values()
                )
                proto_has_var_keyword = any(
                    p.kind == inspect.Parameter.VAR_KEYWORD for p in protocol_params.values()
                )

                can_satisfy = False
                if impl_param.kind in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                ):
                    can_satisfy = proto_has_var_positional or proto_has_var_keyword
                elif impl_param.kind == inspect.Parameter.KEYWORD_ONLY:
                    can_satisfy = proto_has_var_keyword

                if not can_satisfy:
                    errors.append(
                        f"  - '{param_name}': implementation requires this param "
                        f"but protocol doesn't provide it"
                    )

    return errors


def implements(
    *protocols: type,
    signature_check: Literal["error", "warn", "skip"] = "warn",
    allow_inherited: bool = False,
):
    """Decorator to declare and validate protocol implementations.

    Validates members exist (in class body by default) and optionally checks
    signature compatibility. Stores validated protocols in cls.__protocols__.

    Args:
        *protocols: Protocol classes to implement.
        signature_check: "error"=raise, "warn"=warning, "skip"=no check.
        allow_inherited: Accept inherited implementations (default: require in class body).

    Raises:
        TypeError: Required member missing.
        SignatureMismatchError: If signature_check="error" and mismatch.

    Example:
        @implements(Serializable, signature_check="error")
        class MyModel:
            def to_dict(self, **kwargs): return {"id": self.id}
    """

    def decorator(cls):
        all_signature_errors = []

        # Validate that all protocol members are defined in class body
        for protocol in protocols:
            # Get protocol members from protocol class annotations
            protocol_members = {}
            for name, obj in inspect.getmembers(protocol):
                if name.startswith("_"):
                    continue
                # Include methods, properties, classmethods
                if callable(obj) or isinstance(obj, (property, classmethod)):
                    protocol_members[name] = obj

            # Check each required member exists
            for member_name, protocol_member in protocol_members.items():
                # Check if member is in class body or inherited (based on allow_inherited)
                # For Pydantic models, also check __annotations__ for fields
                in_class_body = member_name in cls.__dict__

                # For Pydantic models, check if it's a field annotation
                if not in_class_body and hasattr(cls, "__annotations__"):
                    in_class_body = member_name in cls.__annotations__

                # Check if member exists anywhere (including inherited)
                has_member = hasattr(cls, member_name)

                if allow_inherited:
                    # When inheritance is allowed, just check the member exists
                    if not has_member:
                        protocol_name = protocol.__name__
                        raise TypeError(
                            f"{cls.__name__} declares @implements({protocol_name}) but "
                            f"'{member_name}' is not defined or inherited"
                        )
                else:
                    # Strict mode: require member in class body
                    if not in_class_body:
                        protocol_name = protocol.__name__
                        raise TypeError(
                            f"{cls.__name__} declares @implements({protocol_name}) but does not "
                            f"define '{member_name}' in its class body. "
                            f"Use allow_inherited=True to accept inherited implementations."
                        )

                # Signature checking (if enabled and member exists)
                if signature_check != "skip":
                    # Get the actual implementation (from class body or inherited)
                    if in_class_body:
                        impl_member = cls.__dict__.get(member_name)
                    else:
                        impl_member = getattr(cls, member_name, None)

                    if impl_member is None and hasattr(cls, "__annotations__"):
                        # Pydantic field - skip signature check (it's a field, not method)
                        continue

                    # Get signatures for comparison
                    proto_params = _get_signature_params(protocol_member)
                    impl_params = _get_signature_params(impl_member)

                    # Only check if both have extractable signatures
                    if proto_params is not None and impl_params is not None:
                        errors = _check_signature_compatibility(
                            proto_params,
                            impl_params,
                        )
                        if errors:
                            error_msg = (
                                f"{cls.__name__}.{member_name} signature incompatible "
                                f"with {protocol.__name__}.{member_name}:\n" + "\n".join(errors)
                            )
                            all_signature_errors.append(error_msg)

        # Handle signature errors based on signature_check mode
        if all_signature_errors:
            full_message = "\n\n".join(all_signature_errors)
            if signature_check == "error":
                raise SignatureMismatchError(full_message)
            elif signature_check == "warn":
                warnings.warn(full_message, stacklevel=2)

        cls.__protocols__ = protocols
        return cls

    return decorator
