## CPython 3.10 EOL

Wait until CPython 3.10 reaches EOL, then drop support for it.
This will make the library completely free of external dependencies.

## Simultaneous `__aenter__` and `__aexit__`

Add a feature that allows multiple async context managers to enter and exit simultaneously.

```python
async with simultaneous_enter(async_cm1(), async_cm2()):
    ...
```

(When an `async with` statement has multiple async context managers, the coroutines returned by their `__aenter__` and `__aexit__` methods are executed one by one.)
