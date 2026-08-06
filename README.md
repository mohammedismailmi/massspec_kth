# Mass Spec RPA — Phase 1 (local mock loop)

## Setup
```bash
cd massspec_kth
pip install -r requirements.txt
# edit .env and set your GROQ_API_KEY
```

### `.env` format
```
GROQ_API_KEY=gsk_your_groq_api_key_here
```

## Run (two terminals)
1. **Cloud server**
   ```bash
   uvicorn server:app --reload
   ```
2. **Mock agent** (stands in for the Windows lab PC / PrismaPro_01)
   ```bash
   python mock_agent.py
   ```
3. **Dashboard** — open **http://localhost:8000** in your browser (served by the FastAPI server).

Type something like *"Export the latest Methane run"* into the dashboard.

### Flow
```
Dashboard → Server → Groq LLM (llama-3.3-70b-versatile)
  → parses to {"action": "export_file", "target": "Methane"}
  → Mock Agent (simulates the RPA clicks)
  → success event → Server → Dashboard
```

## Architecture
| File | Role |
|------|------|
| `server.py` | FastAPI server — serves the dashboard, routes WebSocket traffic, calls Groq LLM to parse natural language into structured JSON commands |
| `mock_agent.py` | Simulates the Windows lab PC host agent — connects via WebSocket, receives JSON commands, simulates RPA actions |
| `index.html` | Web dashboard UI with auto-reconnecting WebSocket — survives server restarts |
| `.env` | Stores `GROQ_API_KEY` |

## Notes / known gaps to close before Phase 2
- No auth on the WebSocket endpoints yet — fine for local testing, not for exposing publicly.
- `TARGET_MACHINE = "PrismaPro_01"` is hardcoded; Phase 2 should let the dashboard pick/see which agents are online.
- The mock agent only understands `export_file`; extend the `if action == ...` branch as you add real PV MassSpec actions.
- When you're ready to test on the real Windows lab PC in Sweden, `mock_agent.py` is the file to replace with the real host agent that drives PV MassSpec's UI (pywinauto/pyautogui) instead of `asyncio.sleep()`.