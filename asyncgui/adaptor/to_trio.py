'''This module provides the way to excute asyncgui-flavored code under Trio.
'''

__all__ = ('run_awaitable', 'callable_to_asyncfn', 'awaitable_to_coro', )
import warnings
from inspect import iscoroutinefunction, isawaitable
from functools import wraps
import trio
import asyncgui
from asyncgui.exceptions import CancelledError


async def _ag_awaitable_wrapper(
        outcome:dict, end_signal:trio.Event, ag_awaitable):
    try:
        outcome['return_value'] = await ag_awaitable
    except GeneratorExit:
        outcome['cancelled'] = True
        raise
    except Exception as e:
        outcome['exception'] = e
    finally:
        end_signal.set()


async def run_awaitable(
        ag_awaitable, *, task_status=trio.TASK_STATUS_IGNORED):
    '''(experimental)
    Run an asyncgui-flavored awaitable under Trio.

    Usage #1:
        nursery.start_soon(run_awaitable, an_asyncgui_awaitable)

    Usage #2:
        return_value = await run_awaitable(an_asyncgui_awaitable)
    '''
    if not isawaitable(ag_awaitable):
        raise ValueError(f"{ag_awaitable} is not awaitable")
    end_signal = trio.Event()
    try:
        outcome = {}
        wrapper_coro = _ag_awaitable_wrapper(
            outcome, end_signal, ag_awaitable, )
        asyncgui.start(wrapper_coro)
        task_status.started(wrapper_coro)
        await end_signal.wait()
        exception = outcome.get('exception', None)
        if exception is not None:
            raise exception
        if outcome.get('cancelled', False):
            raise CancelledError("Inner task was cancelled")
        return outcome['return_value']
    finally:
        wrapper_coro.close()


def callable_to_asyncfn(ag_callable):
    '''(experimental)
    Convert a callable that returns a asyncgui-flavored awaitable to
    a Trio-flavored async function.

    Usage:
        a_trio_asyncfn = callable_to_asyncfn(an_asyncgui_asyncfn)
    '''
    if not callable(ag_callable):
        raise ValueError(f"{ag_callable} is not callable")
    async def trio_asyncfn(*args, **kwargs):
        task_status = kwargs.pop('task_status', trio.TASK_STATUS_IGNORED)
        return await run_awaitable(
            ag_callable(*args, **kwargs), task_status=task_status, )
    return trio_asyncfn


def awaitable_to_coro(ag_awaitable):
    '''(experimental)
    Convert an asyncgui-flavored awaitable to a Trio-flavored coroutine.

    Usage:
        return_value = await awaitable_to_coro(an_asyncgui_awaitable)
    '''
    return run_awaitable(ag_awaitable)
