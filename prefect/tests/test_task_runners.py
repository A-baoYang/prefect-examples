import sys
import time
from contextlib import contextmanager
from unittest.mock import MagicMock
from uuid import uuid4

import anyio
import cloudpickle
import distributed
import pytest

from prefect import flow, task
from prefect.context import get_run_context
from prefect.task_runners import BaseTaskRunner, DaskTaskRunner, SequentialTaskRunner
from prefect.futures import PrefectFuture
from prefect.orion.schemas.core import TaskRun
from prefect.orion.schemas.data import DataDocument
from prefect.orion.schemas.states import State, StateType


@contextmanager
def dask_task_runner_with_existing_cluster():
    """
    Generate a dask task runner that's connected to a local cluster
    """
    with distributed.LocalCluster(n_workers=2) as cluster:
        with distributed.Client(cluster) as client:
            address = client.scheduler.address
            yield DaskTaskRunner(address=address)


@contextmanager
def dask_task_runner_with_process_pool():
    yield DaskTaskRunner(cluster_kwargs={"processes": True})


@pytest.fixture
def distributed_client_init(monkeypatch):
    mock = MagicMock()

    class DistributedClient(distributed.Client):
        """
        A patched `distributed.Client` so we can inspect calls to `__init__`
        """

        def __init__(self, *args, **kwargs):
            mock(*args, **kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("distributed.Client", DistributedClient)
    return mock


@pytest.fixture
def task_runner(request):
    """
    An indirect fixture that expects to receive one of the following
    - task_runner instance
    - task_runner type
    - callable generator that yields an task_runner instance

    Returns an task_runner instance that can be used in the test
    """
    if isinstance(request.param, BaseTaskRunner):
        yield request.param

    elif isinstance(request.param, type) and issubclass(request.param, BaseTaskRunner):
        yield request.param()

    elif callable(request.param):
        with request.param() as task_runner:
            yield task_runner

    else:
        raise TypeError(
            "Received invalid task_runner parameter. Expected task runner type, "
            f"instance, or callable generator. Received {type(request.param).__name__}"
        )


parameterize_with_all_task_runners = pytest.mark.parametrize(
    "task_runner",
    [
        DaskTaskRunner,
        SequentialTaskRunner,
        dask_task_runner_with_existing_cluster,
        dask_task_runner_with_process_pool,
    ],
    indirect=True,
)


parameterize_with_parallel_task_runners = pytest.mark.parametrize(
    "task_runner",
    [
        DaskTaskRunner,
        dask_task_runner_with_existing_cluster,
    ],
    indirect=True,
)


parameterize_with_sequential_task_runners = pytest.mark.parametrize(
    "task_runner",
    [SequentialTaskRunner],
    indirect=True,
)


async def test_task_runner_cannot_be_started_while_running():
    async with SequentialTaskRunner().start() as task_runner:
        with pytest.raises(RuntimeError, match="already started"):
            async with task_runner.start():
                pass


@parameterize_with_all_task_runners
def test_flow_run_by_task_runner(task_runner):
    @task
    def task_a():
        return "a"

    @task
    def task_b():
        return "b"

    @task
    def task_c(b):
        return b + "c"

    @flow(version="test", task_runner=task_runner)
    def test_flow():
        a = task_a()
        b = task_b()
        c = task_c(b)
        return a, b, c

    a, b, c = test_flow().result()

    assert (a.result(), b.result(), c.result()) == (
        "a",
        "b",
        "bc",
    )


@parameterize_with_all_task_runners
def test_failing_flow_run_by_task_runner(task_runner):
    @task
    def task_a():
        raise RuntimeError("This task fails!")

    @task
    def task_b():
        raise ValueError("This task fails and passes data downstream!")

    @task
    def task_c(b):
        # This task attempts to use the upstream data and should fail too
        return b + "c"

    @flow(version="test", task_runner=task_runner)
    def test_flow():
        a = task_a()
        b = task_b()
        c = task_c(b)
        d = task_c(c)

        return a, b, c, d

    state = test_flow()

    assert state.is_failed()
    a, b, c, d = state.result(raise_on_failure=False)
    with pytest.raises(RuntimeError, match="This task fails!"):
        a.result()
    with pytest.raises(ValueError, match="This task fails and passes data downstream"):
        b.result()

    assert c.is_pending()
    assert c.name == "NotReady"
    assert (
        f"Upstream task run '{b.state_details.task_run_id}' did not reach a 'COMPLETED' state"
        in c.message
    )

    assert d.is_pending()
    assert d.name == "NotReady"
    assert (
        f"Upstream task run '{c.state_details.task_run_id}' did not reach a 'COMPLETED' state"
        in d.message
    )


@pytest.mark.parametrize(
    "parent_task_runner,child_task_runner",
    [
        (SequentialTaskRunner(), DaskTaskRunner()),
        (DaskTaskRunner(), SequentialTaskRunner()),
        # Select a random port for the child task_runner so it does not collide with the
        # parent. Dask will detect collisions and pick a new port, but it will display
        # a warning
        (DaskTaskRunner(), DaskTaskRunner(cluster_kwargs={"dashboard_address": 8790})),
    ],
)
def test_subflow_run_nested_task_runner_compatibility(
    parent_task_runner, child_task_runner
):
    @task
    def task_a():
        return "a"

    @task
    def task_b():
        return "b"

    @task
    def task_c(b):
        return b + "c"

    @flow(version="test", task_runner=parent_task_runner)
    def parent_flow():
        assert get_run_context().task_runner is parent_task_runner
        a = task_a()
        b = task_b()
        c = task_c(b)
        d = child_flow(c)
        return a, b, c, d

    @flow(version="test", task_runner=child_task_runner)
    def child_flow(c):
        assert get_run_context().task_runner is child_task_runner
        a = task_a()
        b = task_b()
        c = task_c(b)
        d = task_c(c)
        return a, b, c, d

    a, b, c, d = parent_flow().result()
    # parent
    assert (a.result(), b.result(), c.result()) == (
        "a",
        "b",
        "bc",
    )
    # child
    a, b, c, d = d.result()
    assert (a.result(), b.result(), c.result(), d.result()) == ("a", "b", "bc", "bcc")


class TestTaskRunnerParallelism:
    """
    These tests use a simple canary file to indicate if a items in a flow have run
    sequentially or concurrently.

    foo writes 'foo' to the file after sleeping for a little bit
    bar writes 'bar' to the file immediately

    If they run concurrently, 'foo' will be the final content of the file
    If they run sequentially, 'bar' will be the final content of the file
    """

    # Amount of time to sleep before writing 'foo'
    # A larger value will decrease brittleness but increase test times
    SLEEP_TIME = 0.25 if sys.platform == "darwin" else 1.5

    @pytest.fixture
    def tmp_file(self, tmp_path):
        tmp_file = tmp_path / "canary.txt"
        tmp_file.touch()
        return tmp_file

    @parameterize_with_sequential_task_runners
    def test_sync_tasks_run_sequentially_with_sequential_task_runners(
        self, task_runner, tmp_file
    ):
        @task
        def foo():
            time.sleep(self.SLEEP_TIME)
            tmp_file.write_text("foo")

        @task
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo()
            bar()

        test_flow().result()

        assert tmp_file.read_text() == "bar"

    @parameterize_with_parallel_task_runners
    def test_sync_tasks_run_concurrently_with_parallel_task_runners(
        self, task_runner, tmp_file
    ):
        @task
        def foo():
            time.sleep(self.SLEEP_TIME)
            tmp_file.write_text("foo")

        @task
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo()
            bar()

        test_flow().result()

        assert tmp_file.read_text() == "foo"

    @parameterize_with_sequential_task_runners
    async def test_async_tasks_run_sequentially_with_sequential_task_runners(
        self, task_runner, tmp_file
    ):
        @task
        async def foo():
            await anyio.sleep(self.SLEEP_TIME)
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo()
            await bar()

        (await test_flow()).result()

        assert tmp_file.read_text() == "bar"

    @parameterize_with_parallel_task_runners
    async def test_async_tasks_run_concurrently_with_parallel_task_runners(
        self, task_runner, tmp_file
    ):
        @task
        async def foo():
            await anyio.sleep(self.SLEEP_TIME)
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo()
            await bar()

        (await test_flow()).result()

        assert tmp_file.read_text() == "foo"

    @parameterize_with_all_task_runners
    async def test_async_tasks_run_concurrently_with_task_group_with_all_task_runners(
        self, task_runner, tmp_file
    ):
        @task
        async def foo():
            await anyio.sleep(self.SLEEP_TIME)
            tmp_file.write_text("foo")

        @task
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            async with anyio.create_task_group() as tg:
                tg.start_soon(foo)
                tg.start_soon(bar)

        (await test_flow()).result()

        assert tmp_file.read_text() == "foo"

    @parameterize_with_all_task_runners
    def test_sync_subflows_run_sequentially_with_all_task_runners(
        self, task_runner, tmp_file
    ):
        @flow
        def foo():
            time.sleep(self.SLEEP_TIME)
            tmp_file.write_text("foo")

        @flow
        def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        def test_flow():
            foo()
            bar()

        test_flow().result()

        assert tmp_file.read_text() == "bar"

    @parameterize_with_all_task_runners
    async def test_async_subflows_run_sequentially_with_all_task_runners(
        self, task_runner, tmp_file
    ):
        @flow
        async def foo():
            await anyio.sleep(self.SLEEP_TIME)
            tmp_file.write_text("foo")

        @flow
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            await foo()
            await bar()

        (await test_flow()).result()

        assert tmp_file.read_text() == "bar"

    @parameterize_with_all_task_runners
    async def test_async_subflows_run_concurrently_with_task_group_with_all_task_runners(
        self, task_runner, tmp_file
    ):
        @flow
        async def foo():
            await anyio.sleep(self.SLEEP_TIME)
            tmp_file.write_text("foo")

        @flow
        async def bar():
            tmp_file.write_text("bar")

        @flow(version="test", task_runner=task_runner)
        async def test_flow():
            async with anyio.create_task_group() as tg:
                tg.start_soon(foo)
                tg.start_soon(bar)

        (await test_flow()).result()

        assert tmp_file.read_text() == "foo"


@parameterize_with_all_task_runners
async def test_is_pickleable_after_start(task_runner):
    """
    The task_runner must be picklable as it is attached to `PrefectFuture` objects
    """
    if isinstance(task_runner, DaskTaskRunner):
        # We must set the dask client as the default for it to be unpicklable in the
        # main process
        task_runner.client_kwargs["set_as_default"] = True

    async with task_runner.start():
        pickled = cloudpickle.dumps(task_runner)
        unpickled = cloudpickle.loads(pickled)
        assert isinstance(unpickled, type(task_runner))


@parameterize_with_all_task_runners
async def test_submit_and_wait(task_runner):
    task_run = TaskRun(flow_run_id=uuid4(), task_key="foo", dynamic_key="bar")

    async def fake_orchestrate_task_run(example_kwarg):
        return State(
            type=StateType.COMPLETED,
            data=DataDocument.encode("json", example_kwarg),
        )

    async with task_runner.start():
        fut = await task_runner.submit(
            task_run=task_run,
            run_fn=fake_orchestrate_task_run,
            run_kwargs=dict(example_kwarg=1),
        )
        assert isinstance(fut, PrefectFuture), "submit should return a future"
        assert fut.task_run == task_run, "the future should have the same task run"
        assert fut.asynchronous == True

        state = await task_runner.wait(fut)
        assert isinstance(state, State), "wait should return a state"
        assert state.result() == 1


class TestDaskTaskRunner:
    async def test_connect_to_running_cluster(self, distributed_client_init):
        with distributed.Client(processes=False, set_as_default=False) as client:
            address = client.scheduler.address
            task_runner = DaskTaskRunner(address=address)
            assert task_runner.address == address

            async with task_runner.start():
                pass

            distributed_client_init.assert_called_with(
                address, asynchronous=True, **task_runner.client_kwargs
            )

    async def test_start_local_cluster(self, distributed_client_init):
        task_runner = DaskTaskRunner(cluster_kwargs={"processes": False})
        assert task_runner.cluster_class == None, "Default is delayed for import"
        assert task_runner.cluster_kwargs == {"processes": False}

        async with task_runner.start():
            pass

        assert task_runner.cluster_class == distributed.LocalCluster

        distributed_client_init.assert_called_with(
            task_runner._cluster, asynchronous=True, **task_runner.client_kwargs
        )

    async def test_adapt_kwargs(self, monkeypatch):
        adapt_kwargs = {"minimum": 1, "maximum": 1}
        monkeypatch.setattr("distributed.LocalCluster.adapt", MagicMock())

        task_runner = DaskTaskRunner(
            cluster_kwargs={"processes": False, "n_workers": 0},
            adapt_kwargs=adapt_kwargs,
        )
        assert task_runner.adapt_kwargs == adapt_kwargs

        async with task_runner.start():
            pass

        distributed.LocalCluster.adapt.assert_called_once_with(**adapt_kwargs)

    async def test_client_kwargs(self, distributed_client_init):
        task_runner = DaskTaskRunner(
            client_kwargs={"set_as_default": True, "connection_limit": 100},
        )
        assert task_runner.client_kwargs == {
            "set_as_default": True,
            "connection_limit": 100,
        }

        async with task_runner.start():
            pass

        distributed_client_init.assert_called_with(
            task_runner._cluster, asynchronous=True, **task_runner.client_kwargs
        )

    async def test_cluster_class_string_is_imported(self):
        task_runner = DaskTaskRunner(
            cluster_class="distributed.deploy.spec.SpecCluster",
        )
        assert task_runner.cluster_class == distributed.deploy.spec.SpecCluster

    async def test_cluster_class_and_kwargs(self):

        init_method = MagicMock()

        # Define a custom cluster class that just calls a mock; wrap `LocalCluster` so
        # we don't have to actually implement anything
        class TestCluster(distributed.LocalCluster):
            def __init__(self, *args, **kwargs):
                init_method(*args, **kwargs)
                return super().__init__(asynchronous=True)

        task_runner = DaskTaskRunner(
            cluster_class=TestCluster,
            cluster_kwargs={"some_kwarg": "some_val"},
        )
        assert task_runner.cluster_class == TestCluster

        async with task_runner.start():
            pass

        init_method.assert_called_once()
        _, kwargs = init_method.call_args
        assert kwargs == {"some_kwarg": "some_val", "asynchronous": True}

    def test_cannot_specify_both_address_and_cluster_class(self):
        with pytest.raises(ValueError):
            DaskTaskRunner(
                address="localhost:8787",
                cluster_class=distributed.LocalCluster,
            )

    def test_cannot_specify_asynchronous(self):
        with pytest.raises(ValueError, match="`client_kwargs`"):
            DaskTaskRunner(client_kwargs={"asynchronous": True})

        with pytest.raises(ValueError, match="`cluster_kwargs`"):
            DaskTaskRunner(cluster_kwargs={"asynchronous": True})

    def test_nested_dask_task_runners_warn_on_port_collision_but_succeeds(self):
        @task
        def idenitity(x):
            return x

        @flow(version="test", task_runner=DaskTaskRunner())
        def parent_flow():
            a = idenitity("a")
            return child_flow(a), a

        @flow(version="test", task_runner=DaskTaskRunner())
        def child_flow(a):
            return idenitity(a).wait().result()

        with pytest.warns(
            UserWarning,
            match="Port .* is already in use",
        ):
            task_state, subflow_state = parent_flow().result()
            assert task_state.result() == "a"
            assert subflow_state.result() == "a"
