"""
One-off inspection script — NOT part of the running agent.

Dumps WhatsApp Desktop's UI control tree (every window, button, edit box,
list, etc. and their names/automation IDs) to a text file, so we can see
exactly what to target for search-contact / type-message / send-message
automation.

Usage:
    1. pip install pywinauto
    2. Open WhatsApp Desktop manually and make sure you're logged in
    3. Run:  python inspect_whatsapp.py
    4. Send back whatsapp_tree.txt (or just the parts mentioning "search",
       "message", "chat list", "send" if the file is huge)
"""

from pywinauto import Application

OUTPUT_FILE = "whatsapp_tree.txt"


def main():
    print("Connecting to the WhatsApp window (make sure it's already open)...")

    try:
        app = Application(backend="uia").connect(title_re=".*WhatsApp.*", timeout=10)
    except Exception as e:
        print(f"Could not connect: {e}")
        print("Make sure WhatsApp Desktop is open and visible, then try again.")
        return

    window = app.top_window()
    window.set_focus()

    print(f"Connected. Dumping control tree to {OUTPUT_FILE} ...")

    # print_control_identifiers can print a LOT — redirect it to a file
    # instead of the console so it's easy to send back.
    import io
    import contextlib

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        window.print_control_identifiers(depth=None)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(buffer.getvalue())

    print(f"Done. Open {OUTPUT_FILE} and look for controls related to:")
    print("  - the search box at the top of the chat list")
    print("  - individual chat/contact list items")
    print("  - the message text box at the bottom")
    print("  - the send button")


if __name__ == "__main__":
    main()