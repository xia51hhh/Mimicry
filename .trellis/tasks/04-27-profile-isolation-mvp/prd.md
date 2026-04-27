# Browser Profile Isolation — Phase 1 MVP

## Goal
Complete the Profile system so users can create isolated browser profiles with independent fingerprints, proxies, and persistent data directories, then select a profile when launching the browser.

## Architecture Decision
- **Multi-instance model**: Single Sidecar process, multiple BrowserContexts (distinguished by session_id)
- **Workflow binding**: Block-level cross-profile (future); MVP = single instance with profile selection
- **UI location**: ActivityBar browser icon → Sidebar panel for profile list & instance status

## Existing Foundation (already working)
- Profile CRUD: Frontend (ProfileManager/Dialog) → Rust commands → SQLite
- `browser_launch(profile_id)` → DB lookup → sidecar `browser.launch({profile})`
- Python `controller.launch(profile=dict)` applies profile to Camoufox kwargs
- `BrowserProfile` dataclass + `get_profile_data_dir()` in `sidecar/browser/profile.py`

## Tasks

### T1: Rewrite ProfileManager/Dialog UI
- Replace Tailwind utility classes with scoped CSS using project CSS variables
- Match SettingsView visual style (cards, spacing, buttons)
- Add delete confirmation dialog
- Add form validation: name required, duplicate check

### T2: Complete ProfileDialog fields
- Add proxy config form: server (required), username, password (optional)
- Add os_target selector (keep existing)
- Add user_data_dir display (auto-assigned, read-only)
- fingerprint: defer to Phase 3 (JSON editor)

### T3: Auto-assign user_data_dir on creation
- Rust `profile_create` command: after DB insert, call `get_profile_data_dir(id)` to create directory
- Or: Rust-side create `{app_data}/profiles/{id}/` and store path in DB
- On delete: optionally clean up directory (with user confirmation)

### T4: Profile selection on browser launch
- Toolbar launch button: if profiles exist, show dropdown to pick profile
- If no profiles, launch with default (no profile)
- Pass selected `profileId` to `browser.launch()`

### T5: ActivityBar + Sidebar browser panel
- Add Globe/Browser icon to ActivityBar
- New Sidebar panel: profile list (with status badges)
- Quick-launch from sidebar: click profile → launch browser
- Show connected/disconnected status per profile

### T6: i18n
- Add `profile.*` keys to `en.json` and `zh-CN.json`
- Cover: CRUD labels, form fields, validation messages, status badges

### T7: Remove ProfileManager from SettingsView
- SettingsView should NOT contain ProfileManager (it belongs in Sidebar)
- Keep only Camoufox install/status in SettingsView browser section

## Out of Scope (Phase 2+)
- Multiple concurrent browser instances
- Instance management UI (tabs per instance)
- Block-level profile binding in workflows
- Fingerprint JSON editor
- Cookie/localStorage management
- Profile import/export

## Completion Criteria
- [ ] Profile CRUD with validated form (name, proxy, os_target)
- [ ] user_data_dir auto-created per profile
- [ ] Browser launches with selected profile's config
- [ ] ActivityBar → Sidebar panel shows profile list
- [ ] Bilingual i18n complete
- [ ] TypeScript + Rust compilation passes
- [ ] Manual test: create profile → launch → verify isolated data dir
