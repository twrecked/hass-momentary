# 🚀 Momentary v0.8.0-beta.2 — Repository Modernization & Final Beta Pre-Release

> ### 🧪 Final Beta Pre-Release Notice
> **Momentary v0.8.0-beta.2 is the final expected pre-release prior to the general v0.8.0 stable release.**
>
> This update standardizes repository developer tooling, refactors local deployment and release publishing scripts into `scripts/`, updates release automation, and validates integration stability across Home Assistant 2026.7+.
>
> If you encounter any remaining issues, edge cases, or regression anomalies, please [open a GitHub issue](https://github.com/twrecked/hass-momentary/issues) with your configuration snippet and debug logs.

---

## 🌟 What's New in v0.8.0-beta.2

### 1. Developer Tooling & Repository Structure
- **Scripts Directory Reorganization**: Relocated repository utility scripts into a clean `scripts/` directory to declutter the repository root and align with sibling integrations (`hass-pwrstat`, `hass-phantom-power`).
- **Modernized Installation Script (`scripts/install`)**:
  - Dynamically calculates the repository root directory regardless of current working directory.
  - Formats sync command preview with updated script paths.
  - Supports YAML, Python, and JSON asset syncing into Home Assistant configuration directory.
- **GitHub Release Automation (`scripts/publish-release`)**:
  - Added an automated release publisher leveraging GitHub CLI (`gh`).
  - Automatically identifies the active git branch (`git rev-parse --abbrev-ref HEAD`).
  - Verifies presence of versioned release notes under `docs/RELEASE_NOTES_<tag>.md`.
  - Automatically tags alpha and beta releases with `--prerelease`.
- **Repository Cleanliness**:
  - Updated `.gitignore` patterns to match `AGENTS*.md` and ignore deprecated release scripts (`update-repo*`).
  - Updated `AGENTS.local.md` instructions with the new `./scripts/install` commands.

### 2. Prior v0.8 Highlights
- **Interactive Visual Device Editor**: Card-based builder for visual switch configuration, hosted online or locally, with one-click webhook synchronization back into Home Assistant.
- **Modern Validation Engine Compatibility**: Full support for Home Assistant's `probatio` validation engine with fallback to `voluptuous`.
- **Async & Lifecycle Resilience**: Synchronous `@callback` event handling, leak-free timer replacement upon rapid re-triggering, and timezone-aware UTC state restoration.
- **Atomic File I/O**: Executor-backed non-blocking atomic file writes.

---

## 🛠️ Testing Checklist for Beta Testers

1. **Local Deployment**: Deploy to a local Home Assistant test environment using `./scripts/install go /path/to/home-assistant/config`.
2. **Visual Device Editor**: Launch the editor from Home Assistant (**Settings -> Devices & Services -> Momentary -> Configure**), edit switches, and confirm webhook synchronization reloads cleanly.
3. **Timer Expiration & Re-Triggering**: Test rapid clicking and confirm countdown resets without premature termination.
4. **State Restoration**: Confirm switch countdown states survive Home Assistant restarts cleanly.
