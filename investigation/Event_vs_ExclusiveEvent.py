from timeit import timeit
from asyncgui import Event, ExclusiveEvent, start


async def repeat_waiting(e: Event | ExclusiveEvent):
    while True:
        await e.wait()



def measure_with_one_task(event_cls, n):
    e = event_cls()
    task = start(repeat_waiting(e))
    return timeit(e.fire, number=n)


def measure_with_zero_task(event_cls, n):
    e = event_cls()
    return timeit(e.fire, number=n)


def main():
    print("\n### one task")
    for n in (100, 1000, 10000, 100000, 1000000):
        print(f'{n=:10}', end=' ')
        for event_cls in (Event, ExclusiveEvent):
            print(f'{event_cls.__name__}: {measure_with_one_task(event_cls, n):.6f}', end=' ')
        print()

    print("\n### zero task")
    for n in (100, 1000, 10000, 100000, 1000000):
        print(f'{n=:10}', end=' ')
        for event_cls in (Event, ExclusiveEvent):
            print(f'{event_cls.__name__}: {measure_with_zero_task(event_cls, n):.6f}', end=' ')
        print()


if __name__ == '__main__':
    main()
