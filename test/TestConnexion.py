import pytest

from app import app


class TestConnexion:
    """The base test providing auth and flask clients to other tests
    """
    cache: dict = {}

    @pytest.fixture(scope='session')
    def client(self):
        with app.app.test_client() as c:
            yield c
