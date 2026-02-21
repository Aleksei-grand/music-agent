# Changelog

Все значимые изменения проекта будут документированы здесь.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/).

## [Unreleased]

### Added
- Initial release
- Suno API integration
- Poe API integration (translation, covers)
- Audio processing (FFmpeg)
- Distributor automation (RouteNote, Sferoom)
- Voice commands (Deepgram)
- Vault system (history, personalization)
- Telegram Bot
- Web UI (FastAPI)
- Security features (rate limiting, path validation)

## [0.2.0] - 2024-01-15

### Added
- 🔒 Security audit and fixes
- 🎤 Voice command recognition
- 📚 Vault system for history
- 🌐 Web UI with real-time progress
- 📤 Export/Import functionality
- 🔄 Retry logic with backoff
- 🚦 Rate limiting

### Security
- Fixed path traversal vulnerabilities
- Added secret masking in logs
- Implemented rate limiting (60 req/min)
- Added security headers (CSP, X-Frame-Options)
- Path validation for file access

## [0.1.0] - 2024-01-01

### Added
- Initial development
- Basic CLI interface
- Database models (SQLAlchemy)
- Audio processor
- Cover generator
- Basic distributor support
