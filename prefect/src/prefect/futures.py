"""
Futures represent the execution of a task and allow retrieval of the task run's state.

This module contains the definition for futures as well as utilities for resolving
futures in nested data structures.
"""
from typing import (
    TYPE_CHECKING,
    Any,
    Union,
    Optional,
    overload,
    TypeVar,
    Generic,
    Callable,
    cast,
    Awaitable,
)
from typing_extensions import Literal


import prefect
from prefect.client import OrionClient, inject_client
from prefect.orion.schemas.core import TaskRun
from prefect.orion.schemas.states import State
from prefect.utilities.asyncio import sync, A, Async, Sync, sync_compatible
from prefect.utilities.collections import visit_collection

if TYPE_CHECKING:
    from prefect.task_runners import BaseTaskRunner


R = TypeVar("R")


class PrefectFuture(Generic[R, A]):
    """
    Represents the result of a computation happening in a task runner.

    When tasks are called, they are submitted to a task runner which creates a future
    for access to the state and result of the task.

    Examples:
        Define a task that returns a string

        >>> from prefect import flow, task
        >>> @task
        >>> def my_task() -> str:
        >>>     return "hello"

        Calls of this task in a flow will return a future

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()  # PrefectFuture[str, Sync] includes result type
        >>>     future.run_id  # UUID for the task run

        Wait for the task to complete

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()
        >>>     final_state = future.wait()

        Wait for a task to complete and retrieve its result

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()
        >>>     state = future.wait()
        >>>     result = state.result()
        >>>     assert result == "hello"

        Retrieve the state of a task without waiting for completion

        >>> @flow
        >>> def my_flow():
        >>>     future = my_task()
        >>>     state = future.get_state()
    """

    def __init__(
        self,
        task_run: TaskRun,
        task_runner: "BaseTaskRunner",
        asynchronous: A = True,
        _final_state: State[R] = None,  # Exposed for testing
    ) -> None:
        self.task_run = task_run
        self.run_id = task_run.id
        self.asynchronous = asynchronous
        self._final_state = _final_state
        self._exception: Optional[Exception] = None
        self._task_runner = task_runner

    @overload
    def wait(
        self: "PrefectFuture[R, Async]", timeout: None = None
    ) -> Awaitable[State[R]]:
        ...

    @overload
    def wait(self: "PrefectFuture[R, Sync]", timeout: None = None) -> State[R]:
        ...

    @overload
    def wait(
        self: "PrefectFuture[R, Async]", timeout: float
    ) -> Awaitable[Optional[State[R]]]:
        ...

    @overload
    def wait(self: "PrefectFuture[R, Sync]", timeout: float) -> Optional[State[R]]:
        ...

    def wait(self, timeout=None):
        """
        Wait for the run to finish and return the final state

        If the timeout is reached before the run reaches a final state,
        `None` is returned.
        """
        if self.asynchronous:
            return self._wait(timeout=timeout)
        else:
            # type checking cannot handle the overloaded timeout passing
            return sync(self._wait, timeout=timeout)  # type: ignore

    @overload
    async def _wait(self, timeout: None = None) -> State[R]:
        ...

    @overload
    async def _wait(self, timeout: float) -> Optional[State[R]]:
        ...

    async def _wait(self, timeout=None):
        """
        Async implementation for `wait`
        """
        if self._final_state:
            return self._final_state

        self._final_state = await self._task_runner.wait(self, timeout)
        return self._final_state

    @overload
    def get_state(
        self: "PrefectFuture[R, Async]", client: OrionClient = None
    ) -> Awaitable[State[R]]:
        ...

    @overload
    def get_state(
        self: "PrefectFuture[R, Sync]", client: OrionClient = None
    ) -> State[R]:
        ...

    def get_state(self, client: OrionClient = None):
        """
        Wait for the run to finish and return the final state

        If the timeout is reached before the run reaches a final state,
        `None` is returned.
        """
        if self.asynchronous:
            return cast(Awaitable[State[R]], self._get_state(client=client))
        else:
            return cast(State[R], sync(self._get_state, client=client))

    @inject_client
    async def _get_state(self, client: OrionClient = None) -> State[R]:
        assert client is not None  # always injected

        task_run = await client.read_task_run(self.run_id)

        if not task_run:
            raise RuntimeError("Future has no associated task run in the server.")

        # Update the task run reference
        self.task_run = task_run
        return task_run.state

    def __hash__(self) -> int:
        return hash(self.run_id)

    def __repr__(self) -> str:
        return f"PrefectFuture({self.task_run.name!r})"


async def resolve_futures_to_data(
    expr: Union[PrefectFuture[R, Any], Any]
) -> Union[R, Any]:
    """
    Given a Python built-in collection, recursively find `PrefectFutures` and build a
    new collection with the same structure with futures resolved to their results.
    Resolving futures to their results may wait for execution to complete and require
    communication with the API.

    Unsupported object types will be returned without modification.
    """

    async def visit_fn(expr):
        if isinstance(expr, PrefectFuture):
            return (await expr._wait()).result(raise_on_failure=False)
        else:
            return expr

    return await visit_collection(expr, visit_fn=visit_fn, return_data=True)


async def resolve_futures_to_states(
    expr: Union[PrefectFuture[R, Any], Any]
) -> Union[State[R], Any]:
    """
    Given a Python built-in collection, recursively find `PrefectFutures` and build a
    new collection with the same structure with futures resolved to their final states.
    Resolving futures to their final states may wait for execution to complete.

    Unsupported object types will be returned without modification.
    """

    async def visit_fn(expr):
        if isinstance(expr, PrefectFuture):
            return await expr._wait()
        else:
            return expr

    return await visit_collection(expr, visit_fn=visit_fn, return_data=True)


def call_repr(__fn: Callable, *args: Any, **kwargs: Any) -> str:
    """
    Generate a repr for a function call as "fn_name(arg_value, kwarg_name=kwarg_value)"
    """

    name = __fn.__name__

    # TODO: If this computation is concerningly expensive, we can iterate checking the
    #       length at each arg or avoid calling `repr` on args with large amounts of
    #       data
    call_args = ", ".join(
        [repr(arg) for arg in args]
        + [f"{key}={repr(val)}" for key, val in kwargs.items()]
    )

    # Enforce a maximum length
    if len(call_args) > 100:
        call_args = call_args[:100] + "..."

    return f"{name}({call_args})"
