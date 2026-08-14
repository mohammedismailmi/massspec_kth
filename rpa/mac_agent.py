import asyncio
import json
import subprocess
import time
import websockets

URI = "ws://localhost:8000/ws/agent/PrismaPro_01"

# Map common spoken names -> exact macOS app names.
# Add to this as you test more apps.
APP_NAME_MAP = {
    "whatsapp": "WhatsApp",
    "slack": "Slack",
    "discord": "Discord",
    "chrome": "Google Chrome",
    "safari": "Safari",
    "spotify": "Spotify",
    "notes": "Notes",
    "mail": "Mail",
    "calendar": "Calendar",
    "terminal": "Terminal",
}


def resolve_app_name(target: str) -> str:
    key = target.strip().lower()
    return APP_NAME_MAP.get(key, target.strip())


def run_applescript(script: str) -> tuple[bool, str]:
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True
    )
    ok = result.returncode == 0
    return ok, (result.stderr or result.stdout).strip()


def open_app(app_name: str, wait_seconds: float = 1.2) -> tuple[bool, str]:
    ok, msg = run_applescript(f'tell application "{app_name}" to activate')
    if not ok:
        return False, f"Could not open '{app_name}': {msg or 'not found'}"
    time.sleep(wait_seconds)  # give the app time to actually come to front
    return True, f"Opened {app_name}"


def open_settings(app_name: str) -> tuple[bool, str]:
    ok, msg = open_app(app_name)
    if not ok:
        return False, msg

    # Standard macOS shortcut for Preferences/Settings, works for most
    # native + Electron apps (WhatsApp, Slack, Discord, Chrome, Safari...)
    script = f'''
    tell application "{app_name}" to activate
    delay 0.5
    tell application "System Events"
        keystroke "," using command down
    end tell
    '''
    ok, msg = run_applescript(script)
    if not ok:
        return False, (
            f"Could not trigger settings for '{app_name}': {msg}. "
            "Check System Settings > Privacy & Security > Accessibility "
            "and make sure your terminal/Python has permission."
        )
    return True, f"Opened settings/preferences for {app_name}"


ACTIONS = {
    "open_app": lambda target: open_app(resolve_app_name(target)),
    "open_settings": lambda target: open_settings(resolve_app_name(target)),
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
            "message": f"Unknown action '{action}'",
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
            print("Mac Agent connected as PrismaPro_01. Waiting for commands...")

            while True:
                message = await ws.recv()
                print(f"\n[INCOMING] {message}")

                try:
                    payload = json.loads(message)
                except json.JSONDecodeError:
                    print("Error: malformed JSON, ignoring.")
                    continue

                # Grok may return a single step or a list of steps
                steps = payload if isinstance(payload, list) else [payload]

                for step in steps:
                    result = await execute_step(step)
                    print(f">> {result}")
                    await ws.send(json.dumps(result))

    except ConnectionRefusedError:
        print("Could not connect. Is the FastAPI server running? (uvicorn server:app --reload)")


if __name__ == "__main__":
    asyncio.run(run_agent())