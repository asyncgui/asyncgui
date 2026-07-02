from typing import Any, Awaitable, List

from . import __init__ as asyncgui
from .__init__ import TaskState, ExclusiveEvent, StatefulEvent, Event


class StatefulEventWrapper:
    """
    Wraps an Event with statefulness.
    Usually, this is an ExclusiveEvent, but a StatelessEvent would also do, but then we have a StatefulEvent.
    """
    __slots__ = ("_wrapped_event", "_params", "__weakref__",)

    def __init__(self, baseclass=ExclusiveEvent):
        self._wrapped_event = baseclass()
        self._params = None

    @property
    def is_fired(self) -> bool:
        return self._params is not None

    def fire(self, *args, **kwargs):
        """Fires the event if it's not in a fired state."""
        if self._params is not None:
            return
        self._params = (args, kwargs,)
        self._wrapped_event.fire(*args, **kwargs)

    def clear(self):
        """Sets the event to a non-fired state."""
        self._params = None

    async def wait(self) -> asyncgui.SendType:
        if self._params is not None:
            return self._params
        return await self._wrapped_event.wait()

    @property
    def params(self) -> tuple:
        """
        The parameters passed to the last fire. Raises :exc:`InvalidStateError` if the event is not in a "fired" state.
        This is a convenient way to access the parameters from synchronous context.

        .. code-block::

            e = StatefulEvent()

            e.fire(1, crow='raven')
            args, kwargs = e.params
            assert args == (1, )
            assert kwargs == {'crow': 'raven', }

            e.clear()
            e.fire(2, parasol='umbrella')
            args, kwargs = e.params
            assert args == (2, )
            assert kwargs == {'parasol': 'umbrella', }
        """
        p = self._params
        if p is None:
            raise asyncgui.InvalidStateError("The event is not in a 'fired' state.")
        return p

    async def wait_args(self) -> Any:
        return await self.wait()[0]

    async def wait_args_0(self) -> Any:
        return await self.wait()[0][0]


StatefulExclusiveEvent = StatefulEventWrapper  # which it factually is


class TaskWaiter:
    """Object for awaiting on an asyncgui task and its result from outside.

    It goes like

        .. code-block::

            task = asyncgui.start(my_coro())
            await TaskWaiter(task)
    """
    __slots__ = ("_task", "_old_on_end", "_waiting_events", "__weakref__",)

    def __init__(self, task):
        # task should be a running task where we connect to:
        self._task = task
        task._suppresses_exc = True
        # Someone else might be waiting on this task's result, get into the chain:
        self._old_on_end = task._on_end
        task._on_end = self._on_end
        # These events are waiting on the task:
        self._waiting_events: List[Event | StatefulEvent | ExclusiveEvent | StatefulEventWrapper] = []

    def _on_end(self, task):
        """Callback for the end of the task. Fire all listening events."""
        if (old_on_end := self._old_on_end) is not None:
            old_on_end(task)
        for waiting_event in self._waiting_events:
            waiting_event.fire()

    # noinspection PyProtectedMember
    def _return_result(self, default):
        """Determine the result to return.
        If there is no such result, return the sentinel value given by the caller so that they know they should wait."""
        state = self._task._state
        if state is TaskState.FINISHED:
            return self._task._result
        elif state is TaskState.CANCELLED:
            if self._task._exc_caught is not None:
                raise self._task._exc_caught
            else:
                raise asyncgui._Cancelled()
        else:
            return default

    def __await__(self):
        """Result of the task. If the task is not finished, we wait for it. """
        sentinel = object()
        ret = self._return_result(sentinel)
        if ret is sentinel:
            # not ready yet.
            event = ExclusiveEvent()
            self._waiting_events.append(event)
            try:
                yield from event.wait()
            finally:
                self._waiting_events.remove(event)
                ret = self._return_result(sentinel)
                assert ret is not sentinel, "We wrongly were notified about the task being ready."
        return ret


class AwaitableTask(asyncgui.Task):
    """Extended version of a Task which also contains the functionality of TaskWaiter.

    It goes like

        .. code-block::

            task = asyncgui.start(AwaitableTask(my_coro()))
            await task
    But it won't work this way, because asyncgui.start() works the wrong way for it.
    It should first check for isinstance(aw, Task) which also covers our case,
    and only then check for isawaitable(aw).

    The current way, the AwaitableTask() would be wrapped in a Task() which is not awaitable, defeating our purpose.
    """
    __slots__ = ('_waiting_events',)

    def __init__(self, aw: Awaitable, /):
        super().__init__(aw)
        # These events are waiting on the task:
        self._waiting_events: List[Event | StatefulEvent | ExclusiveEvent | StatefulEventWrapper] = []

    async def _wrapper(self, aw, /):
        try:
            await super()._wrapper(aw)
        finally:
            for waiter in self._waiting_events:
                waiter.fire()

    # noinspection PyProtectedMember
    def _return_result(self, default):
        """Determine the result to return.
        If there is no such result, return the sentinel value given by the caller so that they know they should wait."""
        state = self._state
        if state is TaskState.FINISHED:
            return self._result
        elif state is TaskState.CANCELLED:
            if self._exc_caught is not None:
                raise self._exc_caught
            else:
                raise asyncgui._Cancelled()
        else:
            return default

    def __await__(self):
        """Result of the task. If the task is not finished, we wait for it. """
        sentinel = object()
        ret = self._return_result(sentinel)
        if ret is sentinel:
            # not ready yet.
            event = ExclusiveEvent()
            self._waiting_events.append(event)
            try:
                yield from event.wait()
            finally:
                self._waiting_events.remove(event)
                ret = self._return_result(sentinel)
                assert ret is not sentinel, "We wrongly were notified about the task being ready."
        return ret
