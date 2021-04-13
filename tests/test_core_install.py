import pytest


@pytest.fixture(autouse=True)
def cleanup():
    import asyncgui._core
    yield
    asyncgui._core._close_soon = asyncgui._core._default_close_soon


def nothing_is_installed() -> bool:
    from asyncgui._core import _close_soon, _default_close_soon
    return _close_soon is _default_close_soon


def close_soon(coro):
    pass


def test_install_twice():
    from asyncgui import InvalidStateError
    from asyncgui._core import install
    install(close_soon=close_soon)
    assert not nothing_is_installed()
    with pytest.raises(InvalidStateError):
        install(close_soon=close_soon)
    assert not nothing_is_installed()


def test_install_non_callable():
    from asyncgui import InvalidStateError
    from asyncgui._core import install
    with pytest.raises(ValueError):
        install(close_soon=123)
    assert nothing_is_installed()


def test_uninstall_without_installing_anything():
    from asyncgui import InvalidStateError
    from asyncgui._core import uninstall
    with pytest.raises(InvalidStateError):
        uninstall(close_soon=close_soon)
    assert nothing_is_installed()


def test_uninstall_a_non_callable():
    from asyncgui import InvalidStateError
    from asyncgui._core import install, uninstall
    install(close_soon=close_soon)
    assert not nothing_is_installed()
    with pytest.raises(ValueError):
        uninstall(close_soon=123)
    assert not nothing_is_installed()


def test_uninstall_a_wrong_one():
    from asyncgui import InvalidStateError
    from asyncgui._core import install, uninstall
    install(close_soon=close_soon)
    assert not nothing_is_installed()
    with pytest.raises(ValueError):
        uninstall(close_soon=lambda:None)
    assert not nothing_is_installed()


def test_install_and_uninstall():
    from asyncgui._core import install, uninstall
    install(close_soon=close_soon)
    assert not nothing_is_installed()
    uninstall(close_soon=close_soon)
    assert nothing_is_installed()
