# Mass Spec RPA — Phase 1 (local mock loop)

## Setup
```bash
cd mass_spec_rpa
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your real XAI_API_KEY
```

## Run (three terminals)
1. **Cloud server**
   ```bash
   uvicorn server:app --reload
   ```
2. **Mock agent** (stands in for the Windows lab PC / PrismaPro_01)
   ```bash
   python mock_agent.py
   ```
3. **Dashboard** — double-click `index.html` to open it in your browser.

Type something like *"Export the latest Methane run"* into the dashboard.
Flow: dashboard → server → Grok (parses to `{"action": "export_file", "target": "Methane"}`)
→ mock agent (simulates the RPA clicks) → success event → server → dashboard.

## App control on Mac (open_app / open_settings)

`mac_agent.py` is a real (non-mock) agent — run it instead of `mock_agent.py` to
actually open apps and jump to their settings.

**One-time setup — grant Accessibility permission:**
1. System Settings → Privacy & Security → Accessibility
2. Add your terminal app (Terminal.app, iTerm, or whichever runs `python mac_agent.py`)
3. Toggle it on

Without this, `open_settings` will connect and try, but the `Cmd+,` keystroke
will silently fail — you'll see the error message returned over the WebSocket
telling you to check this.

**Run it:**
```bash
uvicorn server:app --reload      # terminal 1
python mac_agent.py              # terminal 2 (instead of mock_agent.py)
# open index.html, type: "open whatsapp and go to its settings"
```

**What actually works reliably:** any app that supports the standard macOS
`Cmd+,` preferences shortcut — WhatsApp Desktop, Slack, Discord, Chrome,
Safari, and most Electron/native apps. Apps with no such shortcut (custom
in-window settings menus, some utility apps) won't work with this approach —
they'd need `pyautogui` coordinate clicks or `pywinauto`-style accessibility-tree
walking instead, which is a fair bit more fragile and app-specific.

Add more spoken-name → exact-app-name mappings in `APP_NAME_MAP` at the top of
`mac_agent.py` as you test new apps.

## Notes / known gaps to close before Phase 2
- `model="grok-beta"` — confirm this is still the correct/current model string on your xAI account before relying on it.
- No auth on the WebSocket endpoints yet — fine for local testing, not for exposing this publicly.
- `target_machine = "PrismaPro_01"` is hardcoded; Phase 2 should let the dashboard pick/see which agents are online.
- The mock agent only understands `export_file`; extend the `if action == ...` branch as you add real PV MassSpec actions.
- When you're ready to test on the real Windows lab PC in Sweden, `mock_agent.py` is the file to replace with the real host agent that drives PV MassSpec's UI (pywinauto/pyautogui) instead of `asyncio.sleep()`.