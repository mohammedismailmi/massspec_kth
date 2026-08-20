import asyncio
import json
import os
import subprocess
import time
import urllib.parse
import webbrowser
import winreg
import websockets
from pywinauto import Application

# ---------------------------------------------------------------------------
# IMPORTANT: when this runs inside a UTM Windows VM and the FastAPI server
# runs on your Mac host, "localhost" refers to the VM itself, not the Mac.
# Replace SERVER_HOST below with your Mac's LAN IP (System Settings > Wi-Fi/
# Network > Details, or run `ipconfig getifaddr en0` in Mac Terminal).
# ---------------------------------------------------------------------------
SERVER_HOST = "localhost"  # <-- change to e.g. "192.168.64.1" or your Mac's LAN IP
URI = f"ws://{SERVER_HOST}:8000/ws/agent/PrismaPro_01"

# Windows Settings app deep-links (ms-settings: URI scheme).
# Full reference: https://learn.microsoft.com/windows/uwp/launch-resume/launch-settings-app
SETTINGS_URI_MAP = {
    "display": "ms-settings:display",
    "sound": "ms-settings:sound",
    "bluetooth": "ms-settings:bluetooth",
    "network": "ms-settings:network",
    "wifi": "ms-settings:network-wifi",
    "apps": "ms-settings:appsfeatures",
    "personalization": "ms-settings:personalization",
    "update": "ms-settings:windowsupdate",
    "windows update": "ms-settings:windowsupdate",
    "privacy": "ms-settings:privacy",
    "accounts": "ms-settings:yourinfo",
    "power": "ms-settings:powersleep",
    "storage": "ms-settings:storagesense",
    "system": "ms-settings:",
}

# Common apps: name -> executable/command Windows can resolve directly.
# Bare names like "chrome" aren't on PATH by default on Windows, so
# resolve_app_target() falls back to the registry's App Paths key (the same
# mechanism Windows itself uses to resolve app names) when a name isn't here.
# Store (UWP) apps like WhatsApp have no plain .exe — open_app() falls back
# further to resolve_uwp_app_id() (PowerShell's Get-StartApps) for those.
APP_MAP = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "settings": "ms-settings:",
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "edge": "msedge.exe",
    "microsoft edge": "msedge.exe",
    "task manager": "taskmgr.exe",
    "control panel": "control.exe",
}


def resolve_via_app_paths(exe_name: str) -> str | None:
    """Look up an exe's real install path via the registry, the same way
    Windows itself resolves app names (Start menu, Win+R, etc.)."""
    if not exe_name.lower().endswith(".exe"):
        exe_name += ".exe"
    key_path = rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{exe_name}"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                path, _ = winreg.QueryValueEx(key, None)
                return path
        except FileNotFoundError:
            continue
    return None


def resolve_app_target(name: str) -> str:
    mapped = APP_MAP.get(name.strip().lower(), name.strip())
    resolved = resolve_via_app_paths(mapped)
    return resolved or mapped


def resolve_uwp_app_id(name: str) -> str | None:
    """Find a Microsoft Store (UWP) app's AppUserModelID via PowerShell's
    Get-StartApps — the same catalog the Start Menu searches. Needed for
    apps like WhatsApp, Spotify (Store version), etc. that have no plain .exe."""
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-Command",
                f"(Get-StartApps | Where-Object {{ $_.Name -like '*{name}*' }} "
                "| Select-Object -First 1 -ExpandProperty AppID)",
            ],
            capture_output=True, text=True, timeout=10,
        )
        app_id = result.stdout.strip()
        return app_id or None
    except Exception:
        return None


def start(target: str) -> tuple[bool, str]:
    """Launch an .exe, a URI (ms-settings:...), or anything the shell can resolve."""
    try:
        os.startfile(target)  # Windows-only; works for exes, URIs, and PATH-resolvable commands
        return True, f"Launched '{target}'"
    except FileNotFoundError as e:
        return False, (
            f"Could not launch '{target}': {e}. "
            "If it's an app, add its exact .exe name or full path to APP_MAP."
        )
    except OSError as e:
        return False, f"Could not launch '{target}': {e}"


def open_app(name: str) -> tuple[bool, str]:
    ok, msg = start(resolve_app_target(name))
    if ok:
        return ok, msg

    # Fallback: might be a Microsoft Store app with no plain .exe
    app_id = resolve_uwp_app_id(name)
    if app_id:
        ok2, msg2 = start(f"shell:appsFolder\\{app_id}")
        if ok2:
            return True, f"Launched {name} (Store app)"
        return False, msg2

    return False, msg


def open_os_settings(section: str) -> tuple[bool, str]:
    key = section.strip().lower()
    uri = SETTINGS_URI_MAP.get(key)
    if not uri:
        ok, msg = start("ms-settings:")
        if not ok:
            return False, msg
        return True, (
            f"Opened Settings home (no direct deep-link mapped for '{section}' yet — "
            f"add it to SETTINGS_URI_MAP if you know its ms-settings: URI)"
        )
    ok, msg = start(uri)
    if not ok:
        return False, msg
    return True, f"Opened Settings > {section}"


def search_web(query: str) -> tuple[bool, str]:
    """Opens the query as a Google search in the OS default browser.
    Note: uses whatever browser is set as default, not necessarily one
    just opened by a prior open_app step — set your default browser to
    match if you want them to always be the same."""
    if not query.strip():
        return False, "No search query provided"
    url = "https://www.google.com/search?q=" + urllib.parse.quote(query.strip())
    try:
        webbrowser.open(url)
        return True, f"Searched '{query}' in default browser"
    except Exception as e:
        return False, f"Could not open search: {e}"


ACTIONS = {
    "open_app": open_app,
    "open_os_settings": open_os_settings,
    "search_web": search_web,
}

WHATSAPP_SEARCH_AUTO_ID = "_r_c_"  # found via inspect_whatsapp_v4.py — stable even as text changes

# pywinauto's type_keys() treats these as special-key syntax (SendKeys-style).
# Wrap each in braces so they're typed as literal characters instead.
_TYPE_KEYS_SPECIAL = set("+^%~(){}")


def _escape_for_type_keys(text: str) -> str:
    return "".join(f"{{{ch}}}" if ch in _TYPE_KEYS_SPECIAL else ch for ch in text)


def _connect_whatsapp(retries: int = 5, delay: float = 1.0):
    """WhatsApp may still be launching (e.g. right after open_app), so retry
    briefly instead of failing on the first missed connection."""
    last_error = None
    for _ in range(retries):
        try:
            app = Application(backend="uia").connect(title_re=".*WhatsApp.*", timeout=5)
            return app.top_window()
        except Exception as e:
            last_error = e
            time.sleep(delay)
    raise RuntimeError(f"Could not connect to WhatsApp after {retries} attempts: {last_error}")


def whatsapp_send_message(contact: str, message: str) -> tuple[bool, str]:
    if not contact.strip():
        return False, "No contact name provided"
    if not message.strip():
        return False, "No message text provided"

    try:
        window = _connect_whatsapp()
    except Exception as e:
        return False, str(e)

    window.set_focus()

    # 1. Focus the search box (by auto_id, not name — its name changes as you type)
    try:
        search_box = window.child_window(auto_id=WHATSAPP_SEARCH_AUTO_ID, control_type="Edit")
        search_box.click_input()
        search_box.type_keys("^a{BACKSPACE}", pause=0.05)  # clear any existing text
        search_box.type_keys(_escape_for_type_keys(contact), with_spaces=True, pause=0.03)
    except Exception as e:
        return False, f"Could not use the search box: {e}"

    time.sleep(1.2)  # let search results render

    # 2. Click the first search result whose visible name contains the contact name
    try:
        result_btn = None
        for ctrl in window.descendants(control_type="Button"):
            try:
                if not ctrl.is_visible():
                    continue
                name = ctrl.window_text()
            except Exception:
                continue
            if contact.strip().lower() in name.lower():
                result_btn = ctrl
                break
        if result_btn is None:
            return False, f"No search result found matching '{contact}'"
        result_btn.click_input()
    except Exception as e:
        return False, f"Could not click the search result: {e}"

    time.sleep(1.0)  # let the chat open

    # 3. The message box is the only OTHER visible Edit control (the search
    # box is excluded by auto_id) — found via inspect_whatsapp_v4.py, it has
    # no accessible name of its own.
    try:
        message_box = None
        for ctrl in window.descendants(control_type="Edit"):
            try:
                if ctrl.automation_id() == WHATSAPP_SEARCH_AUTO_ID:
                    continue
                if not ctrl.is_visible():
                    continue
                message_box = ctrl
                break
            except Exception:
                continue
        if message_box is None:
            return False, "Could not find the message box — is the chat actually open?"
        message_box.click_input()
    except Exception as e:
        return False, f"Could not focus the message box: {e}"

    # 4. Type the message and press Enter to send (WhatsApp has no separate
    # Send button until you've typed something, so Enter is the reliable path)
    try:
        message_box.type_keys(_escape_for_type_keys(message), with_spaces=True, pause=0.02)
        time.sleep(0.2)
        message_box.type_keys("{ENTER}")
    except Exception as e:
        return False, f"Could not type/send the message: {e}"

    return True, f"Sent message to '{contact}'"


async def execute_step(step: dict) -> dict:
    action = step.get("action", "")
    target = step.get("target", "")

    if action == "send_whatsapp_message":
        contact = target
        message_text = step.get("message", "")
        try:
            ok, msg = whatsapp_send_message(contact, message_text)
        except Exception as e:
            ok, msg = False, str(e)
        return {"status": "success" if ok else "error", "action": action, "target": target, "message": msg}

    handler = ACTIONS.get(action)
    if not handler:
        return {
            "status": "error",
            "action": action,
            "target": target,
            "message": f"Unknown action '{action}' (windows_agent supports: "
                       f"{list(ACTIONS) + ['send_whatsapp_message']})",
        }
    try:
        ok, message = handler(target)
        return {
            "status": "success" if ok else "error",
            "action": action,
            "target": target,
            "message": message,
        }
    except Exception as e:
        return {"status": "error", "action": action, "target": target, "message": str(e)}


async def run_agent():
    try:
        async with websockets.connect(URI) as ws:
            print(f"Windows Agent connected to {URI} as PrismaPro_01. Waiting for commands...")

            while True:
                message = await ws.recv()
                print(f"\n[INCOMING] {message}")

                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    print("Error: malformed JSON, ignoring.")
                    continue

                steps = payload if isinstance(payload, list) else [payload]

                for step in steps:
                    result = await execute_step(step)
                    print(f">> {result}")
                    await ws.send(json.dumps(result))

    except ConnectionRefusedError:
        print(
            f"Could not connect to {URI}. Is the server running on the Mac, "
            "is SERVER_HOST set to the Mac's actual LAN IP, and is the Mac "
            "firewall allowing incoming connections on port 8000?"
        )


if __name__ == "__main__":
    asyncio.run(run_agent())