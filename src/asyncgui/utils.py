from typing import Any

from . import __init__ as asyncgui
from .__init__ import ExclusiveEvent


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
