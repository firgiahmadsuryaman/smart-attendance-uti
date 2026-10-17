import pytest

from app.utils import check_rate_limit, reset_rate_limit


@pytest.fixture(autouse=True)
def clean_state():
    reset_rate_limit()
    yield
    reset_rate_limit()


def test_allows_requests_up_to_the_limit():
    for _ in range(3):
        assert check_rate_limit("1.2.3.4", limit=3) is True


def test_blocks_the_request_after_the_limit():
    for _ in range(3):
        check_rate_limit("1.2.3.4", limit=3)

    assert check_rate_limit("1.2.3.4", limit=3) is False


def test_zero_limit_disables_the_limiter():
    for _ in range(50):
        assert check_rate_limit("1.2.3.4", limit=0) is True


def test_keys_are_counted_independently():
    for _ in range(3):
        check_rate_limit("1.2.3.4", limit=3)

    assert check_rate_limit("1.2.3.4", limit=3) is False
    assert check_rate_limit("5.6.7.8", limit=3) is True


def test_reset_clears_the_counter():
    for _ in range(3):
        check_rate_limit("1.2.3.4", limit=3)
    assert check_rate_limit("1.2.3.4", limit=3) is False

    reset_rate_limit()

    assert check_rate_limit("1.2.3.4", limit=3) is True


def test_expired_window_stops_blocking():
    """Jendela nol detik membuat seluruh hitungan lama dianggap kedaluwarsa."""
    for _ in range(3):
        check_rate_limit("1.2.3.4", limit=3, window_seconds=60)

    # Dengan jendela 60 detik, catatan lama masih berlaku dan permintaan diblokir.
    assert check_rate_limit("1.2.3.4", limit=3, window_seconds=60) is False
    # Dengan jendela nol detik, catatan lama sudah dianggap kedaluwarsa.
    assert check_rate_limit("1.2.3.4", limit=3, window_seconds=0) is True
