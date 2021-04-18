__all__ = ('or_', 'and_', )
import types
import typing

from ._core import Task, Awaitable_or_Task, start


@types.coroutine
def _gather(aws_and_tasks: typing.Iterable[Awaitable_or_Task], *, n: int=None) \
        -> typing.List[Task]:
    '''(internal)'''
    tasks = [v if isinstance(v, Task) else Task(v) for v in aws_and_tasks]
    n_tasks = len(tasks)
    n_left = n_tasks if n is None else min(n, n_tasks)

    def step_coro():
        pass

    def done_callback(*args, **kwargs):
        nonlocal n_left
        n_left -= 1
        if n_left == 0:
            step_coro()

    for task in tasks:
        task._event.add_callback(done_callback)
        start(task)

    if n_left <= 0:
        return tasks

    def callback(step_coro_):
        nonlocal step_coro
        step_coro = step_coro_
    yield callback

    return tasks


async def or_(*aws_and_tasks):
    return await _gather(aws_and_tasks, n=1)


async def and_(*aws_and_tasks):
    return await _gather(aws_and_tasks)
