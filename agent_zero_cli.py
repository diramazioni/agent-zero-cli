#!/opt/agent_zero_venv/bin/python3

import asyncio
import sys
import argparse
import json
import subprocess
import re
from fastmcp import Client
from pathlib import Path
from urllib.parse import urlparse
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from dotenv import load_dotenv

COMMAND_HISTORY = []

def execute_command(command):
    """Execute a shell command and return its output"""
    try:
        print(f"🔧 Executing: {command}")
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            output = result.stdout.strip()
            print(f"✅ Command output ({len(output)} chars)")
            return output
        else:
            output = result.stdout.strip()
            error_output = result.stderr.strip()
            print(f"❌ Command failed (exit code {result.returncode})")
            return f"Error (exit code {result.returncode}): {error_output}\n{output}"
            
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def process_message_with_commands(message):
    """Process message and replace `command` with subprocess output and @file/url with content"""
    # Pattern to find commands within backticks
    command_pattern = r'`([^`]+)`'
    
    def replace_command(match):
        command = match.group(1).strip()
        output = execute_command(command)
        return f"```\n{output}\n```"
    
    # Pattern to find file/URL references with @
    # Capture the path/URL after '@'
    file_url_pattern = r'@([^\s]+)'
    
    def replace_file_or_url(match):
        ref = match.group(1).strip()
        
        # Check if it's a valid URL
        try:
            result = urlparse(ref)
            if all([result.scheme, result.netloc]):
                # It's a URL, replace with the fetch prompt
                return f"use mcp fetch url {ref}"
        except ValueError:
            pass # Not a valid URL, proceed as file
            
        # If not a URL, treat it as a local file path
        file_path = Path(ref)
        if file_path.is_file():
            try:
                content = file_path.read_text()
                return f"File content '{ref}':\n{content}"
            except Exception as e:
                return f"Error reading file '{ref}': {str(e)}"
        else:
            return f"Error: File not found or not a regular file: '{ref}'"
    
    # First, replace file/URL references to prevent backticks within them from being processed
    processed_message = re.sub(file_url_pattern, replace_file_or_url, message)
    
    # Then, replace all found commands
    processed_message = re.sub(command_pattern, replace_command, processed_message)
    
    return processed_message

def format_and_extract_commands(text):
    """Formats bash commands and extracts them into COMMAND_HISTORY"""
    global COMMAND_HISTORY
    
    bash_pattern = r"```bash\n(.*?)\n```"
    
    new_text = ""
    last_end = 0
    
    for match in re.finditer(bash_pattern, text, re.DOTALL):
        command = match.group(1).strip()
        if not command: # Skip empty command blocks
            continue
            
        COMMAND_HISTORY.append(command)
        command_index = len(COMMAND_HISTORY)
        
        new_text += text[last_end:match.start()]
        # Using a light blue for the command for better visibility on light/dark backgrounds
        formatted_command = f"  \033[94m[{command_index}] {command}\033[0m"
        new_text += formatted_command
        last_end = match.end()
        
    new_text += text[last_end:]
    
    return new_text

def format_agent_response(result):
    """Format Agent Zero response in a user-friendly way"""
    global COMMAND_HISTORY
    COMMAND_HISTORY.clear()
    current_chat_id = None
    
    # If the result is a list of TextContent (as in the example)
    if isinstance(result, list) and len(result) > 0:
        # Get the first element if it's a list
        first_item = result[0]
        if hasattr(first_item, 'text'):
            # It's a TextContent object
            try:
                # Try to parse JSON from the text
                response_data = json.loads(first_item.text)
                if isinstance(response_data, dict):
                    status = response_data.get('status', 'unknown')
                    response_text = response_data.get('response', '')
                    current_chat_id = response_data.get('chat_id')
                    
                    # Show icon based on status
                    if status == 'success':
                        print("✅ Agent Zero Response:")
                    elif status == 'error':
                        print("❌ Agent Zero Response:")
                    else:
                        print("📨 Agent Zero Response:")
                    
                    # Show only the response text
                    formatted_response = format_and_extract_commands(response_text)
                    print(formatted_response)
                    return current_chat_id
            except json.JSONDecodeError:
                # If it's not valid JSON, show the text as is
                print("📨 Agent Zero Response:")
                formatted_response = format_and_extract_commands(first_item.text)
                print(formatted_response)
                return current_chat_id
    
    # If the result is a direct dictionary
    elif isinstance(result, dict):
        status = result.get('status', 'unknown')
        response_text = result.get('response', '')
        current_chat_id = result.get('chat_id')
        
        # Show icon based on status
        if status == 'success':
            print("✅ Agent Zero Response:")
        elif status == 'error':
            print("❌ Agent Zero Response:")
        else:
            print("📨 Agent Zero Response:")
        
        # Show only the response text if present
        if response_text:
            formatted_response = format_and_extract_commands(response_text)
            print(formatted_response)
        else:
            # Fallback to full JSON if no response field
            print(json.dumps(result, indent=2))
        
        return current_chat_id
    
    # Fallback for other result types
    else:
        print("📨 Agent Zero Response:")
        if isinstance(result, str):
            formatted_response = format_and_extract_commands(result)
            print(formatted_response)
        else:
            print(result)
        return current_chat_id

async def send_message_to_agent(client, message, chat_id=None, persistent_chat=False):
    """Send a message to Agent Zero and return the result and chat_id"""
    result = await client.call_tool(
        "send_message",
        {
            "message": message,
            "attachments": None,
            "chat_id": chat_id,
            "persistent_chat": persistent_chat
        }
    )
    
    # Format Agent Zero response in a user-friendly way
    extracted_chat_id = format_agent_response(result)
    
    # Use the chat_id extracted from the response if available, otherwise the one passed
    current_chat_id = extracted_chat_id if extracted_chat_id else chat_id
    
    return result, current_chat_id

async def main():
    # Setup configuration
    # First, try to load a local .env file (for development)
    local_env_path = Path('.env')
    # Then, define the system-wide configuration path
    system_env_path = Path('/etc/agent_zero/.env')

    if local_env_path.is_file():
        load_dotenv(dotenv_path=local_env_path)
        print("ℹ️ Loaded configuration from local .env file.")
    elif system_env_path.is_file():
        load_dotenv(dotenv_path=system_env_path)
        print(f"ℹ️ Loaded configuration from {system_env_path}.")

    parser = argparse.ArgumentParser(description='Agent Zero CLI Client')
    parser.add_argument('message', help='Message to send to Agent Zero')
    parser.add_argument('-1', '--one-shot', action='store_true',
                        help='Run in non-persistent mode (single interaction)')
    parser.add_argument('--chat-id', help='Continue existing chat with this ID')

    args = parser.parse_args()

    # Determine if the chat should be persistent
    is_persistent = not args.one_shot

    # Agent Zero MCP server URL
    import os
    server_url = os.environ.get("AGENT_ZERO_MCP_URL", "http://localhost:5000/mcp/t-0/sse")

    print(f"🔗 Connecting to Agent Zero at: {server_url}")
    print(f"💬 Message: {args.message}")
    if is_persistent:
        print("🔄 Using persistent chat (default) - you can ask follow-up questions")
    else:
        print("-1️⃣ Using one-shot mode - the script will exit after the response")
    if args.chat_id:
        print(f"📝 Continuing chat: {args.chat_id}")
    
    try:
        # Create FastMCP client with HTTP transport
        client = Client(server_url)
        
        async with client:
            print("✅ Connected to Agent Zero")
            
            # Process the first message to execute any commands
            processed_initial_message = process_message_with_commands(args.message)
            
            # If the message has been modified, show what will be sent
            if processed_initial_message != args.message:
                print(f"📝 Processed initial message with command outputs:")
                print(f"📤 Sending to Agent Zero...")
            
            # Send the first (processed) message
            result, chat_id = await send_message_to_agent(
                client,
                processed_initial_message,
                args.chat_id,
                is_persistent
            )
            
            # If it's a persistent chat, enter the interactive loop
            if is_persistent:
                if chat_id:
                    print(f"\n💾 Chat ID: {chat_id}")
                
                print("\n" + "="*50)
                print("🔄 Persistent chat mode - Type your follow-up questions")
                print("Type 'quit', 'exit', or press Ctrl+C to end the session")
                print("="*50)
                
                history_file = str(Path.home() / ".agent_zero_cli_history")
                session = PromptSession(history=FileHistory(history_file))
                
                while True:
                    try:
                        # Ask for the next message
                        follow_up = (await session.prompt_async("\n💬 Your message: ")).strip()
                        
                        if follow_up.lower() in ['quit', 'exit', 'q']:
                            break
                        
                        if not follow_up:
                            continue

                        # Handle 'run' command
                        if follow_up.lower().startswith('run ') or follow_up.startswith('» '):
                            try:
                                command_index = int(follow_up.split(' ')[1]) - 1
                                if 0 <= command_index < len(COMMAND_HISTORY):
                                    command_to_run = COMMAND_HISTORY[command_index]
                                    output = execute_command(command_to_run)
                                    if output:
                                        print(output)
                                else:
                                    print("❌ Invalid command number.")
                            except (ValueError, IndexError):
                                print("❌ Invalid 'run' command format. Use 'run <number>'.")
                            continue # Ask for next input
                        
                        # Process the message to execute any commands
                        processed_message = process_message_with_commands(follow_up)
                        
                        # If the message has been modified, show what will be sent
                        if processed_message != follow_up:
                            print(f"📝 Processed message with command outputs:")
                            print(f"📤 Sending to Agent Zero...")
                        
                        # Send the follow-up (processed) message
                        result, chat_id = await send_message_to_agent(
                            client,
                            processed_message,
                            chat_id,
                            True
                        )
                        
                    except KeyboardInterrupt:
                        print("\n\n👋 Session ended by user")
                        break
                    except EOFError:
                        print("\n\n👋 Session ended")
                        break
                
                # End the persistent chat if we have a chat_id
                if chat_id:
                    try:
                        print(f"\n🔚 Ending persistent chat: {chat_id}")
                        await client.call_tool("finish_chat", {"chat_id": chat_id})
                        print("✅ Chat session ended")
                    except Exception as e:
                        print(f"⚠️  Warning: Could not properly end chat session: {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())