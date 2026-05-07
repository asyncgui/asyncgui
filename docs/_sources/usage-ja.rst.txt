==============
Usage |ja|
==============

ここではどのように ``asyncgui`` とコールバック型のAPIを繋ぐのかを :mod:`sched` を例に見ていきます。
まずはこれをそのまま用いて

#. １秒待機
#. ``A`` を出力
#. ２秒待機
#. ``B`` を出力
#. 3秒待機
#. ``C`` を出力

といった処理を書いてみます。

.. code-block::

    import sched

    PRIORITY = 0
    s = sched.scheduler()

    def やりたい事():
        def step1():
            print('A')
            s.enter(2, PRIORITY, step2)

        def step2():
            print('B')
            s.enter(3, PRIORITY, step3)

        def step3():
            print('C')

        s.enter(1, PRIORITY, step1)

    やりたい事()
    s.run()

コールバック型のコードはやはり読みづらいですね。
ここでもしかすると「いや :func:`time.sleep` 使えばいいのでは？」といった声が上がるかもしれないので反論しておきます。

「time.sleep 使えばいいのでは？」に対する反論
===============================================

確かに ``time.sleep`` を用いれば次のように書けます。

.. code-block::

    from time import sleep

    def やりたい事():
        sleep(1)
        print('A')
        sleep(2)
        print('B')
        sleep(3)
        print('C')

    やりたい事()

しかしこれは ``やりたい事`` が一つしか無いとき限定であり複数あると話が変わってきます。
``time.sleep`` のやり方では複数のスレッドを建てないと複数の事ができないのに対し ``sched`` を用いたやり方は一つで足ります。
具体的にはコードの最後の部分で

.. code-block::

    # あくまで一例
    やりたい事()
    やりたい事()
    s.run()

という風に ``やりたい事`` を複数回呼ぶだけです。なので ``time.sleep`` に ``sched`` の代わりは務まらないと言えます。

APIを決める
=================

それではこれから繋げていくのですが先ずはいま繋げようとしているコールバック型APIである :meth:`sched.scheduler.enter`
を ``asyncgui`` からどのような形で利用したいかを考えないといけません。

ここで上で出てきた ``time.sleep`` の例を思い出して欲しいのですが 以下のようなコードでした。

.. code-block::

    from time import sleep

    def やりたい事():
        sleep(1)
        print('A')
        sleep(2)
        print('B')
        sleep(3)
        print('C')

このやり方はスレッドを占有するという短所がある反面、コードがすこぶる読みやすいという利を持っています。
``enter()`` のasync/await版もこのように読みやすいと使う側はきっと嬉しいんじゃないでしょうか？
具体的には以下の感じです。

.. code-block::

    async def やりたい事():
        await sleep(1)
        print('A')
        await sleep(2)
        print('B')
        await sleep(3)
        print('C')

これが実現すれば ``time.sleep`` の物とほぼ同等の読みやすさな上にスレッドを占有しないという良いとこ取りができた事になります [#obtain_cancellation]_ 。
なのでこの様な姿を目指す事にしましょう。

``await sleep(1)`` という使い方をするという事は ``sleep`` は :class:`~collections.abc.Awaitable` を返す :class:`~collections.abc.Callable`
でないといけません。
その条件を満たす実装方法は幾つか有るのですが、とりあえずその一つであるasync関数 [#async_func_mitasu]_ から考えてみます。

.. code-block::

    async def sleep(duration):
        ...

こう書きたいところなのですが ``enter()`` はインスタンスメソッドなのでインスタンスを渡さないと呼びようがありませんし、
このメソッドは ``priority`` という引数も取るのでそれも渡してあげましょう。

.. code-block::

    async def sleep(scheduler, priority, duration):
        ...

というわけでこの姿を目指して実装にとりかかります。

.. そもそもコールバック型のコードが読みづらいのはコードが細切れになってしまうからです。
   本来は一つの関数に纏めるべき処理であったとしてもその中に「〇秒経ってから〇〇する」や「〇〇が起こった時に〇〇する」のような"待ち"があると
   関数をそこで分割せざるを得ません。
   しかし処理の進行を一時停止できるasync/awaitの世界では話が変わってきます。
   "待ち"が必要な時には一時停止して文字通り待てばいいだけなのですから。

実装
====

コールバック型のAPIをasync/awaitの世界と繋ぐにはコールバック関数が呼ばれた時に処理が再開するように仕組んだ上で処理を停めるようなasync関数が要ります。
難しそうに聞こえますが :class:`asyncio.Event` や :class:`trio.Event` を使った事があればピンと来るんじゃないでしょうか？

.. code-block::

    import asyncio

    async def 仲介者():
        e = asyncio.Event()

        # コールバック関数が呼ばれた時に処理が再開するように仕組む
        コールバック関数を登録(lambda *args, **kwargs: e.set())

        # 処理を停める
        await e.wait()

    async def 利用者():
        print('A')
        await 仲介者()
        print('B')

このように ``仲介者`` を挟む事で ``利用者`` 側のコードは読みやすさを損なわずにコールバック型のAPIを使えるようになります。
そして ``asyncgui`` にはこの目的に特化したAPIがあります。

.. code-block::

    import asyncgui as ag

    async def 仲介者():
        e = ag.ExclusiveEvent()
        コールバック関数を登録(e.fire)  # A
        args, kwargs = await e.wait()  # B

``asyncgui`` の場合は :meth:`asyncgui.ExclusiveEvent.fire` がどんな引数でも受け取れるようになっているのでlambdaを挟まなくて済むうえ(A行)、
``fire`` に渡った引数を受け取れる(B行)というのが :class:`asyncio.Event` には無い強みです。
これ用いて ``sleep`` を実装すると以下のようになります。

.. code-block::

    import asyncgui as ag

    async def sleep(scheduler, priority, duration):
        e = ag.ExclusiveEvent()
        scheduler.enter(duration, priority, e.fire)
        await e.wait()

これで以下のように分かりやすく ``やりたい事`` が書けるようになりました...

.. code-block::

    import functools
    import sched
    import asyncgui as ag

    async def sleep(...):
        省略

    def main():
        s = sched.scheduler()
        slp = functools.partial(sleep, s, 0)
        ag.start(やりたい事(slp))
        s.run()

    async def やりたい事(slp):
        await slp(1)
        print('A')
        await slp(2)
        print('B')
        await slp(3)
        print('C')

    main()

と言いたい所なのですがもう一つやっておきたい事があり、それは中断への対応です。
最低限の対応は ``ExclusiveEvent`` が行っているので ``sleep`` 内で行うことは必須ではないのですがやっておく方がより良いです。
(参考: :ref:`dealing-with-cancellation`)

.. code-block::

    import asyncgui as ag

    async def sleep(scheduler, priority, duration):
        e = ag.ExclusiveEvent()
        event = scheduler.enter(duration, priority, e.fire)
        try:
            await e.wait()
        except ag.Cancelled:
            scheduler.cancel(event)
            raise

これで完璧に ``sched`` を ``asyncgui`` と繋ぐ事に成功しました。
一度繋ぐ事ができれば ``asyncgui`` の持つ強力な :doc:`structured-concurrency-ja` の恩恵を受けられます。

.. code-block::

    import functools
    import sched
    import asyncgui as ag
    import string

    async def sleep(scheduler, priority, duration):
        省略

    def main():
        s = sched.scheduler()
        slp = functools.partial(sleep, s, 0)
        ag.start(async_main(slp))
        s.run()

    async def async_main(slp):
        # 0から9までの数字を0.3秒間隔で出力するが、その作業に2秒の制限時間を設ける
        async with ag.move_on_when(slp(2)) as timeout_tracker:
            for c in string.digits:
                print(c, end=' ')
                await slp(0.3)
        print('')

        if timeout_tracker.finished:
            print("時間切れ")
        else:
            print("時間内に全ての数字を出力し終わりました")

    main()

::

    0 1 2 3 4 5 6
    時間切れ


.. [#obtain_cancellation] 加えて強力な中断能力も手に入ります。
.. [#async_func_mitasu] async関数は関数なので勿論 ``Callable`` ですし戻り値は必ず ``Awaitable`` の一種である ``Coroutine`` なので条件を満たします。
