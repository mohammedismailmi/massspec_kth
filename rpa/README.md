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

## App & Settings control on Windows (UTM VM)

`windows_agent.py` is the real agent for Windows — it launches apps and jumps
straight into specific Settings panes using the `ms-settings:` deep-link
scheme (e.g. `ms-settings:display`), which is far more reliable than clicking
through menus.

**Networking — read this first.** Your Mac and the UTM Windows VM are two
separate machines on the network. `localhost` inside the VM points at the VM,
not your Mac, so the agent can't just connect to `ws://localhost:8000`.

1. On your **Mac**, find its LAN IP:
   ```bash
   ipconfig getifaddr en0
   ```
   (or check System Settings → Wi-Fi/Network → Details). You'll get something
   like `192.168.64.1` or `192.168.1.23`.
2. Open `windows_agent.py` and set `SERVER_HOST` to that IP.
3. Make sure UTM's network mode lets the VM reach the host (Shared Network
   mode works out of the box; Bridged also works if both are on the same
   LAN). Check UTM's VM network settings if the connection is refused.
4. macOS Firewall may block the incoming connection — if `python
   windows_agent.py` inside the VM can't connect, check System Settings →
   Network → Firewall and allow incoming connections for Python/uvicorn, or
   temporarily disable the firewall to confirm that's the issue.

**Run it:**
```bash
# On the Mac:
uvicorn server:app --reload --host 0.0.0.0   # --host 0.0.0.0 so the VM can reach it
python -m http.server 5500                    # optional: serve index.html so the VM's browser can open it too

# In the Windows VM (Python installed, requirements.txt installed):
python windows_agent.py
```
Then type into the dashboard: *"open settings and go to display"* — Grok
parses it to `[{"action": "open_os_settings", "target": "display"}]`, the
agent runs `os.startfile("ms-settings:display")`, and Windows Settings opens
directly on the Display page.

**What works reliably:** any Settings section with a known `ms-settings:` URI
(display, sound, bluetooth, network, wifi, apps, update, privacy, accounts,
power, storage — full list in `SETTINGS_URI_MAP`). Add more sections there as
you need them — Microsoft's reference list is at
https://learn.microsoft.com/windows/uwp/launch-resume/launch-settings-app

**What's more fragile:** opening arbitrary third-party apps (`APP_MAP`) works
for anything with a normal `.exe` on PATH, but Microsoft Store / UWP apps
(e.g. WhatsApp from the Store) need a `shell:AppsFolder\<AppUserModelId>`
path instead of a plain exe name — flag it if you hit this and we'll add
proper UWP app resolution.

## Notes / known gaps to close before Phase 2
- `model="grok-beta"` — confirm this is still the correct/current model string on your xAI account before relying on it.
- No auth on the WebSocket endpoints yet — fine for local testing, not for exposing this publicly.
- `target_machine = "PrismaPro_01"` is hardcoded; Phase 2 should let the dashboard pick/see which agents are online.
- The mock agent only understands `export_file`; extend the `if action == ...` branch as you add real PV MassSpec actions.
- When you're ready to test on the real Windows lab PC in Sweden, `mock_agent.py` is the file to replace with the real host agent that drives PV MassSpec's UI (pywinauto/pyautogui) instead of `asyncio.sleep()`.