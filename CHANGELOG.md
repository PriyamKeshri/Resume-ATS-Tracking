# Changelog

All notable changes to this project are documented here, most recent first.
This project doesn't cut versioned releases — it's a continuously deployed
Streamlit app — so entries are grouped by date instead of a version number.

## 2026-08-23

### Added
- Test suite for `resume_parser.py` — 9 `pytest` tests covering PDF/DOCX/TXT
  extraction, DOCX table-cell text, and the "no extractable text" error paths.
- GitHub Actions CI workflow — lints with `pyflakes` and runs the test suite
  on every push and pull request to `main`.

## 2026-08-22

### Added
- "How It Works" section in the README, including a Mermaid flow diagram of
  the analysis pipeline plus a step-by-step table.

### Fixed
- Mermaid diagram not rendering on GitHub — removed `<br/>` HTML tags from
  node labels, since GitHub's Mermaid renderer runs in a sandboxed mode that
  doesn't allow HTML inside labels.

## 2026-08-20

### Removed
- Dead code in `app.py`: an unused `io` import and a redundant session-state
  re-fetch right before the Export tab.

## 2026-08-18

### Added
- App screenshots in the README (homepage, analysis results, more-tools tabs).

### Changed
- Streamlined the README: dropped the project-structure section, centered
  the header block, and switched the Tech Stack list to a badge row.

## 2026-08-17

### Added
- Grammar and spelling check tool.
- Features overview section on the homepage, grouped into Analyze / Improve /
  Apply, each with a small inline icon.
- MIT license.
- Black background + light-green accent theme (`.streamlit/config.toml`),
  with matching feature icons and score-tier colors.
- Live Streamlit Community Cloud deployment link in the README.

### Changed
- Full UI redesign: editorial serif headline, small-caps section labels,
  card-based sections, a ring-style score gauge, outlined keyword tags, and
  tabs for the cover letter / bullet rewriter / export tools. Removed all
  emoji from the app UI in favor of this more formal, report-style look.

### Fixed
- Pinned the Python runtime to 3.11 for Streamlit Cloud, ruling out a crash
  caused by Python 3.14 not yet having stable wheels for some C-extension
  dependencies (`pyarrow`, `pydantic-core`, `lxml`, `cryptography`).

## 2026-08-16

### Added
- Initial release: a Streamlit app powered by the Gemini API — ATS-style
  match scoring, keyword gap analysis, strengths/weaknesses, suggestions,
  a cover letter generator, and a resume bullet rewriter.

### Changed
- Restyled the README with badges, a feature table, and numbered quick-start
  steps.
- Updated the analysis spinner message to be more descriptive.
