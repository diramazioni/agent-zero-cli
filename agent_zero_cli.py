#!/usr/bin/env python3
"""
Agent Zero MCP CLI Client - Corrected Version

This version uses the correct MCP protocol format (not JSON-RPC) and
follows the FastMCP server expectations based on the server source code.
"""

import argparse
import json
import requests
import sys
import os
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class AgentZeroMCPClient:
    def __init__(self, base_url: str = None, token: str = None):
        self.base_url = (base_url or os.getenv('AGENT_ZERO_MCP_URL', 'http://localhost:5000')).rstrip('/')
        self.token = token or os.getenv('AGENT_ZERO_MCP_TOKEN', '0')
        self.messages_url = f"{self.base_url}/mcp/t-{self.token}/messages/"
        self.sse_url = f"{self.base_url}/mcp/t-{self.token}/sse"

    def send_message(self, message: str):
        """Send message using correct MCP protocol format"""
        try:
            print(f"🔗 Connecting to Agent Zero at: {self.base_url}")
            print(f"🎯 Token: {self.token}")
            
            # Correct MCP payload format (not JSON-RPC)
            payload = {
                "method": "tools/call",
                "params": {
                    "name": "send_message",
                    "arguments": {
                        "message": message,
                        "attachments": [],
                        "chat_id": None,
                        "persistent_chat": False
                    }
                }
            }
            
            print(f"📤 Sending message...")
            print(f"🔍 DEBUG: Messages URL: {self.messages_url}")
            print(f"🔍 DEBUG: Payload: {json.dumps(payload, indent=2)}")
            print(f"🔍 DEBUG: Content-Length: {len(json.dumps(payload))}")
            
            # Send POST request to messages endpoint
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            
            with requests.Session() as session:
                response = session.post(
                    self.messages_url,
                    data=json.dumps(payload),
                    headers=headers,
                    timeout=30
                )
                
                print(f"🔍 DEBUG: Response status: {response.status_code}")
                print(f"🔍 DEBUG: Response headers: {dict(response.headers)}")
                
                if response.status_code == 202:
                    print("✅ Message sent successfully, listening for response...")
                    self._listen_for_response(session)
                else:
                    response.raise_for_status()
                    
        except requests.exceptions.RequestException as e:
            print(f"❌ Error: Request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"🔍 DEBUG: Response status: {e.response.status_code}")
                print(f"🔍 DEBUG: Response text: {e.response.text}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")
            sys.exit(1)

    def _listen_for_response(self, session: requests.Session):
        """Listen for SSE response from Agent Zero"""
        try:
            print(f"👂 Listening for response on: {self.sse_url}")
            
            headers = {
                'Accept': 'text/event-stream',
                'Cache-Control': 'no-cache'
            }
            
            with session.get(self.sse_url, headers=headers, stream=True, timeout=300) as response:
                response.raise_for_status()
                
                print("🔍 DEBUG: SSE connection established")
                buffer = ""
                last_activity = time.time()
                
                for chunk in response.iter_content(chunk_size=1, decode_unicode=True):
                    if chunk:
                        last_activity = time.time()
                        buffer += chunk
                        
                        # Process complete lines
                        while '\n' in buffer:
                            line, buffer = buffer.split('\n', 1)
                            line = line.strip()
                            
                            if line:
                                print(f"🔍 DEBUG: SSE Line: '{line}'")
                                
                                if line.startswith('data: '):
                                    data = line[6:].strip()
                                    if data and data != '[DONE]':
                                        try:
                                            event_data = json.loads(data)
                                            print("📨 Response received:")
                                            print(json.dumps(event_data, indent=2))
                                            
                                            # Check if this is the final response
                                            if self._is_final_response(event_data):
                                                print("🏁 Final response received")
                                                return
                                                
                                        except json.JSONDecodeError:
                                            print(f"📝 Raw response: {data}")
                                            
                                elif line.startswith('event: '):
                                    event_type = line[7:].strip()
                                    print(f"🎯 Event: {event_type}")
                                    
                                    if event_type in ['end', 'done', 'complete']:
                                        print("🏁 Stream ended")
                                        return
                    
                    # Timeout check for inactive streams
                    if time.time() - last_activity > 60:
                        print("⏰ No activity for 60 seconds, checking if response is complete...")
                        break
                        
                print("🔍 DEBUG: Stream ended, checking for any remaining data...")
                
        except requests.exceptions.Timeout:
            print("⏰ Timeout waiting for response")
        except requests.exceptions.RequestException as e:
            print(f"❌ Error listening for response: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error in response listener: {str(e)}")

    def _is_final_response(self, event_data: dict) -> bool:
        """Check if this is a final response from Agent Zero"""
        if isinstance(event_data, dict):
            # Check for common final response indicators
            if 'status' in event_data and event_data['status'] in ['success', 'error', 'complete']:
                return True
            if 'response' in event_data and 'chat_id' in event_data:
                return True
            if 'error' in event_data:
                return True
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Agent Zero MCP CLI Client - Corrected Version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Example:
  ./agent_zero_cli.py "What is your name?"
  ./agent_zero_cli.py "List files in current directory"
"""
    )
    parser.add_argument("message", nargs="?", help="Message to send to Agent Zero")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()

    if not args.message:
        parser.print_help()
        sys.exit(1)

    client = AgentZeroMCPClient()
    client.send_message(args.message)

if __name__ == "__main__":
    main()
