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
        """Send message using correct MCP protocol format with session_id"""
        try:
            print(f"🔗 Connecting to Agent Zero at: {self.base_url}")
            print(f"🎯 Token: {self.token}")
            
            with requests.Session() as session:
                # Step 1: Get session_id from SSE endpoint
                print(f"🔗 Step 1: Getting session_id from: {self.sse_url}")
                
                sse_response = session.get(self.sse_url, stream=True, timeout=15)
                sse_response.raise_for_status()
                
                session_id = None
                for line in sse_response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        print(f"🔍 DEBUG: SSE Line: '{decoded_line}'")
                        
                        if decoded_line.startswith('data: '):
                            endpoint_path = decoded_line[6:].strip()
                            # Extract session_id from endpoint path
                            if '?session_id=' in endpoint_path:
                                session_id = endpoint_path.split('?session_id=')[1]
                                print(f"✅ Session ID obtained: {session_id}")
                                break
                
                sse_response.close()
                
                if not session_id:
                    raise ConnectionError("Could not obtain session_id from server")
                
                # Step 2: Send message with session_id
                messages_url_with_session = f"{self.messages_url}?session_id={session_id}"
                print(f"📤 Step 2: Sending message to: {messages_url_with_session}")
                
                # FastMCP expects complete JSON-RPC 2.0 format
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
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
                
                print(f"🔍 DEBUG: Payload: {json.dumps(payload, indent=2)}")
                print(f"🔍 DEBUG: Content-Length: {len(json.dumps(payload))}")
                
                headers = {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
                
                response = session.post(
                    messages_url_with_session,
                    data=json.dumps(payload),
                    headers=headers,
                    timeout=30
                )
                
                print(f"🔍 DEBUG: Response status: {response.status_code}")
                print(f"🔍 DEBUG: Response headers: {dict(response.headers)}")
                
                if response.status_code == 202:
                    print("✅ Message sent successfully, waiting for Agent Zero to process...")
                    print("🔍 DEBUG: Waiting 5 seconds for Agent Zero to start processing...")
                    time.sleep(5)  # Give Agent Zero time to start processing
                    self._listen_for_response(session, session_id)
                else:
                    print(f"🔍 DEBUG: Response text: {response.text}")
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

    def _listen_for_response(self, session: requests.Session, session_id: str):
        """Listen for SSE response from Agent Zero"""
        try:
            sse_url_with_session = f"{self.sse_url}?session_id={session_id}"
            print(f"👂 Step 3: Listening for response on: {sse_url_with_session}")
            
            headers = {
                'Accept': 'text/event-stream',
                'Cache-Control': 'no-cache'
            }
            
            response_endpoint = None
            
            with session.get(sse_url_with_session, headers=headers, stream=True, timeout=300) as response:
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
                                        # Check if this is a new endpoint for responses
                                        if data.startswith('/mcp/t-') and 'session_id=' in data:
                                            response_endpoint = f"{self.base_url}{data}"
                                            print(f"🔄 New response endpoint received: {response_endpoint}")
                                            print("📥 Step 4: Polling response endpoint...")
                                            
                                            # Try polling the response endpoint
                                            max_polls = 30  # 30 attempts
                                            poll_interval = 2  # 2 seconds between polls
                                            
                                            for poll_count in range(max_polls):
                                                try:
                                                    print(f"🔄 Poll {poll_count + 1}/{max_polls}...")
                                                    response = session.get(response_endpoint, timeout=10)
                                                    print(f"🔍 DEBUG: Poll Response status: {response.status_code}")
                                                    
                                                    if response.status_code == 200:
                                                        try:
                                                            result = response.json()
                                                            print("📨 Agent Zero Response:")
                                                            print(json.dumps(result, indent=2))
                                                            return
                                                        except json.JSONDecodeError:
                                                            print(f"📝 Agent Zero Response: {response.text}")
                                                            return
                                                    elif response.status_code == 202:
                                                        print("🔄 Response not ready yet, continuing to poll...")
                                                    else:
                                                        print(f"🔍 DEBUG: Poll Response text: {response.text}")
                                                        
                                                except Exception as e:
                                                    print(f"❌ Poll error: {e}")
                                                
                                                if poll_count < max_polls - 1:
                                                    time.sleep(poll_interval)
                                            
                                            print("⏰ Polling timeout - no response received")
                                                
                                            # Continue listening for more data
                                        else:
                                            try:
                                                event_data = json.loads(data)
                                                print("📨 Agent Zero Response:")
                                                print(json.dumps(event_data, indent=2))
                                                
                                                # Check if this is the final response
                                                if self._is_final_response(event_data):
                                                    print("🏁 Final response received")
                                                    return
                                                    
                                            except json.JSONDecodeError:
                                                print(f"📝 Agent Zero Response: {data}")
                                                
                                elif line.startswith('event: '):
                                    event_type = line[7:].strip()
                                    print(f"🎯 Event: {event_type}")
                                    
                                    if event_type in ['end', 'done', 'complete']:
                                        print("🏁 Stream ended")
                                        return
                        
                    # Timeout check for inactive streams
                    if time.time() - last_activity > 120:
                        print("⏰ No activity for 2 minutes, checking if response is complete...")
                        break
                        
                print("🔍 DEBUG: Stream ended")
                
        except requests.exceptions.Timeout:
            print("⏰ Timeout waiting for response")
        except requests.exceptions.RequestException as e:
            print(f"❌ Error listening for response: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error in response listener: {str(e)}")

    def _fetch_response_from_endpoint(self, session: requests.Session, endpoint_url: str):
        """Listen for SSE response from the response endpoint"""
        try:
            print(f"📥 Listening for SSE response from: {endpoint_url}")
            
            # The response endpoint is for SSE streaming, not for requests
            # We need to listen to it as an SSE stream without sending any payload
            headers = {
                'Accept': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
            
            print(f"🔍 DEBUG: Opening SSE stream to response endpoint...")
            
            # Use the SSE endpoint directly, not the messages endpoint
            sse_endpoint = endpoint_url.replace('/messages/', '/sse')
            if '?session_id=' in endpoint_url:
                session_id = endpoint_url.split('?session_id=')[1]
                sse_endpoint = f"{self.base_url}/mcp/t-{self.token}/sse?session_id={session_id}"
            
            print(f"🔍 DEBUG: SSE endpoint: {sse_endpoint}")
            
            with session.get(sse_endpoint, headers=headers, stream=True, timeout=300) as response:
                print(f"🔍 DEBUG: SSE Response status: {response.status_code}")
                print(f"🔍 DEBUG: SSE Response headers: {dict(response.headers)}")
                
                if response.status_code != 200:
                    print(f"🔍 DEBUG: SSE Response text: {response.text}")
                    response.raise_for_status()
                
                self._process_response_stream(response, "SSE")
                    
        except requests.exceptions.Timeout:
            print("⏰ Timeout waiting for response from endpoint")
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching response: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error fetching response: {str(e)}")

    def _process_response_stream(self, response, method_type: str):
        """Process the response stream from either GET or POST"""
        try:
            print(f"🔍 DEBUG: {method_type} response endpoint connection established")
            buffer = ""
            last_activity = time.time()
            
            for chunk in response.iter_content(chunk_size=1024, decode_unicode=False):
                if chunk:
                    last_activity = time.time()
                    # Decode bytes to string properly
                    try:
                        chunk_str = chunk.decode('utf-8') if isinstance(chunk, bytes) else str(chunk)
                        buffer += chunk_str
                    except UnicodeDecodeError:
                        # Skip invalid UTF-8 bytes
                        continue
                    
                    # Process complete lines
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        line = line.strip()
                        
                        if line:
                            print(f"🔍 DEBUG: Response Line: '{line}'")
                            
                            if line.startswith('data: '):
                                data = line[6:].strip()
                                if data and data != '[DONE]':
                                    try:
                                        event_data = json.loads(data)
                                        print("📨 Agent Zero Response:")
                                        print(json.dumps(event_data, indent=2))
                                        
                                        # Check if this is the final response
                                        if self._is_final_response(event_data):
                                            print("🏁 Final response received")
                                            return
                                            
                                    except json.JSONDecodeError:
                                        print(f"📝 Agent Zero Response: {data}")
                                        
                            elif line.startswith('event: '):
                                event_type = line[7:].strip()
                                print(f"🎯 Response Event: {event_type}")
                                
                                if event_type in ['end', 'done', 'complete']:
                                    print("🏁 Response stream ended")
                                    return
                
                # Timeout check for inactive streams
                if time.time() - last_activity > 120:
                    print("⏰ No response activity for 2 minutes, ending...")
                    break
                    
        except Exception as e:
            print(f"❌ Error processing response stream: {str(e)}")
            response.raise_for_status()
            
            print("🔍 DEBUG: Response endpoint connection established")
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
                            print(f"🔍 DEBUG: Response Line: '{line}'")
                            
                            if line.startswith('data: '):
                                data = line[6:].strip()
                                if data and data != '[DONE]':
                                    try:
                                        event_data = json.loads(data)
                                        print("📨 Agent Zero Response:")
                                        print(json.dumps(event_data, indent=2))
                                        
                                        # Check if this is the final response
                                        if self._is_final_response(event_data):
                                            print("🏁 Final response received")
                                            return
                                            
                                    except json.JSONDecodeError:
                                        print(f"📝 Agent Zero Response: {data}")
                                        
                            elif line.startswith('event: '):
                                event_type = line[7:].strip()
                                print(f"🎯 Response Event: {event_type}")
                                
                                if event_type in ['end', 'done', 'complete']:
                                    print("🏁 Response stream ended")
                                    return
                
                # Timeout check for inactive streams
                if time.time() - last_activity > 120:
                    print("⏰ No response activity for 2 minutes, ending...")
                    break
                        
        except requests.exceptions.Timeout:
            print("⏰ Timeout waiting for response from endpoint")
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching response: {str(e)}")
        except Exception as e:
            print(f"❌ Unexpected error fetching response: {str(e)}")

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
