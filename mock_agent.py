import asyncio
import json
import websockets

URI = "ws://localhost:8000/ws/agent/PrismaPro_01"


async def run_mock_agent():
    try:
        async with websockets.connect(URI) as ws:
            print("Mock Agent successfully connected to the cloud server.")
            print("Waiting for RPA instructions...")

            while True:
                # 1. Receive the JSON command from Grok via the server
                message = await ws.recv()
                print(f"\n[INCOMING COMMAND] {message}")

                try:
                    data = json.loads(message)
                    action = data.get("action", "")

                    # 2. Simulate the execution
                    if action == "export_file":
                        print(">> Simulating RPA: Hooking into PV MassSpec process...")
                        await asyncio.sleep(1.5)  # Simulating physical UI clicks
                        print(">> Clicking 'Export to ASCII'...")
                        await asyncio.sleep(1.0)

                        # 3. Report success back to the dashboard
                        success_payload = json.dumps(
                            {"status": "success", "event": "data_extracted"}
                        )
                        await ws.send(success_payload)
                        print(">> Data extraction simulated successfully. Notified server.")
                    else:
                        print(f">> Unknown action '{action}', ignoring.")

                except json.JSONDecodeError:
                    print("Error: Received malformed JSON from the server.")

    except ConnectionRefusedError:
        print("Could not connect. Is the FastAPI server running? (uvicorn server:app --reload)")


if __name__ == "__main__":
    asyncio.run(run_mock_agent())