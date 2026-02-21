"""
Pytest fixtures and configuration
"""
import pytest
import tempfile
from pathlib import Path

from music_agent.config import Settings
from music_agent.models import Database


@pytest.fixture
def temp_db():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    db = Database('sqlite', db_path)
    db.connect().migrate()
    
    yield db
    
    # Cleanup
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def temp_storage():
    """Create temporary storage directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings():
    """Test settings with dummy values"""
    return Settings(
        db_type='sqlite',
        db_conn=':memory:',
        poe_api_key='test_key',
        suno_cookie='test_cookie',
        debug=True
    )
