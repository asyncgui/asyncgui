from contextlib import contextmanager
import sched
import asyncgui


@contextmanager
def open_scheduler():
    import types
    import sched

    s = sched.scheduler()

    @types.coroutine
    def sleep(duration):
        yield lambda task: s.enter(duration, 10, task._step)

    yield (s, sleep)
    s.run()


async def repeat_printing(sleep, obj, *, interval=.1, times=1):
    for __ in range(times):
        await sleep(interval)
        print(obj)


async def main(scheduler: sched.scheduler, sleep):

    print("\n### Run multiple tasks concurrently, and wait for ALL of them to end")
    await asyncgui.wait_all(
        repeat_printing(sleep, 'Kivy', times=4),
        repeat_printing(sleep, 'Python', times=2),
    )
    print("### done")

    print("\n### Run multiple tasks concurrently, and wait for ANY of them to end")
    tasks = await asyncgui.wait_any(
        repeat_printing(sleep, 'Kivy', times=4),
        repeat_printing(sleep, 'Python', times=2),
    )
    print('Kivy' if tasks[0].finished else 'Python', 'ended earlier')
    print("### done")


if __name__ == '__main__':
    with open_scheduler() as (scheduler, sleep):
        asyncgui.start(main(scheduler, sleep))
