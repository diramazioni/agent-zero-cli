#!/usr/bin/env python3
"""
Agent Zero MCP CLI Client (SSE Version)

A command-line interface to communicate with Agent Zero through its streaming MCP SSE endpoint.
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
        self.session = requests.Session()
        self.sse_url = f"{self.base_url}/mcp/t-{self.token}/sse"

    def stream_tool_call(self, payload: dict):
        """Connects to the MCP endpoint using a 3-step handshake with a session object."""
        session_url = None

        try:
            # Step 1: Initial GET to get session URL. We use a session to manage state.
            print(f"🔗 Step 1: Initializing session with: {self.sse_url}", file=sys.stderr)
            init_response = self.session.get(self.sse_url, stream=True, timeout=15)
            init_response.raise_for_status()

            for line in init_response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith('data:'):
                        endpoint_path = decoded_line[len('data:'):].strip()
                        session_url = f"{self.base_url.rstrip('/')}{endpoint_path}"
                        print(f"✅ Session endpoint received: {session_url}", file=sys.stderr)
                        break # Exit the loop once we have the URL
            
            # IMPORTANT: Close the initial response to free the connection for the POST
            init_response.close()

            if not session_url:
                print("❌ Error: Did not receive a session endpoint from the server.", file=sys.stderr)
                sys.exit(1)

            # Step 2: Send the message payload via POST using the same session
            print(f"📤 Step 2: Sending payload to: {session_url}", file=sys.stderr)
            payload['jsonrpc'] = '2.0'
            payload['id'] = 1
            post_headers = {'Content-Type': 'application/json'}
            post_response = self.session.post(session_url, data=json.dumps(payload), headers=post_headers, timeout=30)
            post_response.raise_for_status()

            # Step 3: Listen for the response via streaming GET using the same session
            print(f"👂 Step 3: Listening for response from: {session_url}", file=sys.stderr)
            get_headers = {'Accept': 'text/event-stream'}
            with self.session.get(session_url, headers=get_headers, stream=True, timeout=180) as stream_response:
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
            "method": "tools/call",
            "params": {"name": "finish_chat", "arguments": {"chat_id": args.finish_chat}}
        }
    elif args.message:
        arguments = {"message": args.message}
        if args.attachments: arguments["attachments"] = args.attachments
        if args.chat_id: arguments["chat_id"] = args.chat_id
        if args.persistent: arguments["persistent_chat"] = args.persistent
        payload = {
            "method": "tools/call",
            "params": {"name": "send_message", "arguments": arguments}
        }
    else:
        parser.print_help()
        sys.exit(1)

    if payload:
        client = AgentZeroMCPClient(base_url=args.url, token=args.token)
        client.stream_tool_call(payload)

if __name__ == "__main__":
    main()
