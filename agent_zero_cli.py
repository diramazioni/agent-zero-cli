#!/usr/bin/env python3
"""
Agent Zero MCP CLI Client (SSE Version) - Definitive Version

This version implements the correct three-step, session-based handshake and
sends a fully compliant JSON-RPC payload that matches the server's tool
definition for `send_message`, as discovered by inspecting the source code.
"""

import argparse
import json
import requests
import sys
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class AgentZeroMCPClient:
    def __init__(self, base_url: str = None, token: str = None):
        self.base_url = (base_url or os.getenv('AGENT_ZERO_MCP_URL', 'http://localhost:5000')).rstrip('/')
        self.token = token or os.getenv('AGENT_ZERO_MCP_TOKEN', '0')
        self.sse_url = f"{self.base_url}/mcp/t-{self.token}/sse"

    def stream_tool_call(self, message: str):
        session_url = None
        try:
            with requests.Session() as session:
                # Step 1: Initial GET to get session URL.
                print(f"🔗 Step 1: Initializing session with: {self.sse_url}", file=sys.stderr)
                init_response = session.get(self.sse_url, stream=True, timeout=15)
                init_response.raise_for_status()

                for line in init_response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data:'):
                            endpoint_path = decoded_line[len('data:'):].strip()
                            session_url = f"{self.base_url.rstrip('/')}{endpoint_path}"
                            print(f"✅ Session endpoint received: {session_url}", file=sys.stderr)
                            break
                
                init_response.close()

                if not session_url:
                    raise ConnectionError("Did not receive a session endpoint from the server.")

                # Step 2: Send the fully compliant payload via POST.
                print(f"📤 Step 2: Sending payload to: {session_url}", file=sys.stderr)
                
                # This payload structure matches the server's `send_message` tool definition exactly.
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "send_message",
                    "params": {
                        "message": message,
                        "attachments": [],
                        "chat_id": None,
                        "persistent_chat": False
                    }
                }

                post_headers = {'Content-Type': 'application/json'}
                post_response = session.post(session_url, data=json.dumps(payload), headers=post_headers, timeout=30)
                post_response.raise_for_status()

                # Step 3: Listen for the response.
                print(f"👂 Step 3: Listening for response from: {session_url}", file=sys.stderr)
                get_headers = {'Accept': 'text/event-stream'}
                with session.get(session_url, headers=get_headers, stream=True, timeout=180) as stream_response:
                    stream_response.raise_for_status()
                    for line in stream_response.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith('data:'):
                                json_data = decoded_line[len('data:'):].strip()
                                try:
                                    event = json.loads(json_data)
                                    print(json.dumps(event, indent=2))
                                except json.JSONDecodeError:
                                    print(json_data)
                            elif 'event: end' in decoded_line:
                                print("\n🏁 Stream finished.", file=sys.stderr)
                                break

        except requests.exceptions.RequestException as e:
            print(f"❌ Error: Request failed: {str(e)}", file=sys.stderr)
            if e.response is not None:
                print(f"Response body: {e.response.text}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"❌ An unexpected error occurred: {str(e)}", file=sys.stderr)
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Agent Zero MCP CLI Client (SSE Version) - Definitive Version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example:\n  ./agent_zer🔗 Step 1: Initializing session with: http://localhost:5000/mcp/t-0/sse
✅ Session endpoint received: http://localhost:5000/mcp/t-0/messages/?session_id=fd1b3d132bfd490d8929c08065227cca
📤 Step 2: Sending payload to: http://localhost:5000/mcp/t-0/messages/?session_id=fd1b3d132bfd490d8929c08065227cca
👂 Step 3: Listening for response from: http://localhost:5000/mcp/t-0/messages/?session_id=fd1b3d132bfd490d8929c08065227cca
❌ Error: Request failed: 400 Client Error: Bad Request for url: http://localhost:5000/mcp/t-0/messages/?session_id=fd1b3d132bfd490d8929c08065227cca
Response body:o_cli.py "What is your name?"\n"""
    )
    parser.add_argument("message", nargs="?", help="Message to send to Agent Zero")
    args = parser.parse_args()

    if not args.message:
        parser.print_help()
        sys.exit(1)

    client = AgentZeroMCPClient()
    client.stream_tool_call(args.message)

if __name__ == "__main__":
    main()
