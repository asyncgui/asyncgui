from inspect import stack
import asyncgui as ag


async def async_fn():
    while True:
        print(len(stack()))
        await ag.current_task()
        print(len(stack()))
        await ag.current_task()
        print(len(stack()))
        await ag.sleep_forever()

print('start()')
task = ag.start(async_fn())
print('_step()')
task._step()
