"""
Security tests
"""
import pytest
from pathlib import Path

from music_agent.utils.security import (
    sanitize_filename,
    validate_path_within_base,
    validate_album_id,
    SecretMaskFilter
)


class TestSanitizeFilename:
    def test_removes_path_traversal(self):
        assert sanitize_filename('../../../etc/passwd') == 'etc_passwd'
        assert sanitize_filename('..\\..\\windows\\system32') == 'windows_system32'
    
    def test_removes_special_chars(self):
        assert sanitize_filename('file<>:"|?*.txt') == 'file_.txt'
    
    def test_handles_empty_string(self):
        assert sanitize_filename('') == 'untitled'
        assert sanitize_filename('   ') == 'untitled'
    
    def test_limits_length(self):
        long_name = 'a' * 300
        assert len(sanitize_filename(long_name)) == 200


class TestValidatePath:
    def test_valid_path(self, temp_storage):
        base = temp_storage / "base"
        base.mkdir()
        file = base / "subdir" / "file.txt"
        file.parent.mkdir()
        
        assert validate_path_within_base(file, base) is True
    
    def test_invalid_path_traversal(self, temp_storage):
        base = temp_storage / "base"
        base.mkdir()
        file = temp_storage / "secret.txt"
        
        assert validate_path_within_base(file, base) is False
    
    def test_symlink_attack(self, temp_storage):
        base = temp_storage / "base"
        base.mkdir()
        
        secret = temp_storage / "secret.txt"
        secret.write_text("secret")
        
        link = base / "link"
        link.symlink_to(secret)
        
        assert validate_path_within_base(link, base) is False


class TestValidateAlbumId:
    def test_valid_ulid(self):
        # ULID: 26 chars, alphanumeric
        assert validate_album_id('01HNEXAMPLE12345678901234') is True
    
    def test_invalid_length(self):
        assert validate_album_id('short') is False
        assert validate_album_id('a' * 27) is False
    
    def test_invalid_chars(self):
        assert validate_album_id('01HNEXAMPLE!@#$%^&*()_+=') is False
    
    def test_empty(self):
        assert validate_album_id('') is False
        assert validate_album_id(None) is False


class TestSecretMaskFilter:
    def test_masks_api_key(self):
        filter = SecretMaskFilter()
        record = type('LogRecord', (), {
            'msg': 'api_key=secret123&other=value',
            'args': ()
        })()
        
        filter.filter(record)
        
        assert 'secret123' not in record.msg
        assert 'api_key=***' in record.msg
    
    def test_masks_token(self):
        filter = SecretMaskFilter()
        record = type('LogRecord', (), {
            'msg': 'token=abc123',
            'args': ()
        })()
        
        filter.filter(record)
        
        assert 'token=***' in record.msg
    
    def test_masks_in_args(self):
        filter = SecretMaskFilter()
        record = type('LogRecord', (), {
            'msg': 'Request: %s',
            'args': ('api_key=secret123',)
        })()
        
        filter.filter(record)
        
        assert 'secret123' not in record.args[0]
