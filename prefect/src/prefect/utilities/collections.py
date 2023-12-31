"""
Utilities for complex operations on Python collections
"""
import itertools
from collections import OrderedDict, defaultdict
from collections.abc import Iterator as IteratorABC
from collections.abc import Sequence, Set
from dataclasses import dataclass, fields, is_dataclass
from functools import partial
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    Iterable,
    Iterator,
    List,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)
from unittest.mock import Mock

import pydantic
import prefect


T = TypeVar("T")
KT = TypeVar("KT")
VT = TypeVar("VT")


def dict_to_flatdict(
    dct: Dict[KT, Union[Any, Dict[KT, Any]]], _parent: Tuple[KT, ...] = None
) -> Dict[Tuple[KT, ...], Any]:
    """Converts a (nested) dictionary to a flattened representation.

    Each key of the flat dict will be a CompoundKey tuple containing the "chain of keys"
    for the corresponding value.

    Args:
        dct (dict): The dictionary to flatten
        _parent (Tuple, optional): The current parent for recursion

    Returns:
        A flattened dict of the same type as dct
    """
    typ = cast(Type[Dict[Tuple[KT, ...], Any]], type(dct))
    items: List[Tuple[Tuple[KT, ...], Any]] = []
    parent = _parent or tuple()

    for k, v in dct.items():
        k_parent = tuple(parent + (k,))
        if isinstance(v, dict):
            items.extend(dict_to_flatdict(v, _parent=k_parent).items())
        else:
            items.append((k_parent, v))
    return typ(items)


def flatdict_to_dict(
    dct: Dict[Tuple[KT, ...], VT]
) -> Dict[KT, Union[VT, Dict[KT, VT]]]:
    """Converts a flattened dictionary back to a nested dictionary.

    Args:
        dct (dict): The dictionary to be nested. Each key should be a tuple of keys
            as generated by `dict_to_flatdict`

    Returns
        A nested dict of the same type as dct
    """
    typ = type(dct)
    result = cast(Dict[KT, Union[VT, Dict[KT, VT]]], typ())
    for key_tuple, value in dct.items():
        current_dict = result
        for prefix_key in key_tuple[:-1]:
            # Build nested dictionaries up for the current key tuple
            # Use `setdefault` in case the nested dict has already been created
            current_dict = current_dict.setdefault(prefix_key, typ())  # type: ignore
        # Set the value
        current_dict[key_tuple[-1]] = value

    return result


T = TypeVar("T")


def ensure_iterable(obj: Union[T, Iterable[T]]) -> Iterable[T]:
    if isinstance(obj, Sequence) or isinstance(obj, Set):
        return obj
    obj = cast(T, obj)  # No longer in the iterable case
    return [obj]


def listrepr(objs: Iterable, sep=" ") -> str:
    return sep.join(repr(obj) for obj in objs)


def extract_instances(
    objects: Iterable,
    types: Union[Type[T], Tuple[Type[T], ...]] = object,
) -> Union[List[T], Dict[Type[T], T]]:
    """
    Extract objects from a file and returns a dict of type -> instances

    Args:
        objects: An iterable of objects
        types: A type or tuple of types to extract, defaults to all objects

    Returns:
        If a single type is given: a list of instances of that type
        If a tuple of types is given: a mapping of type to a list of instances
    """
    types = ensure_iterable(types)

    # Create a mapping of type -> instance from the exec values
    ret = defaultdict(list)

    for o in objects:
        # We iterate here so that the key is the passed type rather than type(o)
        for type_ in types:
            if isinstance(o, type_):
                ret[type_].append(o)

    if len(types) == 1:
        return ret[types[0]]

    return ret


def batched_iterable(iterable: Iterable[T], size: int) -> Iterator[Tuple[T, ...]]:
    """
    Yield batches of a certain size from an iterable

    Args:
        iterable (Iterable): An iterable
        size (int): The batch size to return

    Yields:
        tuple: A batch of the iterable
    """
    it = iter(iterable)
    while True:
        batch = tuple(itertools.islice(it, size))
        if not batch:
            break
        yield batch


@dataclass
class Quote(Generic[T]):
    """
    Simple wrapper to mark an expression as a different type so it will not be coerced
    by Prefect. For example, if you want to return a state from a flow without having
    the flow assume that state.
    """

    expr: T

    def unquote(self) -> T:
        return self.expr


def quote(expr: T) -> Quote[T]:
    """
    Create a `Quote` object

    Examples:
        >>> from prefect.utilities.collections import quote
        >>> x = quote(1)
        >>> x.unquote()
        1
    """
    return Quote(expr)


async def visit_collection(
    expr, visit_fn: Callable[[Any], Awaitable[Any]], return_data: bool = False
):
    """
    This function visits every element of an arbitrary Python collection and
    applies `visit_fn` to each element. If `return_data=True`, a copy of the
    data structure containing the results of `visit_fn` is returned. Note that
    `return_data=True` may be slower due to the need to copy every object.

    Args:
        expr (Any): a Python object or expression
        visit_fn (Callable[[Any], Awaitable[Any]]): an async function that
            will be applied to every non-collection element of expr.
        return_data (bool): if `True`, a copy of `expr` containing data modified
            by `visit_fn` will be returned. This is slower than `return_data=False`
            (the default).
    """
    # package the provided arguments for recursive calls
    recurse = partial(visit_collection, visit_fn=visit_fn, return_data=return_data)

    # Get the expression type; treat iterators like lists
    typ = list if isinstance(expr, IteratorABC) else type(expr)
    typ = cast(type, typ)  # mypy treats this as 'object' otherwise and complains

    # do not visit mock objects
    if isinstance(expr, Mock):
        return expr if return_data else None

    elif typ in (list, tuple, set):
        result = [await recurse(o) for o in expr]
        return typ(result) if return_data else None

    elif typ in (dict, OrderedDict):
        assert isinstance(expr, (dict, OrderedDict))  # typecheck assertion
        result = [[await recurse(k), await recurse(v)] for k, v in expr.items()]
        return typ(result) if return_data else None

    elif is_dataclass(expr) and not isinstance(expr, type):
        result = {f.name: await recurse(getattr(expr, f.name)) for f in fields(expr)}
        return typ(**result) if return_data else None

    elif (
        # Recurse into Pydantic models but do _not_ do so for states/datadocs
        isinstance(expr, pydantic.BaseModel)
        and not isinstance(expr, prefect.orion.schemas.states.State)
        and not isinstance(expr, prefect.orion.schemas.data.DataDocument)
    ):
        result = {f: await recurse(getattr(expr, f)) for f in expr.__fields__}
        return typ(**result) if return_data else None

    else:
        result = await visit_fn(expr)
        return result if return_data else None
