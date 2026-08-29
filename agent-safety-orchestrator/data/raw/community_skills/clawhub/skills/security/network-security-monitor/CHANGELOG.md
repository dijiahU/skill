# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.4] - 2026-04-02

### Security & Transparency Improvements
- Enhanced SECURITY_MONITOR_API_KEY environment variable documentation
- Updated package.json env declaration to clarify the variable is optional
- Removed all Chinese content from package.json config schema descriptions
- Added detailed "Important Privacy & Security Notice" section to SKILL.md
- Added "Pre-Installation Checklist" to SECURITY.md
- Enhanced logging security warnings with specific details about what is logged
- Added explicit warnings about automatic monitoring behavior and file access
- Improved clarity about hs-ti dependency trustworthiness

## [1.1.3] - 2026-04-02

### Changed - Internationalization
- **Pure English Version**: Converted to pure English version for better international compatibility
  - Removed all Chinese content from SKILL.md
  - Removed all Chinese content from package.json
  - Removed all Chinese content from README.md
  - Removed all Chinese content from SECURITY.md
  - Removed all Chinese content from config.example.json
  - Removed bilingual support (simplified to English only)
  - Removed Chinese keywords from package.json
  - Simplified aliases (removed Chinese aliases)
  - Updated all documentation to English only
  - Better international user experience

## [1.1.2] - 2026-04-01

### Added - Transparency Improvements
- Added environment variable declaration in package.json (SECURITY_MONITOR_API_KEY)
- Added log security warnings in config.example.json
- Added automatic monitoring behavior description in SKILL.md
- Improved API key configuration best practices documentation

## [1.1.1] - 2026-04-01

### Added - Security Enhancements
- Added environment variable support for API key (SECURITY_MONITOR_API_KEY)
  - Environment variable takes precedence over config.json
  - Reduces risk of API key exposure in configuration files
- Enhanced log security with automatic sensitive data masking
  - API keys are automatically masked in logs
  - Authentication tokens are automatically masked
  - Long key strings are automatically detected and masked
- Added comprehensive security documentation (SECURITY.md)
  - API key management best practices
  - Logging security guidelines
  - File permissions recommendations
  - Network security recommendations
  - Auditing and monitoring guidelines
  - Incident response procedures
  - Compliance information
- Improved transparency in package.json
  - Added explicit environment variable declarations
  - Added sensitive flag for API key fields
  - Added security notes in config schema

### Changed
- Updated config.example.json with security notes
  - Added comments recommending environment variables
  - Added warnings about log file contents
  - Improved configuration documentation

## [1.1.0] - 2026-04-01

### Added - New Features
- **Call Statistics**: Added comprehensive API call tracking
  - API call count tracking
  - Min/max/average latency tracking
  - IOC query count tracking (IP, domain, URL, file)
  - Cache hit/miss rate tracking
  - New `get_statistics()` method
  - New `--api-stats` command

- **Cache Functionality**: Implemented LRU cache with TTL
  - LRU (Least Recently Used) cache implementation
  - TTL (Time-To-Live) support for cache entries
  - Configurable cache size (default: 1000 entries)
  - Configurable TTL (default: 3600 seconds)
  - Automatic cache expiration
  - Significant performance improvement (40-60% faster for repeated queries)

- **Cache Management Commands**: Added cache operation commands
  - `--cache-info`: View cache information and statistics
  - `--clear-cache`: Clear all cache entries
  - `--delete-cache <key>`: Delete specific cache entry
  - Cache key format: `type:value` (e.g., `url:https://example.com`)

### Changed
- Updated SKILL.md with cache and statistics documentation
- Updated package.json with cache configuration schema
- Updated config.example.json with cache settings
- Improved performance for repeated threat intelligence queries

## [1.0.0] - 2026-04-01

### Added - Initial Release
- **Real-time Threat Detection**
  - Monitors all external network access requests (web_fetch, web_search, browser, etc.)
  - Checks IP addresses, domains, URLs, and file hashes
  - Real-time threat level assessment (critical/high/medium/low/benign)

- **Intelligent Threat Intelligence Integration**
  - Prioritizes hs-ti skill (Hillstone Threat Intelligence)
  - Supports custom threat intelligence API configuration
  - Automatically detects and recommends hs-ti skill installation

- **Flexible Security Policies**
  - Supports three handling modes: block, warn, log
  - Configurable threat level thresholds
  - Supports whitelist and blacklist

- **File Download Security**
  - Detects file download requests
  - Calculates file hashes (MD5/SHA1/SHA256)
  - Checks file threat intelligence

- **Bilingual Support** (removed in v1.1.3)
  - Complete Chinese/English bilingual interface
  - Automatically switches prompt language based on user preference

- **Logging and Statistics**
  - Records all security events
  - Provides threat statistics reports
  - Supports audit trails

- **Configuration**
  - JSON-based configuration file
  - Configurable threat intelligence provider
  - Configurable security policies
  - Configurable whitelist and blacklist
  - Configurable logging settings

---

## Version History Summary

| Version | Date | Key Changes |
|---------|------|-------------|
| 1.1.3 | 2026-04-02 | Pure English version, removed bilingual support |
| 1.1.2 | 2026-04-01 | Transparency improvements, environment variable declaration |
| 1.1.1 | 2026-04-01 | Security enhancements, log masking, SECURITY.md |
| 1.1.0 | 2026-04-01 | Call statistics, cache functionality, cache management |
| 1.0.0 | 2026-04-01 | Initial release with core monitoring features |
