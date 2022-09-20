import sched
import asyncgui
from asyncgui.testing import open_scheduler


async def repeat_printing(sleep, obj, *, interval=.1, times=1):
    for __ in range(times):
        await sleep(interval)
        print(obj)


async def main(scheduler: sched.scheduler, sleep):
    from asyncgui.structured_concurrency import and_, or_

    print("\n### Run multiple tasks simultaneously, and wait for ALL of them to end")
    await and_(
        repeat_printing(sleep, 'Kivy', times=4),
        repeat_printing(sleep, 'Python', times=2),
    )
    print("### done")

    print("\n### Run multiple tasks simultaneously, and wait for ONE of them to end")
    tasks = await or_(
        repeat_printing(sleep, 'Kivy', times=4),
        repeat_printing(sleep, 'Python', times=2),
    )
    print('Kivy' if tasks[0].done else 'Python', 'ended earlier')
    print("### done")


if __name__ == '__main__':
    with open_scheduler() as (scheduler, sleep):
        asyncgui.start(main(scheduler, sleep))
