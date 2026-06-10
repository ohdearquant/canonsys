"""Utility functions for spec adapters."""

from __future__ import annotations

import re
import types
from functools import reduce
from typing import Annotated, Any, ForwardRef, Union, get_args, get_origin
from uuid import UUID


def _resolve_forward_ref(fwd: ForwardRef) -> dict[str, Any]:
    """Handle ForwardRef annotations (from 'from __future__ import annotations').

    Parses the string representation to extract type info for DDL generation.
    FK[Model] -> Annotated[UUID, FKMeta(model_name)], Vector[dim] -> list[float], etc.
    """
    from kron.types import FKMeta, VectorMeta

    arg = fwd.__forward_arg__
    nullable = "| None" in arg or "None |" in arg

    # FK[Model] or FK[Model] | None -> Annotated[UUID, FKMeta(model_name)]
    fk_match = re.search(r"FK\[(\w+)\]", arg)
    if fk_match:
        model_name = fk_match.group(1)
        base_type = Annotated[UUID, FKMeta(model_name)]
        return {"base_type": base_type, "nullable": nullable, "listable": False}

    # Vector[dim] -> Annotated[list[float], VectorMeta(dim)]
    vec_match = re.search(r"Vector\[(\d+)\]", arg)
    if vec_match:
        dim = int(vec_match.group(1))
        base_type = Annotated[list[float], VectorMeta(dim)]
        return {"base_type": base_type, "nullable": nullable, "listable": False}

    # Default: treat as generic type (will map to TEXT in SQL)
    return {"base_type": str, "nullable": nullable, "listable": False}


def resolve_annotation_to_base_types(annotation: Any) -> dict[str, Any]:
    """Resolve an annotation to its base types, detecting nullable and listable.

    Args:
        annotation: Type annotation to resolve (may include Optional, list, etc.)

    Returns:
        Dict with keys:
            - base_type: The innermost type
            - nullable: Whether None is allowed
            - listable: Whether it's a list type
    """
    # Handle ForwardRef (from 'from __future__ import annotations')
    if isinstance(annotation, ForwardRef):
        return _resolve_forward_ref(annotation)

    def resolve_nullable_inner_type(_anno: Any) -> tuple[bool, Any]:
        origin = get_origin(_anno)

        if origin is type(None):
            return True, type(None)

        if origin in (type(int | str), types.UnionType) or origin is Union:
            args = get_args(_anno)
            non_none_args = [a for a in args if a is not type(None)]
            if len(args) != len(non_none_args):
                if len(non_none_args) == 1:
                    return True, non_none_args[0]
                if non_none_args:
                    return True, reduce(lambda a, b: a | b, non_none_args)
            return False, _anno

        return False, _anno

    def resolve_listable_element_type(_anno: Any) -> Any:
        origin = get_origin(_anno)

        if origin is list:
            args = get_args(_anno)
            if args:
                return True, args[0]
            return True, Any

        return False, _anno

    _null, _inner = resolve_nullable_inner_type(annotation)
    _list, _elem = resolve_listable_element_type(_inner)

    return {
        "base_type": _elem,
        "nullable": _null,
        "listable": _list,
    }
