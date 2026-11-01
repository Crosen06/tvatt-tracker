import pytest
from starlette.testclient import TestClient

from app.main import create_app


@pytest.fixture
def data_dir(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def app(data_dir):
    return create_app(data_dir)


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def conn(app):
    from app.db import connect

    c = connect(app.state.db_path)
    yield c
    c.close()
