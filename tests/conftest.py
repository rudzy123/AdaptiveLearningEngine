import pytest

from ale.engine import Tutor
from ale.engine.curriculum import load_curriculum


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "ale.db"


@pytest.fixture()
def tutor(db_path):
    return Tutor(db_path)


@pytest.fixture(scope="session")
def curriculum():
    return load_curriculum()


@pytest.fixture()
def client(db_path):
    from fastapi.testclient import TestClient

    from ale.interfaces.api import create_app

    return TestClient(create_app(db_path), raise_server_exceptions=False)
