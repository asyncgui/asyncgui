import functools
import sched
import asyncgui as ag
import string


async def sleep(scheduler, priority, duration):
    e = ag.ExclusiveEvent()
    event = scheduler.enter(duration, priority, e.fire)
    try:
        await e.wait()
    except ag.Cancelled:
        scheduler.cancel(event)
        raise


def main():
    s = sched.scheduler()
    slp = functools.partial(sleep, s, 0)
    ag.start(async_main(slp))
    s.run()


async def async_main(slp):
    # Print digits from 0 to 9 at 0.3-second intervals, with a 2-second time limit
    async with ag.move_on_when(slp(2)) as timeout_tracker:
        for c in string.digits:
            print(c, end=' ')
            await slp(0.3)
    print('')

    if timeout_tracker.finished:
        print("Timeout")
    else:
        print("Printed all digits in time")


if __name__ == '__main__':
    main()
