import pytest
from app import config, db

@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DATA', tmp_path)
    monkeypatch.setattr(config, 'DB', tmp_path/'leap.db')
    monkeypatch.setattr(config, 'TOKEN', 'test-token-with-at-least-32-characters')
    monkeypatch.setenv('ENABLE_SCHEDULER', '0')
    monkeypatch.delenv('WEBDAV_URL', raising=False)
    db.init()
    return tmp_path
