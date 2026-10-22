# AGENTS.local.md — hass-momentary Local Guidelines

These rules take precedence over global guidelines for any work in `hass-momentary`.

---

## 1. Preventing Unintended Side-Effects & Regressions

### A. State Persistence & Restoration (`RestoreEntity`)
- **Never assume saved attribute values are non-null:** When restoring state (`async_get_last_state()` / `_restore_state()`), attributes from prior runs may be `None`, stale, or from an older version of Home Assistant.
- **Always guard `.get(ATTR, default)`:** If an attribute exists in `state.attributes` with a value of `None`, `dict.get(key, default)` returns `None`, **not** `default`. Always explicitly validate values:
  ```python
  val = state.attributes.get(ATTR)
  if val is None:
      val = default_val
  ```
- **Datetime parsing and timezone safety:**
  - Saved ISO datetimes must be parsed safely using `dt_util.parse_datetime()` or guarded with `try...except (ValueError, TypeError)`.
  - Always verify datetime objects are timezone-aware before comparing against `dt_util.utcnow()`.
- **Lifecycle completeness:** Any state or timer modified must be audited across the entire entity lifecycle:
  1. `__init__` / initial config
  2. `_create_state` (fresh entity)
  3. `_restore_state` (persisted entity across HA restart)
  4. Entity service calls (`turn_on`, `turn_off`)
  5. State reporting / `_update_attributes`
  6. Teardown / `async_will_remove_from_hass` (ensure active timers are cancelled)

### B. Home Assistant Entity Contract Invariants
- **Proper Callback & Async Semantics:**
  - Never decorate an `async def` with `@callback`. In Home Assistant, `@callback` functions must be synchronous and run directly on the event loop.
  - When state attributes change in memory on the event loop, use `self.async_write_ha_state()`, not `schedule_update_ha_state()`.
- **Timer Management:**
  - Always cancel any existing timer callback before assigning a new one to prevent orphaned timer firing.
  - Cancel all active timers during `async_will_remove_from_hass()`.
- **Property getters vs Extra State Attributes:**
  - Do not duplicate HA base entity properties (e.g., `is_on`) into `extra_state_attributes`. HA core handles those natively.

---

## 2. Supply Chain & Nefarious Behavior Checks

When reviewing contributions or third-party PRs:
- **Zero External Network Egress:** `hass-momentary` is strictly an in-memory momentary switch integration (`local_push`).
  - Flag any imports of `requests`, `urllib`, `aiohttp.ClientSession`, `socket`, `subprocess`, or raw OS pipes in integration runtime code.
  - Do not introduce unapproved third-party runtime dependencies (e.g. `aiofiles`). Use standard library file operations wrapped in `await hass.async_add_executor_job(...)`.
- **Manifest & Dependency Audits (`manifest.json`):**
  - Reject PRs that add unexpected entries to `requirements`, `dependencies`, or `codeowners` without explicit maintainer sign-off.
- **Code Obfuscation & Dynamic Execution:**
  - Reject any usage of `eval()`, `exec()`, dynamic `__import__()`, base64-decoded payloads, or hidden attributes (`getattr(..., payload)`).
- **Filesystem Boundaries:**
  - No writes outside of HA config directory boundaries or intended state files (no path traversals, tempfile hijacking, or dotfile manipulation).

---

## 3. Issue Triage & Diagnostics Workflow

When investigating user-reported issues:

### A. Minimal Reproduction First
- **Extract Minimal YAML Config:** Always distill the user's config down to the absolute minimal momentary switch definition (e.g., 3–5 lines).
- **Identify Core vs Integration Updates:** Ask or check:
  - Which Home Assistant Core version broke it?
  - Which `hass-momentary` release introduced it?
- **Test Matrix Checklist:**
  - [ ] Tested with `mode: on` vs `mode: off`
  - [ ] Tested with `cancellable: true` vs `cancellable: false`
  - [ ] Tested rapid double-toggling (cancelling and resetting timers)
  - [ ] Tested across HA restart / integration reload during an active countdown
  - [ ] Tested turning on/off via both direct service call and UI card toggle

### B. Standard Debug Log Request
- Provide users with the exact configuration snippet to enable debug logging when they report issues:
  ```yaml
  logger:
    default: info
    logs:
      custom_components.momentary: debug
  ```
