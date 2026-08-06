import os
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load the .env file containing API keys
load_dotenv()

app = FastAPI()


@app.get("/")
async def serve_dashboard():
    """Serve the web dashboard."""
    return FileResponse("index.html")

# Configure the SDK to route to Groq
client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

SYSTEM_PROMPT = (
    "You are an RPA orchestrator for a mass spectrometer. The user will give you "
    "a natural language command. You must return ONLY a raw, minified JSON object "
    "with 'action' and 'target' keys (e.g., {\"action\": \"export_file\", \"target\": \"Methane\"}). "
    "Do not output markdown, backticks, or conversational text."
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

            # 1. Ask LLM to parse the intent into strict JSON
            try:
                response = await client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": command},
                    ],
                    temperature=0.1,
                )

                structured_command = response.choices[0].message.content.strip()
                print(f"[LLM PARSED] {structured_command}")
            except Exception as e:
                error_msg = f"Error: LLM call failed - {e}"
                print(f"[ERROR] {error_msg}")
                await websocket.send_text(error_msg)
                continue

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