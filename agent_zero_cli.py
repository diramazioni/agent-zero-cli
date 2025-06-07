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
import urllib.parse
from typing import Optional, List

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
        """Connects to the SSE endpoint and streams the response for a given tool call payload."""
        try:
            # URL-encode the JSON payload to pass as a query parameter
            encoded_payload = urllib.parse.quote(json.dumps(payload))
            request_url = f"{self.sse_url}?query={encoded_payload}"

            print(f"🔗 Connecting to SSE stream: {self.sse_url}", file=sys.stderr)
            
            headers = {'Accept': 'text/event-stream'}
            with self.session.get(request_url, headers=headers, stream=True, timeout=180) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data:'):
                            json_data = decoded_line[len('data:'):].strip()
                            try:
                                # Attempt to parse the data as JSON and print it
                                event = json.loads(json_data)
                                # Pretty print the JSON output
                                print(json.dumps(event, indent=2))
                            except json.JSONDecodeError:
                                # If it's not JSON, print as plain text
                                print(json_data)
                        elif 'event: end' in decoded_line:
                            print("\n🏁 Stream finished.", file=sys.stderr)
                            break

        except requests.exceptions.RequestException as e:
            print(f"❌ Error: Request failed: {str(e)}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Agent Zero MCP CLI Client (SSE Version)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  ./agent_zero_cli.py "What is your name?"
  ./agent_zero_cli.py --finish-chat <chat_id_to_close>\n"""
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
        print(f"📤 Sending message...", file=sys.stderr)
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
