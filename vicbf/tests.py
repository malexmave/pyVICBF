"""Test cases for the VICBF implementation.

These test cases are run with "nosetest".
"""

from vicbf import VICBF

"""Constructor tests"""


def test_incorrect_constructor_slots():
    try:
        VICBF(-1, 1000, 3)
    except ValueError:
        assert True
        return
    assert False


def test_incorrect_constructor_expected():
    try:
        VICBF(100, -2, 3)
    except ValueError:
        assert True
        return
    assert False


def test_incorrect_constructor_hashfunctions():
    try:
        VICBF(1000, 1000, -1)
    except ValueError:
        assert True
        return
    assert False


def test_incorrect_constructor_vibase():
    try:
        VICBF(1000, 1000, 3, vibase=3)
    except ValueError:
        assert True
        return
    assert False

"""Insertion tests"""


def test_insert():
    v = VICBF(10000, 1000, 3)
    v.insert(123)
    assert True


def test_insert_none():
    v = VICBF(10000, 1000, 3)
    try:
        v.insert(None)
    except ValueError:
        assert True
        return
    assert False


def test_many_inserts():
    v = VICBF(10000, 1000, 3)
    for i in range(1000):
        v.insert(i)
    assert not v.query(1001)


def test_insert_overflow():
    v = VICBF(10000, 1000, 3)
    for i in range(1000):
        v.insert(123)
    assert v.query(123)
    for i in range(1000):
        v.remove(123)
    # Even though it should now theoretically be removed, the implementation
    # should still return true because the values should have been fixed at
    # the maximum when the overflow occured
    assert v.query(123)

"""Query tests"""


def test_query_inserted():
    v = VICBF(10000, 1000, 3)
    v.insert(123)
    assert v.query(123)


def test_query_not_inserted():
    v = VICBF(10000, 1000, 3)
    v.insert(123)
    assert not v.query(4567)


def test_query_multi_insert_remove():
    v = VICBF(10000, 1000, 3)
    v.insert(123)
    v.insert(123)
    v.remove(123)
    assert v.query(123)


def test_query_none():
    v = VICBF(10000, 1000, 3)
    try:
        v.query(None)
    except ValueError:
        assert True
        return
    assert False


def test_query_list_syntax():
    v = VICBF(10000, 1000, 3)
    v.insert(123)
    assert 123 in v
    assert 124 not in v

"""Removal tests"""


def test_remove():
    v = VICBF(10000, 1000, 3)
    v.insert(123)
    v.remove(123)
    assert not v.query(123)


def test_remove_not_inserted():
    v = VICBF(10000, 1000, 3)
    try:
        v.remove(124)
    except ValueError:
        assert True
        return
    assert False


def test_remove_none():
    v = VICBF(10000, 1000, 3)
    try:
        v.remove(None)
    except ValueError:
        assert True
        return
    assert False
