import pytest

from calculator import divide


def test_divide():
    assert divide(6, 2) == 3


def test_divide_by_zero_has_clear_error():
    with pytest.raises(ValueError, match="divisor cannot be zero"):
        divide(6, 0)
