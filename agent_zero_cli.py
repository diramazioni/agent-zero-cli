#!/usr/bin/env python3
"""
Agent Zero MCP CLI Client (SSE Version) - Hybrid Approach

Uses `requests` for GET and `curl` via `subprocess` for the problematic POST request.
This version uses a revised, more standard JSON-RPC payload structure.
"""

import argparse
import json
import requests
import sys
import os
import subprocess

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

    def stream_tool_call(self, payload: dict):
        session_url = None

        try:
            # Step 1: Initial GET to get session URL (using requests)
            print(f"🔗 Step 1: Initializing session with: {self.sse_url}", file=sys.stderr)
            init_response = requests.get(self.sse_url, stream=True, timeout=15)
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
                print("❌ Error: Did not receive a session endpoint.", file=sys.stderr)
                sys.exit(1)

            # Step 2: Send payload via POST using curl (subprocess)
            print(f"📤 Step 2: Sending payload via curl to: {session_url}", file=sys.stderr)
            json_payload = json.dumps(payload)
            
            curl_command = [
                'curl',
                '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '--data', json_payload,
                session_url
            ]
            
            result = subprocess.run(curl_command, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                print(f"❌ Error: curl command failed with exit code {result.returncode}", file=sys.stderr)
                print(f"curl stderr: {result.stderr}", file=sys.stderr)
                sys.exit(1)

            # Step 3: Listen for response via streaming GET (using requests)
            print(f"👂 Step 3: Listening for response from: {session_url}", file=sys.stderr)
            get_headers = {'Accept': 'text/event-stream'}
            with requests.get(session_url, headers=get_headers, stream=True, timeout=180) as stream_response:
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
            print(f"❌ Error: A requests operation failed: {str(e)}", file=sys.stderr)
            if e.response is not None:
                print(f"Response body: {e.response.text}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"❌ An unexpected error occurred: {str(e)}", file=sys.stderr)
            sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Agent Zero MCP CLI Client (SSE Version)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:\n  ./agent_zero_cli.py "What is your name?"\n  ./agent_zero_cli.py --finish-chat <chat_id_to_close>\n"""
    )
    parser.add_argument("message", nargs="?", help="Message to send to Agent Zero")
    parser.add_argument("--url", help="Base URL for Agent Zero MCP server")
    parser.add_argument("--token", help="Authentication token")
    parser.add_argument("--attachments", nargs="*", help="File paths or URLs to attach")
    parser.add_argument("--chat-id", help="Chat ID to continue a conversation")
    parser.add_argument("--persistent", action="store_true", help="Keep the chat session persistent")
    parser.add_argument("--finish-chat", help="Chat ID to finish/close")
    args = parser.parse_args()

    payload = None

    if args.finish_chat:
        payload = {
            "method": "finish_chat",
            "params": {"chat_id": args.finish_chat},
            "jsonrpc": "2.0",
            "id": 1
        }
    elif args.message:
        params = {"message": args.message}
        if args.attachments: params["attachments"] = args.attachments
        if args.chat_id: params["chat_id"] = args.chat_id
        if args.persistent: params["persistent_chat"] = args.persistent
        payload = {
            "method": "send_message",
            "params": params,
            "jsonrpc": "2.0",
            "id": 1
        }
    else:
        parser.print_help()
        sys.exit(1)

    if payload:
        client = AgentZeroMCPClient(base_url=args.url, token=args.token)
        client.stream_tool_call(payload)

if __name__ == "__main__":
    main()
