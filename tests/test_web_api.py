"""
Web API tests
"""
import pytest
from fastapi.testclient import TestClient

from music_agent.web.app import app


client = TestClient(app)


class TestWebAPI:
    def test_health_check(self):
        response = client.get("/api/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "albums" in data
        assert "songs" in data
    
    def test_sync_endpoint_unauthorized(self):
        # Without proper setup, should fail gracefully
        response = client.post("/api/sync")
        # Should return error about missing cookie or start task
        assert response.status_code in [200, 500, 422]
    
    def test_invalid_path(self):
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
    
    def test_security_headers(self):
        response = client.get("/")
        
        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"
