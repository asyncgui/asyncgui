from timeit import timeit
from asyncgui import Box, ExclusiveBox, start


async def repeat_getting(box: Box | ExclusiveBox):
    while True:
        await box.get()
        box.clear()


def measure_with_one_task(box_cls, n):
    box = box_cls()
    task = start(repeat_getting(box))
    return timeit(box.put, number=n)


def measure_with_zero_task(box_cls, n):
    box = box_cls()
    return timeit("box.put(); box.clear()", number=n, globals={'box': box, })


def measure_with_zero_task_no_clear(box_cls, n):
    box = box_cls()
    return timeit(box.put, number=n)


def main():
    print("\n### one task")
    for n in (100, 1000, 10000, 100000, 1000000):
        print(f'{n=:10}', end=' ')
        for box_cls in (Box, ExclusiveBox):
            print(f'{box_cls.__name__}: {measure_with_one_task(box_cls, n):.6f}', end=' ')
        print()

    print("\n### zero task")
    for n in (100, 1000, 10000, 100000, 1000000):
        print(f'{n=:10}', end=' ')
        for box_cls in (Box, ExclusiveBox):
            print(f'{box_cls.__name__}: {measure_with_zero_task(box_cls, n):.6f}', end=' ')
        print()

    print("\n### zero task (no clear)")
    for n in (100, 1000, 10000, 100000, 1000000):
        print(f'{n=:10}', end=' ')
        for box_cls in (Box, ExclusiveBox):
            print(f'{box_cls.__name__}: {measure_with_zero_task_no_clear(box_cls, n):.6f}', end=' ')
        print()


if __name__ == '__main__':
    main()
