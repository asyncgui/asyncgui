__all__ = (
    'ExceptionGroup', 'BaseExceptionGroup', 'InvalidStateError', 'Cancelled',
    'Aw_or_Task', 'start', 'Task', 'TaskState', 'current_task', 'open_cancel_scope', 'CancelScope',
    'sleep_forever', 'Event', 'disable_cancellation', 'dummy_task', 'check_cancellation',
    'wait_all', 'wait_any', 'run_and_cancelling', 'OnetimeBox',
)
import types
import typing as T
from inspect import getcoroutinestate, CORO_CREATED, CORO_SUSPENDED, isawaitable
import sys
import itertools
from functools import cached_property, partial
import enum
from contextlib import asynccontextmanager

# -----------------------------------------------------------------------------
# Core
# -----------------------------------------------------------------------------

if sys.version_info < (3, 11):
    from exceptiongroup import BaseExceptionGroup, ExceptionGroup
else:
    BaseExceptionGroup = BaseExceptionGroup
    ExceptionGroup = ExceptionGroup

potential_bug_msg = '''
This may be a bug of this library. Please make a minimal code that reproduces the bug, and open an issue at the GitHub
repository. (https://github.com/gottadiveintopython/asyncgui).
'''


class InvalidStateError(Exception):
    """The operation is not allowed in the current state."""


class _Cancelled(BaseException):
    @cached_property
    def level(self) -> int:
        return self.args[0]


Cancelled = (_Cancelled, GeneratorExit, )


class TaskState(enum.Flag):
    CREATED = enum.auto()
    '''CORO_CREATED'''

    STARTED = enum.auto()
    '''CORO_RUNNING or CORO_SUSPENDED'''

    CANCELLED = enum.auto()
    '''CORO_CLOSED by 'Task.cancel()' or an unhandled exception'''

    FINISHED = enum.auto()
    '''CORO_CLOSED (finished)'''

    ENDED = CANCELLED | FINISHED


class Task:
    __slots__ = (
        'name', '_uid', '_root_coro', '_state', '_result', '_on_end',
        '_exc_caught', '_suppresses_exc',
        '_cancel_disabled', '_cancel_depth', '_cancel_level',
    )

    _uid_iter = itertools.count()

    def __init__(self, awaitable):
        if not isawaitable(awaitable):
            raise ValueError(str(awaitable) + " is not awaitable.")
        self._uid = next(self._uid_iter)
        self.name = ""
        self._cancel_disabled = 0
        self._root_coro = self._wrapper(awaitable)
        self._state = TaskState.CREATED
        self._on_end = None
        self._cancel_depth = 0
        self._cancel_level = None
        self._exc_caught = None
        self._suppresses_exc = False

    def __str__(self):
        return f'Task(state={self._state.name}, uid={self._uid}, name={self.name!r})'

    @property
    def uid(self) -> int:
        return self._uid

    @property
    def root_coro(self) -> T.Coroutine:
        return self._root_coro

    @property
    def state(self) -> TaskState:
        return self._state

    @property
    def finished(self) -> bool:
        return self._state is TaskState.FINISHED

    @property
    def cancelled(self) -> bool:
        return self._state is TaskState.CANCELLED

    @property
    def result(self) -> T.Any:
        '''Result of the task. If the task hasn't finished yet,
        InvalidStateError will be raised.
        '''
        state = self._state
        if state is TaskState.FINISHED:
            return self._result
        elif state is TaskState.CANCELLED:
            raise InvalidStateError(f"{self} was cancelled")
        else:
            raise InvalidStateError(f"Result of {self} is not ready")

    async def _wrapper(self, awaitable):
        try:
            self._state = TaskState.STARTED
            self._result = await awaitable
        except _Cancelled as e:
            self._state = TaskState.CANCELLED
            e.level == 0, potential_bug_msg
            self._cancel_level == 0, potential_bug_msg
        except Exception as e:
            self._state = TaskState.CANCELLED
            self._exc_caught = e
            if not self._suppresses_exc:
                raise
        except:  # noqa: E722
            self._state = TaskState.CANCELLED
            raise
        else:
            self._state = TaskState.FINISHED
        finally:
            assert self._cancel_depth == 0, potential_bug_msg
            if (on_end := self._on_end) is not None:
                on_end(self)

    def cancel(self, _level=0):
        '''Cancel the task as soon as possible'''
        if self._cancel_level is None:
            self._cancel_level = _level
            state = getcoroutinestate(self._root_coro)
            if state == CORO_SUSPENDED:
                if not self._cancel_disabled:
                    self._actual_cancel()
            elif state == CORO_CREATED:
                self._root_coro.close()
                self._state = TaskState.CANCELLED
        else:
            self._cancel_level = min(self._cancel_level, _level)

    def _actual_cancel(self):
        try:
            # NOTE: _cancel_levelが0の時は末尾の関数呼び出し (self) は省いても良いかもしれない
            self._root_coro.throw(_Cancelled(self._cancel_level))(self)
        except StopIteration:
            pass
        else:
            self._cancel_if_needed()

    # give 'cancel()' an alias so that we can pass a Task instance to `contextlib.closing`
    close = cancel

    @property
    def _cancel_requested(self) -> bool:
        return self._cancel_level is not None

    @property
    def _is_cancellable(self) -> bool:
        '''Whether the task can immediately be cancelled.'''
        return (not self._cancel_disabled) and getcoroutinestate(self._root_coro) == CORO_SUSPENDED

    def _cancel_if_needed(self, getcoroutinestate=getcoroutinestate, CORO_SUSPENDED=CORO_SUSPENDED):
        if (self._cancel_level is None) or self._cancel_disabled or \
                (getcoroutinestate(self._root_coro) != CORO_SUSPENDED):
            pass
        else:
            self._actual_cancel()

    def _step(self, *args, **kwargs):
        coro = self._root_coro
        if getcoroutinestate(coro) != CORO_SUSPENDED:
            return
        try:
            coro.send((args, kwargs, ))(self)
        except StopIteration:
            pass
        else:
            self._cancel_if_needed()

    def _throw_exc(self, exc):
        '''停止中のTaskへ例外を投げる。Taskが停止中ではない場合は :exc:`InvalidStateError` が起こる。'''
        coro = self._root_coro
        if getcoroutinestate(coro) != CORO_SUSPENDED:
            raise InvalidStateError("Throwing an exception to an unstarted/running/closed task is not allowed.")
        try:
            coro.throw(exc)(self)
        except StopIteration:
            pass
        else:
            self._cancel_if_needed()


Aw_or_Task = T.Union[T.Awaitable, Task]


def start(aw: Aw_or_Task) -> Task:
    '''Starts an asyncgui-flavored awaitable or a Task.

    If the argument is a Task, itself will be returned. If it's an awaitable,
    it will be wrapped in a Task, and the Task will be returned.
    '''
    if isawaitable(aw):
        task = Task(aw)
    elif isinstance(aw, Task):
        task = aw
        if task._state is not TaskState.CREATED:
            raise ValueError(f"{task} has already started")
    else:
        raise ValueError("Argument must be either a Task or an awaitable.")

    try:
        task._root_coro.send(None)(task)
    except StopIteration:
        pass
    else:
        task._cancel_if_needed()

    return task


class CancelScope:
    '''(internal)'''
    __slots__ = ('_task', '_depth', 'cancelled_caught', 'cancell_called', )

    def __init__(self, task: Task):
        self._task = task
        self.cancelled_caught = False
        self.cancell_called = False

    def __enter__(self) -> 'CancelScope':
        t = self._task
        t._cancel_depth = self._depth = t._cancel_depth + 1
        return self

    def __exit__(self, exc_type, exc, __):
        # LOAD_FAST
        task = self._task
        level = task._cancel_level
        depth = self._depth

        self._task = None
        task._cancel_depth -= 1
        if level is not None:
            if level == depth:
                task._cancel_level = None
            else:
                assert level < depth, potential_bug_msg
        if exc_type is not _Cancelled:
            return
        level = exc.level
        if level == depth:
            self.cancelled_caught = True
            return True
        else:
            assert level < depth, potential_bug_msg

    @property
    def closed(self) -> bool:
        return self._task is None

    def cancel(self):
        if self.cancell_called:
            return
        self.cancell_called = True
        if not self.closed:
            self._task.cancel(self._depth)


class open_cancel_scope:
    '''(experimental)'''
    __slots__ = ('_scope', )

    async def __aenter__(self) -> T.Awaitable[CancelScope]:
        self._scope = CancelScope(await current_task())
        return self._scope.__enter__()

    async def __aexit__(self, *args):
        return self._scope.__exit__(*args)


@types.coroutine
def current_task(_f=lambda task: task._step(task)) -> T.Awaitable[Task]:
    '''Returns the Task instance corresponding to the caller.'''
    return (yield _f)[0][0]


class disable_cancellation:
    '''
    (experimental)
    Async context manager that protects its code-block from cancellation.

    .. code-block::

        await something      # <- might get cancelled
        async with disable_cancellation():
            await something  # <- never gets cancelled
            await something  # <- never gets cancelled
        await something      # <- might get cancelled
    '''

    __slots__ = ('_task', )

    async def __aenter__(self):
        self._task = task = await current_task()
        task._cancel_disabled += 1

    async def __aexit__(self, *__):
        self._task._cancel_disabled -= 1


async def check_cancellation():
    '''
    (experimental) If the ``.cancel()`` method of the current task has been
    called and the task is not protected from cancellation, cancels the task
    immediately. Otherwise, does nothing.
    '''
    task = await current_task()
    if task._cancel_requested and not task._cancel_disabled:
        await sleep_forever()


@types.coroutine
def sleep_forever(_f=lambda task: None):
    yield _f


dummy_task = Task(sleep_forever())
dummy_task.cancel()
dummy_task.name = r"asyncgui.dummy_task"

# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------


class Event:
    '''
    Equivalent of :class:`asyncio.Event`.

    Difference
    ----------

    :meth:`set` accepts any number of arguments and doesn't use them at all so it can be a callback function of any
    library.

    .. code-block::

        e = Event()
        any_library.register_callback(e.set)
    '''

    __slots__ = ('_flag', '_waiting_tasks', )

    def __init__(self):
        self._flag = False
        self._waiting_tasks = []

    def is_set(self):
        return self._flag

    def set(self, *args, **kwargs):
        if self._flag:
            return
        self._flag = True
        tasks = self._waiting_tasks
        self._waiting_tasks = []
        for t in tasks:
            if t is not None:
                t._step()

    def clear(self):
        self._flag = False

    @types.coroutine
    def wait(self):
        if self._flag:
            return
        try:
            tasks = self._waiting_tasks
            idx = len(tasks)
            yield self._waiting_tasks.append
        finally:
            tasks[idx] = None


async def wait_all(*aws: T.Iterable[Aw_or_Task]) -> T.Awaitable[T.List[Task]]:  # noqa: C901
    '''
    Run multiple tasks concurrently, and wait for all of them to end. When any of them raises an exception,
    the others will be cancelled, and the exception will be propagated to the caller, like Trio's Nursery does.

    Guaranteed Start
    ----------------

    When any of the tasks raises an exception while there are still ones that haven't started yet, they still will
    start (and will be cancelled soon).
    '''
    children = [v if isinstance(v, Task) else Task(v) for v in aws]
    if not children:
        return children
    n_left = len(children)
    exceptions = []
    parent = await current_task()
    parent_step = None

    def on_child_end(child: Task):
        nonlocal n_left
        n_left -= 1
        if (e := child._exc_caught) is not None:
            exceptions.append(e)
            scope.cancel()
        if parent_step is not None and (not n_left):
            parent_step()

    succeeded = False
    try:
        with CancelScope(parent) as scope:
            for c in children:
                c._suppresses_exc = True
                c._on_end = on_child_end
                start(c)
            if exceptions or parent._cancel_requested:
                await sleep_forever()
                assert False, potential_bug_msg
            elif n_left:
                parent_step = parent._step
                await sleep_forever()
            succeeded = True
    finally:
        if succeeded:
            return children
        parent_step = None
        for c in children:
            c.cancel()
        if n_left:
            parent_step = parent._step
            try:
                parent._cancel_disabled += 1
                await sleep_forever()
            finally:
                parent_step = None
                parent._cancel_disabled -= 1
        if exceptions:
            raise ExceptionGroup("One or more exceptions occurred in child tasks.", exceptions)
        elif parent._cancel_requested:
            await sleep_forever()
            assert False, potential_bug_msg


async def wait_any(*aws: T.Iterable[Aw_or_Task]) -> T.Awaitable[T.List[Task]]:  # noqa: C901
    '''
    Run multiple tasks concurrently, and wait for any of them to finish.
    As soon as that happens, the others will be cancelled, and the function will
    return.

    .. code-block::

        e = asyncgui.Event()

        async def async_fn():
            ...

        tasks = await wait_any(async_fn(), e.wait())
        if tasks[0].finished:
            print("async_fn() finished")
        else:
            print("The event was set")

    When any of the tasks raises an exception, the rest will be cancelled, and
    the exception will be propagated to the caller, like Trio's Nursery does.

    Guaranteed Start
    ----------------

    Like ``wait_all()``, when any of the tasks:
    A) raises an exception
    B) finishes
    while there are still ones that haven't started yet, they still will
    start, (and will be cancelled soon).

    Chance of zero tasks to finish
    --------------------------------

    When all the tasks are cancelled, and there are no exceptions to
    propagate, it would happen.

    .. code-block::

        def test_cancel_all_children():
            import asyncgui as ag

            async def main():
                tasks = await ag.wait_any(child1, child2)
                for task in tasks:
                    assert task.cancelled  # NO TASKS HAVE FINISHED

            child1 = ag.Task(ag.sleep_forever())
            child2 = ag.Task(ag.sleep_forever())
            main_task = ag.start(main())
            child1.cancel()
            child2.cancel()
            assert main_task.finished

    Chance of multiple tasks to finish
    ------------------------------------

    .. warning::

        ``wait_any()``が正常に終了した時に常に一つだけ子taskが完了しているとは限らない事に注意されたし。
        例えば次のように即座に完了する子が複数ある場合はその全てが完了する。

        .. code-blobk::

            async def f():
                pass

            tasks = await wait_any(f(), f())
            assert tasks[0].finished
            assert tasks[1].finished

        また次の例も両方の子が完了する。

        .. code-blobk::

            async def f_1(e):
                await e.wait()

            async def f_2(e):
                e.set()

            e = asyncgui.Event()
            tasks = await wait_any([f_1(e), f_2(e))
            assert tasks[0].finished
            assert tasks[1].finished

        これは``e.set()``が呼ばれた事で``f_1()``が完了するが、その後``f_2()``が中断可能
        な状態にならないまま完了するためでる。中断可能な状態とは何かと言うと

        * 中断に対する保護がかかっていない(保護は`async with disable_cancellation()`でかかる)
        * Taskが停まっている(await式の地点で基本的に停まるが、停まらない例外としては ``await current_task()`` , ``await set済のEvent.wait()`` がある)

        の両方を満たしている状態の事で、上のcodeでは``f_2``が``e.set()``を呼んだ後に停止
        する事が無かったため中断される事なく完了する事になった。
    '''
    children = [v if isinstance(v, Task) else Task(v) for v in aws]
    if not children:
        return children
    n_left = len(children)
    exceptions = []
    parent = await current_task()
    parent_step = None

    def on_child_end(child: Task):
        nonlocal n_left
        n_left -= 1
        if (e := child._exc_caught) is not None:
            exceptions.append(e)
            scope.cancel()
        elif child.finished or (not n_left):
            scope.cancel()
        if parent_step is not None and (not n_left):
            parent_step()

    try:
        with CancelScope(parent) as scope:
            for c in children:
                c._suppresses_exc = True
                c._on_end = on_child_end
                start(c)
            await sleep_forever()
            assert False, potential_bug_msg
    finally:
        for c in children:
            c.cancel()
        if n_left:
            parent_step = parent._step
            try:
                parent._cancel_disabled += 1
                await sleep_forever()
            finally:
                parent_step = None
                parent._cancel_disabled -= 1
        if exceptions:
            raise ExceptionGroup("One or more exceptions occurred in child tasks.", exceptions)
        elif parent._cancel_requested:
            await sleep_forever()
            assert False, potential_bug_msg
        return children


@asynccontextmanager
async def run_and_cancelling(aw: Aw_or_Task) -> T.AsyncIterator[Task]:
    '''
    Equivalent of :func:`trio_util.run_and_cancelling`.
    '''

    bg_task = start(aw)
    if bg_task._state in TaskState.ENDED:
        yield bg_task
        return

    fg_task = await current_task()
    end_signal = Event()
    exc = None

    try:
        with CancelScope(fg_task) as scope:
            bg_task._suppresses_exc = True
            bg_task._on_end = partial(_rac_on_bg_task_end, end_signal, scope)
            yield bg_task
    except Exception as e:
        exc = e
    finally:
        bg_task.cancel()
        try:
            fg_task._cancel_disabled += 1
            await end_signal.wait()
        finally:
            fg_task._cancel_disabled -= 1
        excs = tuple(
            e for e in (exc, bg_task._exc_caught, )
            if e is not None
        )
        if excs:
            raise ExceptionGroup("run_and_cancelling()", excs)
        elif fg_task._cancel_level is not None:
            await sleep_forever()
            assert False, potential_bug_msg


def _rac_on_bg_task_end(end_signal, scope, bg_task):
    if bg_task._exc_caught is not None:
        scope.cancel()
    end_signal.set()


class OnetimeBox:
    '''
    (internal)
    An item box with the following limitations.

    * You can put an item in it only once. Calling :meth:`put_nowait` more than once will be ignored.
    * Only one task can get an item from it at a time.
    '''

    __slots__ = ('_args', '_kwargs', '_getter', )

    def __init__(self):
        self._args = None
        self._kwargs = None
        self._getter = None

    @property
    def is_empty(self) -> bool:
        return self._args is None

    def put_nowait(self, *args, **kwargs):
        if self._args is not None:
            return
        self._args = args
        self._kwargs = kwargs
        if (getter := self._getter) is not None:
            getter._step(*args, **kwargs)

    def get_nowait(self) -> T.Tuple[tuple, dict]:
        if self._args is None:
            raise InvalidStateError("The box is empty.")
        return (self._args, self._kwargs, )

    @types.coroutine
    def get(self) -> T.Awaitable[T.Tuple[tuple, dict]]:
        if self._getter is not None:
            raise InvalidStateError("There is already a task trying to get an item from this box.")
        if self._args is None:
            try:
                return (yield self._store_getter)
            finally:
                self._getter = None
        else:
            return (self._args, self._kwargs, )

    def _store_getter(self, task):
        self._getter = task
