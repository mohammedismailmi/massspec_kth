import asyncio
import json
import os
import subprocess
import urllib.parse
import webbrowser
import winreg
import websockets

# ---------------------------------------------------------------------------
# IMPORTANT: when this runs inside a UTM Windows VM and the FastAPI server
# runs on your Mac host, "localhost" refers to the VM itself, not the Mac.
# Replace SERVER_HOST below with your Mac's LAN IP (System Settings > Wi-Fi/
# Network > Details, or run `ipconfig getifaddr en0` in Mac Terminal).
# ---------------------------------------------------------------------------
SERVER_HOST = "192.168.1.2"  # <-- change to e.g. "192.168.64.1" or your Mac's LAN IP
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
# For Store (UWP) apps like WhatsApp installed via Microsoft Store, this
# won't work — those need a shell:AppsFolder\<AppUserModelId> path instead;
# flag it if you hit it and we'll add proper UWP resolution.
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
    return start(resolve_app_target(name))


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


async def execute_step(step: dict) -> dict:
    action = step.get("action", "")
    target = step.get("target", "")
    handler = ACTIONS.get(action)
    if not handler:
        return {
            "status": "error",
            "action": action,
            "target": target,
            "message": f"Unknown action '{action}' (windows_agent supports: {list(ACTIONS)})",
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