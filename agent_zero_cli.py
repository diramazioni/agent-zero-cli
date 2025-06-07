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
from typing import Optional

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

    def get_session_endpoint(self) -> Optional[str]:
        """Performs an initial GET to the SSE endpoint to get the session-specific URL."""
        print(f"🔗 Initializing session with: {self.sse_url}", file=sys.stderr)
        try:
            headers = {'Accept': 'text/event-stream'}
            with self.session.get(self.sse_url, headers=headers, stream=True, timeout=15) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data:'):
                            endpoint_path = decoded_line[len('data:'):].strip()
                            session_url = f"{self.base_url.rstrip('/')}{endpoint_path}"
                            print(f"✅ Session endpoint received: {session_url}", file=sys.stderr)
                            return session_url
            print("❌ Error: Did not receive a session endpoint from the server.", file=sys.stderr)
            return None
        except requests.exceptions.RequestException as e:
            print(f"❌ Error: Failed to initialize session: {str(e)}", file=sys.stderr)
            return None

    def stream_tool_call(self, payload: dict):
        """Connects to the MCP endpoint using the 3-step handshake and streams the response."""
        session_url = self.get_session_endpoint()
        if not session_url:
            sys.exit(1)

        try:
            # Add JSON-RPC required fields
            payload['jsonrpc'] = '2.0'
            payload['id'] = 1

            # Step 2: Send the message payload via a direct POST, passing session cookies manually
            print(f"📤 Sending payload to: {session_url}", file=sys.stderr)
            post_headers = {'Content-Type': 'application/json'}
            post_data = json.dumps(payload)
            post_response = requests.post(session_url, data=post_data, headers=post_headers, cookies=self.session.cookies, timeout=30)
            
            # Update the session with any cookies from the POST response
            self.session.cookies.update(post_response.cookies)

            post_response.raise_for_status()
            if post_response.status_code != 202:
                print(f"⚠️ Warning: Expected status 202 but got {post_response.status_code}", file=sys.stderr)

            # Step 3: Listen for the response via streaming GET using the original session
            print(f"👂 Listening for response from: {session_url}", file=sys.stderr)
            get_headers = {'Accept': 'text/event-stream'}
            with self.session.get(session_url, headers=get_headers, stream=True, timeout=180) as response:
                response.raise_for_status()
                for line in response.iter_lines():
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
            print(f"❌ Error: Request failed during communication: {str(e)}", file=sys.stderr)
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

    client = AgentZeroMCPClient(base_url=args.url, token=args.token)
    payload = None

    if args.finish_chat:
        print(f"🔚 Finishing chat: {args.finish_chat}", file=sys.stderr)
        payload = {
            "method": "tools/call",
            "params": {"name": "finish_chat", "arguments": {"chat_id": args.finish_chat}}
        }
    elif args.message:
        print(f"📤 Sending initial message...", file=sys.stderr)
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
        client.stream_tool_call(payload)

if __name__ == "__main__":
    main()
