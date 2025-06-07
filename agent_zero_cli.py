#!/usr/bin/env python3
"""
Agent Zero MCP CLI Client - FastMCP Compatible

This version follows the FastMCP protocol correctly by using Server-Sent Events (SSE)
for establishing the connection and properly formatted JSON-RPC for making requests.
"""

import argparse
import json
import requests
import sys
import os
import time
import uuid

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class AgentZeroMCPClient:
    def __init__(self, base_url: str = None, token: str = None):
        self.base_url = (base_url or os.getenv('AGENT_ZERO_MCP_URL', 'http://localhost:5000')).rstrip('/')
        self.token = token or os.getenv('AGENT_ZERO_MCP_TOKEN', '0')
        # FastMCP paths follow a specific pattern
        self.base_path = f"/mcp/t-{self.token}"
        self.messages_url = f"{self.base_url}{self.base_path}/messages/"
        self.sse_url = f"{self.base_url}{self.base_path}/sse"
        
    def send_message(self, message: str):
        """Send message using the correct FastMCP protocol format"""
        try:
            print(f"🔗 Connecting to Agent Zero at: {self.base_url}")
            print(f"🎯 Token: {self.token}")
            
            # Generate a unique request ID
            request_id = str(uuid.uuid4())
            
            # Create a session for connection reuse
            with requests.Session() as session:
                # First establish SSE connection to get session_id
                print(f"🔗 Establishing SSE connection: {self.sse_url}")
                
                # Headers for SSE request
                sse_headers = {
                    'Accept': 'text/event-stream',
                    'Cache-Control': 'no-cache',
                    'X-Request-ID': request_id
                }
                
                # Start SSE connection to get session_id
                sse_response = session.get(
                    self.sse_url,
                    stream=True,
                    headers=sse_headers,
                    timeout=30
                )
                sse_response.raise_for_status()
                print(f"✅ SSE connection established")
                
                # Extract session_id from SSE response
                session_id = self._extract_session_id(sse_response)
                if not session_id:
                    raise ConnectionError("Could not obtain session_id from SSE connection")
                
                print(f"✅ Session ID obtained: {session_id}")
                
                # Now send the message request with session_id
                messages_url_with_session = f"{self.messages_url}?session_id={session_id}"
                print(f"📤 Sending message request to: {messages_url_with_session}")
                
                # FastMCP expects specific JSON-RPC 2.0 format
                payload = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/call",
                    "params": {
                        "name": "send_message",
                        "arguments": {
                            "message": message,
                            "attachments": None,
                            "chat_id": None,
                            "persistent_chat": None
                        }
                    }
                }
                
                headers = {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-Request-ID': request_id
                }
                
                # Send the message request
                response = session.post(
                    messages_url_with_session,
                    json=payload,
                    headers=headers,
                    timeout=30
                )
                
                print(f"🔍 Response status: {response.status_code}")
                
                # Process the response
                if response.status_code in (200, 202):
                    print("✅ Message request accepted")
                    
                    if response.status_code == 200:
                        # Direct response
                        try:
                            result = response.json()
                            print("📨 Agent Zero Response:")
                            print(json.dumps(result, indent=2))
                            return
                        except json.JSONDecodeError:
                            print(f"📝 Raw response: {response.text}")
                    else:
                        # Async response - we need to wait for events on the SSE connection
                        self._process_sse_events_with_session(session, session_id)
                else:
                    print(f"❌ Request failed with status: {response.status_code}")
                    print(f"Response: {response.text}")
                    response.raise_for_status()
                    
        except requests.exceptions.RequestException as e:
            print(f"❌ Request error: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Status: {e.response.status_code}")
                print(f"Response: {e.response.text}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")
            sys.exit(1)

    def _extract_session_id(self, sse_response):
        """Extract session_id from the initial SSE connection"""
        try:
            # Read the first few lines to get the session_id
            for chunk in sse_response.iter_content(chunk_size=1024):
                if chunk:
                    chunk_text = chunk.decode('utf-8', errors='replace')
                    lines = chunk_text.split('\n')
                    
                    for line in lines:
                        line = line.strip()
                        if line.startswith('data:'):
                            data = line[5:].strip()
                            # Look for endpoint path with session_id
                            if data.startswith('/mcp/t-') and '?session_id=' in data:
                                session_id = data.split('?session_id=')[1]
                                return session_id
                            # Or look for direct session_id
                            elif data and not data.startswith('{'):
                                return data
                    
                    # Stop after first chunk to avoid blocking
                    break
            
            return None
            
        except Exception as e:
            print(f"❌ Error extracting session_id: {e}")
            return None

    def _process_sse_events_with_session(self, session, session_id):
        """Process events from a new SSE connection with session_id"""
        try:
            sse_url_with_session = f"{self.sse_url}?session_id={session_id}"
            print(f"👂 Listening for response on: {sse_url_with_session}")
            
            headers = {
                'Accept': 'text/event-stream',
                'Cache-Control': 'no-cache'
            }
            
            with session.get(sse_url_with_session, headers=headers, stream=True, timeout=300) as response:
                response.raise_for_status()
                self._process_sse_events(response)
                
        except Exception as e:
            print(f"❌ Error in SSE with session: {e}")

    def _process_sse_events(self, sse_response):
        """Process events from the SSE connection to get the Agent Zero response"""
        try:
            print("👂 Waiting for Agent Zero response via SSE...")
            
            buffer = ""
            last_activity = time.time()
            
            for chunk in sse_response.iter_content(chunk_size=1024):
                if chunk:
                    last_activity = time.time()
                    chunk_text = chunk.decode('utf-8', errors='replace')
                    buffer += chunk_text
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if not line:
                            continue
                            
                        if line.startswith('event:'):
                            event_type = line[6:].strip()
                            print(f"🎯 Event: {event_type}")
                            
                            if event_type in ['end', 'done', 'complete']:
                                print("🏁 Stream complete")
                                return
                                
                        elif line.startswith('data:'):
                            data = line[5:].strip()
                            
                            # Check if this is a complete message
                            if data == '[DONE]':
                                print("🏁 Stream complete")
                                return
                            
                            # Check if this is a new endpoint - just log it but continue listening
                            if data.startswith('/mcp/t-') and 'session_id=' in data:
                                print(f"🔄 New endpoint received: {data}")
                                # Don't switch sessions, just continue listening on current SSE
                                continue
                                
                            try:
                                # Try to parse JSON directly if it's a complete message
                                parsed_data = json.loads(data)
                                if isinstance(parsed_data, dict):
                                    if 'result' in parsed_data:
                                        result = parsed_data['result']
                                        print("📨 Agent Zero Response:")
                                        print(json.dumps(result, indent=2))
                                        return
                                    elif 'response' in parsed_data:
                                        print("📨 Agent Zero Response:")
                                        print(json.dumps(parsed_data, indent=2))
                                        return
                            except json.JSONDecodeError:
                                # Not JSON, might be plain text response
                                if data and data != '[DONE]':
                                    print(f"📝 Message: {data}")
                
                # Check for timeout
                if time.time() - last_activity > 120:
                    print("⏰ No activity for 2 minutes, closing connection")
                    break
            
            print("⏰ SSE stream ended without complete response")
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error in SSE stream: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error: {str(e)}")

    def _listen_on_new_session(self, session_id):
        """Open a new SSE connection with the new session_id"""
        try:
            sse_url_with_session = f"{self.sse_url}?session_id={session_id}"
            print(f"👂 Opening new SSE connection: {sse_url_with_session}")
            
            headers = {
                'Accept': 'text/event-stream',
                'Cache-Control': 'no-cache'
            }
            
            with requests.get(sse_url_with_session, headers=headers, stream=True, timeout=300) as response:
                response.raise_for_status()
                print("✅ New SSE connection established")
                self._process_sse_events(response)
                
        except Exception as e:
            print(f"❌ Error in new SSE connection: {e}")

    def _trigger_processing(self, endpoint_url):
        """Send a simple request to trigger processing, but don't poll for response"""
        try:
            print(f"🔄 Triggering processing at: {endpoint_url}")
            
            # Generate a unique request ID
            trigger_request_id = str(uuid.uuid4())
            
            # Create a simple trigger payload
            trigger_payload = {
                "jsonrpc": "2.0",
                "id": trigger_request_id,
                "method": "notifications/initialized",
                "params": {}
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Request-ID': trigger_request_id
            }
            
            # Send one request to trigger processing
            response = requests.post(
                endpoint_url,
                json=trigger_payload,
                headers=headers,
                timeout=10
            )
            
            print(f"🔍 Trigger Response status: {response.status_code}")
            
            if response.status_code == 202:
                print("✅ Processing triggered, waiting for SSE response...")
            elif response.status_code == 200:
                try:
                    result = response.json()
                    print("📨 Agent Zero Response (immediate):")
                    print(json.dumps(result, indent=2))
                    return True
                except json.JSONDecodeError:
                    response_text = response.text.strip()
                    if response_text:
                        print(f"📝 Agent Zero Response (immediate): {response_text}")
                        return True
            else:
                print(f"🔍 Trigger Response text: {response.text}")
            
            return False
            
        except Exception as e:
            print(f"❌ Error triggering processing: {e}")
            return False

    def finish_chat(self, chat_id: str):
        """Finish a persistent chat with Agent Zero"""
        if not chat_id:
            print("❌ Error: chat_id is required for finish_chat")
            return
            
        try:
            print(f"🔗 Finishing chat with ID: {chat_id}")
            
            # Generate a unique request ID
            request_id = str(uuid.uuid4())
            
            # Prepare the payload
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": "finish_chat",
                    "arguments": {
                        "chat_id": chat_id
                    }
                }
            }
            
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-Request-ID': request_id
            }
            
            # Send the finish_chat request
            response = requests.post(
                self.messages_url,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            print(f"🔍 Response status: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    print("📨 Result:")
                    print(json.dumps(result, indent=2))
                except json.JSONDecodeError:
                    print(f"📝 Raw response: {response.text}")
            else:
                print(f"❌ Request failed with status: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Error finishing chat: {str(e)}")

    def _is_complete_response(self, data):
        """Check if this is a complete response"""
        if isinstance(data, dict):
            # Check for common response patterns
            if 'result' in data:
                return True
            if 'status' in data and data['status'] in ['success', 'error', 'complete']:
                return True
            if 'response' in data and 'chat_id' in data:
                return True
            if 'error' in data:
                return True
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Agent Zero MCP CLI Client - FastMCP compatible",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  ./agent_zero_cli.py "What is your name?"
  ./agent_zero_cli.py "List files in current directory"
  ./agent_zero_cli.py --finish-chat CHAT_ID
"""
    )
    parser.add_argument("message", nargs="?", help="Message to send to Agent Zero")
    parser.add_argument("--finish-chat", help="Finish a persistent chat with the given chat_id")
    parser.add_argument("--url", help="Base URL for Agent Zero MCP server")
    parser.add_argument("--token", help="Token for Agent Zero MCP server")
    args = parser.parse_args()

    if not args.message and not args.finish_chat:
        parser.print_help()
        sys.exit(1)

    client = AgentZeroMCPClient(base_url=args.url, token=args.token)
    
    if args.finish_chat:
        client.finish_chat(args.finish_chat)
    else:
        client.send_message(args.message)

if __name__ == "__main__":
    main()
