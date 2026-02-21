"""
Database model tests
"""
import pytest
from datetime import datetime

from music_agent.models import Song, Album, Generation, Cover, State


class TestSong:
    def test_create_song(self, temp_db):
        session = temp_db.session()
        
        song = Song(
            id='01HNEXAMPLE12345678901234',
            title='Test Song',
            original_lyrics='Original lyrics',
            translated_lyrics='Translated lyrics',
            state=State.PENDING
        )
        
        session.add(song)
        session.commit()
        
        # Retrieve
        result = session.query(Song).first()
        assert result.title == 'Test Song'
        assert result.original_lyrics == 'Original lyrics'
        
        session.close()


class TestAlbum:
    def test_create_album(self, temp_db):
        session = temp_db.session()
        
        album = Album(
            id='01HNEXAMPLE12345678901234',
            title='Test Album',
            artist='Test Artist',
            primary_genre='Pop',
            published=False
        )
        
        session.add(album)
        session.commit()
        
        result = session.query(Album).first()
        assert result.title == 'Test Album'
        assert result.artist == 'Test Artist'
        
        session.close()


class TestGeneration:
    def test_create_generation(self, temp_db):
        session = temp_db.session()
        
        gen = Generation(
            id='01HNEXAMPLE12345678901234',
            external_id='suno_123',
            title='Generated Track',
            duration=120.5,
            processed=False
        )
        
        session.add(gen)
        session.commit()
        
        result = session.query(Generation).first()
        assert result.external_id == 'suno_123'
        assert result.processed is False
        
        session.close()
