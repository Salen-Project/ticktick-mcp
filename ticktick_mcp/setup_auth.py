#!/usr/bin/env python3
"""
TickTick OAuth Setup Script

Run this ONCE before using the MCP server to authenticate your TickTick account.
It will open your browser, ask you to log in, then save your tokens automatically.

Usage:
    python setup_auth.py
"""

import json
import time
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
from pathlib import Path

import httpx

# --- Configuration ---
# Get these from https://developer.ticktick.com after registering your app
CLIENT_ID = "YOUR_CLIENT_ID"
CLIENT_SECRET = "YOUR_CLIENT_SECRET"
REDIRECT_URI = "http://localhost:8080/callback"
AUTH_URL = "https://ticktick.com/oauth/authorize"
TOKEN_URL = "https://ticktick.com/oauth/token"
TOKENS_FILE = Path.home() / ".ticktick_mcp" / "tokens.json"

# Shared state for the callback handler
auth_code: str | None = None


class CallbackHandler(BaseHTTPRequestHandler):
    """Handles the OAuth redirect from TickTick."""

    def do_GET(self):
        global auth_code
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
                <html>
                <body style="font-family: sans-serif; text-align: center; padding: 60px; background: #f9f9f9;">
                    <h2 style="color: #4caf50;">&#10003; Authentication Successful!</h2>
                    <p style="color: #555;">You can close this tab and return to Claude.</p>
                </body>
                </html>
            """)
        else:
            error = params.get("error", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h2>Authorization failed: {error}</h2></body></html>".encode()
            )

    def log_message(self, format, *args):
        pass  # Suppress server logs


def main():
    global auth_code

    print()
    print("🔐  TickTick Authentication Setup")
    print("=" * 42)

    # Build authorization URL
    auth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "tasks:read tasks:write",
    }
    url = f"{AUTH_URL}?{urlencode(auth_params)}"

    # Start a local server to capture the OAuth callback
    server = HTTPServer(("127.0.0.1", 8080), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.daemon = True
    thread.start()

    print("\n📋  Opening your browser for TickTick authorization...")
    print(f"\n    If the browser doesn't open automatically, visit:\n    {url}\n")
    webbrowser.open(url)

    print("⏳  Waiting for you to authorize in the browser...")
    thread.join(timeout=120)

    if not auth_code:
        print("\n❌  Authorization timed out after 2 minutes. Please run this script again.")
        return

    print("✅  Authorization received! Exchanging for access tokens...")

    # Exchange the authorization code for access + refresh tokens
    # TickTick requires HTTP Basic Auth with credentials + form body
    try:
        response = httpx.post(
            TOKEN_URL,
            auth=(CLIENT_ID, CLIENT_SECRET),
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": REDIRECT_URI,
            },
            timeout=30.0,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        print(f"\n❌  Token exchange failed (HTTP {e.response.status_code}): {e.response.text}")
        return
    except Exception as e:
        print(f"\n❌  Unexpected error: {e}")
        return

    tokens = response.json()
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)

    # Save tokens to disk
    TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=2)

    print(f"💾  Tokens saved to: {TOKENS_FILE}")
    print("\n🎉  Setup complete! The TickTick MCP server is ready to use.")
    print("    You don't need to run this script again unless you revoke access.\n")


if __name__ == "__main__":
    main()
