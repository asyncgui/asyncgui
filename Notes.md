# coroutine

- 既に閉じてしまったcoroへの`coro.send()`や`coro.throw()`は`RuntimeError: cannot reuse already awaited coroutine`を引き起こす。
- 未開始状態のcoroへ`coro.throw()`とすると例外がそのまま湧いてきてcoroはCORO_CLOSEDとなる。開始していない状態で投げた例外なのでcoroが内部で捌く機会は無い(多分?)。
