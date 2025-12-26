===========================
Structured Concurrency |ja|
===========================

ここでは `structured concurrency`_ (`構造化された並行性`_) 関連のAPIについて解説していきます。
``構造化された並行性`` が何であるか また何故素晴らしいのかはここでは触れませんので
興味がある人は `Notes on structured concurrency`_ (`不完全な和訳`_) を読んでください。


wait_any
--------

複数のタスクを同時に走らせ ``そのいずれかが完了するか`` 或いは ``全てが中断される`` まで待ちます。
そしていずれかのタスクが完了しだい残りのタスクは中断されます。

.. code-block::

    tasks = await wait_any(async_fn0(), async_fn1(), async_fn2())

どのタスクが完了/中断したのか、完了した物の戻り値は何か等は全て戻り値から判別可能です。

.. code-block::

    for idx, task in enumerate(tasks):
        if task.finished:
            print(f"async_fn{idx} は {task.result} を返して完了しました。")
        else:
            print(f"async_fn{idx} は中断されました。")


wait_all
--------

全てのタスクが完了あるいは中断されるまで待ちます。

.. code-block::

    tasks = await wait_all(async_fn1(), async_fn2(), async_fn3())

``tasks`` の扱い方は ``wait_any`` と同じです。


好きなだけ入れ子に
------------------

``wait_all`` と ``wait_any`` は共に :class:`~collections.abc.Awaitable` を返すのでそれを ``wait_all`` や ``wait_any``
の引数に渡すことも可能です。

.. code-block::

    # async_fn1が完了し なおかつ async_fn2かasync_fn3のいずれかが完了するまで待つ
    tasks = await wait_all(
        async_fn1(),
        wait_any(
            async_fn2(),
            async_fn3(),
        ),
    )

.. figure:: ./figure/nested-tasks.*

ただ階層深くにあるタスクを触るまでが面倒くさくなるのが難点です。

.. code-block::

    flattened_tasks = (tasks[0], *tasks[1].result, )

    for idx, task in enumerate(flattened_tasks, start=1):
        if task.finished:
            print(f"async_fn{idx} は {task.result} を返して完了しました。")
        else:
            print(f"async_fn{idx} は中断されました。")

入れ子が深くなればなるほど階層深くにあるタスクを触るための式が ``tasks[i].result[j].result[k]`` といった具合に長くなる
わけですが、このような書き方を好まないのであれば以下の様に :class:`asyncgui.Task` のインスタンスを自ら作って渡せば後は階層には触らずに
タスクの結果を知ることも出来ます。

.. code-block::

    await wait_all(
        async_fn1(),
        wait_any(
            task2 := Task(async_fn2()),  # 自ら作って渡す
            async_fn3(),
        ),
    )
    if tasks2.finished:
        print(f"async_fn2 は {tasks2.result} を返して完了しました")
    else:
        print("async_fn2 は中断されました")


wait_any_cm, wait_all_cm
------------------------

:func:`~asyncgui.wait_any` と :func:`~asyncgui.wait_all` にはコンテキストマネージャ版である :func:`~asyncgui.wait_any_cm` と :func:`~asyncgui.wait_all_cm` が用意されています。
これらは渡されたタスクに加えてwithブロック内のコードも並行して走らせます。
すなわち以下のコードでは ``async_fn0`` と ``async_fn1`` と ``hogehoge`` の３つを並行して走らせます。

.. code-block::

    async def wait_any_cm(async_fn0(), async_fn1()) as tasks:
        # hogehoge

引数に渡したタスクが完了/中断したのか、完了した物の戻り値は何か等の調べ方は同じです。

.. code-block::

    for i, task in enumerate(tasks):
        if task.finished:
            print(f"async_fn{i} は {task.result} を返して完了しました。")
        else:
            print(f"async_fn{i} は中断されました。")

run_as_daemon
-------------

これまで解説してきたAPIはどれも並行させたタスク達の関係が対等でした。
``wait_any_cm`` を例に挙げるならwithブロック内のコードと ``wait_any_cm`` に渡したタスクのどれが完了した場合でも他の処理を中断させるのでした。
しかし時には対等ではない関係も必要となります。

.. code-block::

    async with run_as_daemon(async_fn()) as daemon_tasks:
        ...

このコードではwithブロック内が先に完了した場合は ``async_fn()`` は中断させられますが、 ``async_fn()`` が先に完了しても何も起きず
withブロックの完了を待つだけです。例えるならデーモンスレッドと非デーモンスレッドの関係です。withブロック内のコードが非デーモンで
``async_fn()`` がデーモンになっていると考えて下さい。


run_as_main
-----------

これは ``run_as_daemon`` の逆でwithブロック内がデーモンとなります。

.. code-block::

    async with run_as_main(async_fn()) as main_tasks:
        ...

すなわちwithブロックが先に完了した場合は ``async_fn()`` の完了を待つ事になり、
``async_fn()`` が先に完了した場合はwithブロックが中断されます。


open_nursery
------------

:func:`trio.open_nursery` を真似たものです。
このAPIの利は並行させたいタスクをあらかじめ用意しなくて良い事です。
``nursery`` が開いている限りは後からいくらでも ``nursery.start()`` でタスクを加えられます。

.. code-block::

    async with open_nursery() as nursery:
        while True:
            touch = await 画面に指が触れられるのを待つ
            nursery.start(指に沿って線を引く(touch))

但しタスクの戻り値を得る方法は無いので別の形で値を受け渡してください。

.. seealso:: :class:`asyncgui.Nursery`, `Trio関連の日本語記事`_


例外処理
--------

ここのAPI全てに共通しているのが例外の運ばれ方です。
並行させているタスクの内どれか一つで例外が起きると他のタスクは中断され例外は呼び出し元に運ばれます。
この時 中断された他のタスクがその中断過程で更に例外を起こすかもしれないので例外は複数同時に起こりえます。
このため ``asyncgui`` は例外を運ぶために Python3.11 より登場した :exc:`ExceptionGroup` を用います
(3.11未満のPythonが使われていた場合は exceptiongroup_ を用います)。
これはたとえ例外が一つしか起こらなかった場合でもです。

.. tabs::

    .. group-tab:: 3.11以上

        .. code-block::

            try:
                await wait_any(...)
            except* Exception as excgroup:
                for exc in excgroup.exceptions:
                    print('例外が起きました:', type(exc))
                

    .. group-tab:: 3.11未満

        .. code-block::

            import exceptiongroup

            def error_handler(excgroup):
                for exc in excgroup.exceptions:
                    print('例外が起きました:', type(exc))

            with exceptiongroup.catch({Exception: error_handler, }):
                await wait_any(...)


.. _structured concurrency: https://en.wikipedia.org/wiki/Structured_concurrency
.. _構造化された並行性: https://ja.wikipedia.org/wiki/%E6%A7%8B%E9%80%A0%E5%8C%96%E3%81%95%E3%82%8C%E3%81%9F%E4%B8%A6%E8%A1%8C%E6%80%A7
.. _trio: https://trio.readthedocs.io/
.. _trio-util: https://trio-util.readthedocs.io/
.. _Notes on structured concurrency: https://vorpus.org/blog/notes-on-structured-concurrency-or-go-statement-considered-harmful/
.. _不完全な和訳: https://qiita.com/gotta_dive_into_python/items/6feb3224a5fa572f1e19
.. _Trio関連の日本語記事: https://qiita.com/tags/trio
.. _exceptiongroup: https://github.com/agronholm/exceptiongroup
