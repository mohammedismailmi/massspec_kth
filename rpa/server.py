import os
import json
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load the .env file containing OPENROUTER_API_KEY
load_dotenv()

app = FastAPI()

# Configure the SDK to route to OpenRouter instead of OpenAI
client = AsyncOpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)

SYSTEM_PROMPT = (
    "You are an RPA orchestrator. Given a natural language command, return ONLY a "
    "raw, minified JSON array of step objects, each with 'action' and 'target' keys. "
    "Do not output markdown, backticks, or conversational text. Never repeat the same "
    "step more than once.\n\n"
    "Supported actions:\n"
    "- open_app: target is the app name (e.g. WhatsApp, Slack, Chrome, Notepad)\n"
    "- open_settings: target is the app name; opens the app then triggers its own settings/preferences panel\n"
    "- open_os_settings: target is a Windows Settings section, e.g. display, sound, bluetooth, "
    "network, wifi, apps, personalization, update, privacy, accounts, power, storage, system\n"
    "- search_web: target is the search query text; opens it as a web search in the default browser\n"
    "- send_whatsapp_message: target is the exact contact name as it appears in WhatsApp; also include "
    "a 'message' key with the message text to send\n"
    "- export_file: target is the compound/run name, for mass spec data exports\n\n"
    "If the command implies multiple steps (e.g. 'open WhatsApp and go to its settings'), "
    "return them as separate steps in order, e.g.:\n"
    "[{\"action\": \"open_app\", \"target\": \"WhatsApp\"}, "
    "{\"action\": \"open_settings\", \"target\": \"WhatsApp\"}]\n\n"
    "For 'open settings and go to display' (Windows system settings, not an app's own "
    "settings), return:\n"
    "[{\"action\": \"open_os_settings\", \"target\": \"display\"}]\n\n"
    "For 'open <browser> and search <query>', return exactly two steps — one open_app "
    "for the browser, one search_web for the query, e.g.:\n"
    "[{\"action\": \"open_app\", \"target\": \"Microsoft Edge\"}, "
    "{\"action\": \"search_web\", \"target\": \"KTH Royal Institute of Technology\"}]\n\n"
    "For 'open whatsapp and text <name> <message>', return exactly two steps — one "
    "open_app for WhatsApp, one send_whatsapp_message with the contact as target and "
    "the message text in a separate 'message' key, e.g.:\n"
    "[{\"action\": \"open_app\", \"target\": \"WhatsApp\"}, "
    "{\"action\": \"send_whatsapp_message\", \"target\": \"Mohammed Ismail\", \"message\": \"hi\"}]"
)

TARGET_MACHINE = "PrismaPro_01"

# In-memory storage for our WebSockets
connected_agents: dict[str, WebSocket] = {}
connected_clients: list[WebSocket] = []


@app.websocket("/ws/agent/{machine_id}")
async def agent_endpoint(websocket: WebSocket, machine_id: str):
    """Endpoint for the Windows Lab PC (or Mock Agent) to connect to."""
    await websocket.accept()
    connected_agents[machine_id] = websocket
    print(f"[SYSTEM] Agent {machine_id} connected.")
    try:
        while True:
            # Listen for updates from the lab PC
            data = await websocket.receive_text()
            print(f"[{machine_id}] {data}")

            # Broadcast lab updates back to every connected web dashboard
            for client_ws in connected_clients:
                await client_ws.send_text(f"Lab Update: {data}")
    except WebSocketDisconnect:
        connected_agents.pop(machine_id, None)
        print(f"[SYSTEM] Agent {machine_id} disconnected.")


@app.websocket("/ws/client")
async def client_endpoint(websocket: WebSocket):
    """Endpoint for the Web Dashboard to connect to."""
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            # Receive natural language command from the web dashboard
            command = await websocket.receive_text()
            print(f"[USER COMMAND] {command}")

            # 1. Ask the LLM to parse the intent into strict JSON
            response = await client.chat.completions.create(
                model="nvidia/nemotron-3-ultra-550b-a55b:free",
                extra_headers={
                    # Optional — OpenRouter uses these for its public leaderboard/analytics,
                    # not required for the API to work.
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "Mass Spec RPA",
                },
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": command},
                ],
                temperature=0.1,
            )

            raw_content = response.choices[0].message.content.strip()
            # Nemotron is a reasoning model and may emit a <think>...</think>
            # trace before the actual JSON — strip it so parsing doesn't break.
            structured_command = re.sub(
                r"<think>.*?</think>", "", raw_content, flags=re.DOTALL
            ).strip()
            print(f"[LLM PARSED] {structured_command}")

            # 2. Route the JSON command to the Mock/Host Agent
            if TARGET_MACHINE in connected_agents:
                await connected_agents[TARGET_MACHINE].send_text(structured_command)
                await websocket.send_text(
                    f"System: Command routed to {TARGET_MACHINE} -> {structured_command}"
                )
            else:
                await websocket.send_text("Error: Lab agent is currently offline.")

    except WebSocketDisconnect:
        connected_clients.remove(websocket)