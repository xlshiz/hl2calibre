# Changelog

## [Unreleased]

### Added
- KOReader annotation import (sidecar Lua files)
- KOReader device sync (selected book + all books)
- GitHub Actions CI and release workflow

### Changed
- Menu restructured to 3124 order
- Annotation timestamp uses current import time (prevents removed-override bug)

### Fixed
- Support new KOReader annotations dict format
- Support page field fallback for bookmarks without pos0/pos1
- Use current timestamp to prevent merge losses
- Clear viewer cache before import
- Rebuild FTS index after import
- Menu items not showing (popup_type and create_menu_action fixes)
