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
        self.base_url = (base_url or os.getenv('AGENT_ZERO_MCP_URL', 'http://localhost:50000')).rstrip('/')
        self.token = token or os.getenv('AGENT_ZERO_MCP_TOKEN', '0')
        self.session = requests.Session()
        self.sse_url = f"{self.base_url}/mcp/t-{self.token}/sse"

    def stream_tool_call(self, payload: dict):
        """Connects to the SSE endpoint, sends a tool call, and streams the response."""
        print(f"🔗 Connecting to SSE stream: {self.sse_url}", file=sys.stderr)
        headers = {'Accept': 'text/event-stream'}
        
        try:
            with self.session.get(self.sse_url, headers=headers, stream=True, timeout=180) as response:
                response.raise_for_status()
                
                messages_url = None
                
                # First, listen for the 'endpoint' event to know where to POST
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('event: endpoint'):
                            # The next line should be the data line
                            continue
                        if decoded_line.startswith('data:'):
                            messages_endpoint = decoded_line[len('data:'):].strip()
                            # Construct the full URL for the POST request
                            messages_url = urllib.parse.urljoin(self.base_url, messages_endpoint)
                            break # Got the URL, exit this loop

                if not messages_url:
                    print("❌ Error: Did not receive the messages endpoint from the server.", file=sys.stderr)
                    sys.exit(1)

                # Construct a JSON-RPC 2.0 compliant payload
                jsonrpc_payload = payload.copy()
                jsonrpc_payload['jsonrpc'] = '2.0'
                jsonrpc_payload['id'] = 1 # A simple ID for the request

                # Now, make the POST request to the obtained URL with the JSON-RPC payload
                print(f"📮 Sending command to: {messages_url}", file=sys.stderr)
                post_headers = {'Content-Type': 'application/json'}
                post_response = requests.post(messages_url, json=jsonrpc_payload, headers=post_headers)
                post_response.raise_for_status()

                # Continue listening on the original stream for the agent's response
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith('data:'):
                            json_data = decoded_line[len('data:'):].strip()
                            try:
                                event = json.loads(json_data)
                                print(json.dumps(event, indent=2))
                            except json.JSONDecodeError:
                                print(json_data) # Print as-is if not JSON
                        elif 'event: end' in decoded_line:
                            print("\n🏁 Stream finished.", file=sys.stderr)
                            break
            
            sys.exit(0) # Success

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
