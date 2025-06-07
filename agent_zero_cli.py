#!/opt/agent_zero_venv/bin/python3

import asyncio
import sys
import argparse
import json
import subprocess
import re
from fastmcp import Client
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from dotenv import load_dotenv

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
            error_output = result.stderr.strip()
            print(f"❌ Command failed (exit code {result.returncode})")
            return f"Error (exit code {result.returncode}): {error_output}"
            
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def process_message_with_commands(message):
    """Process message and replace `command` with subprocess output"""
    # Pattern per trovare comandi tra backticks
    command_pattern = r'`([^`]+)`'
    
    def replace_command(match):
        command = match.group(1).strip()
        # Esegui il comando e restituisci l'output
        output = execute_command(command)
        # Restituisci l'output formattato
        return f"```\n{output}\n```"
    
    # Sostituisci tutti i comandi trovati
    processed_message = re.sub(command_pattern, replace_command, message)
    
    return processed_message

def format_agent_response(result):
    """Format Agent Zero response in a user-friendly way"""
    current_chat_id = None
    
    # Se il risultato è una lista di TextContent (come nell'esempio)
    if isinstance(result, list) and len(result) > 0:
        # Prendi il primo elemento se è una lista
        first_item = result[0]
        if hasattr(first_item, 'text'):
            # È un TextContent object
            try:
                # Prova a parsare il JSON dal testo
                response_data = json.loads(first_item.text)
                if isinstance(response_data, dict):
                    status = response_data.get('status', 'unknown')
                    response_text = response_data.get('response', '')
                    current_chat_id = response_data.get('chat_id')
                    
                    # Mostra icona basata sullo status
                    if status == 'success':
                        print("✅ Agent Zero Response:")
                    elif status == 'error':
                        print("❌ Agent Zero Response:")
                    else:
                        print("📨 Agent Zero Response:")
                    
                    # Mostra solo il testo della risposta
                    print(response_text)
                    return current_chat_id
            except json.JSONDecodeError:
                # Se non è JSON valido, mostra il testo così com'è
                print("📨 Agent Zero Response:")
                print(first_item.text)
                return current_chat_id
    
    # Se il risultato è un dizionario diretto
    elif isinstance(result, dict):
        status = result.get('status', 'unknown')
        response_text = result.get('response', '')
        current_chat_id = result.get('chat_id')
        
        # Mostra icona basata sullo status
        if status == 'success':
            print("✅ Agent Zero Response:")
        elif status == 'error':
            print("❌ Agent Zero Response:")
        else:
            print("📨 Agent Zero Response:")
        
        # Mostra solo il testo della risposta se presente
        if response_text:
            print(response_text)
        else:
            # Fallback al JSON completo se non c'è campo response
            print(json.dumps(result, indent=2))
        
        return current_chat_id
    
    # Fallback per altri tipi di risultato
    else:
        print("📨 Agent Zero Response:")
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
    
    # Formatta la risposta in modo user-friendly
    extracted_chat_id = format_agent_response(result)
    
    # Usa il chat_id estratto dalla risposta se disponibile, altrimenti quello passato
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

    # URL del server Agent Zero MCP
    server_url = "http://localhost:5000/mcp/t-0/sse"

    print(f"🔗 Connecting to Agent Zero at: {server_url}")
    print(f"💬 Message: {args.message}")
    if is_persistent:
        print("🔄 Using persistent chat (default) - you can ask follow-up questions")
    else:
        print("-1️⃣ Using one-shot mode - the script will exit after the response")
    if args.chat_id:
        print(f"📝 Continuing chat: {args.chat_id}")
    
    try:
        # Crea il client FastMCP con transport HTTP
        client = Client(server_url)
        
        async with client:
            print("✅ Connected to Agent Zero")
            
            # Processa il primo messaggio per eseguire eventuali comandi
            processed_initial_message = process_message_with_commands(args.message)
            
            # Se il messaggio è stato modificato, mostra cosa verrà inviato
            if processed_initial_message != args.message:
                print(f"📝 Processed initial message with command outputs:")
                print(f"📤 Sending to Agent Zero...")
            
            # Invia il primo messaggio (processato)
            result, chat_id = await send_message_to_agent(
                client,
                processed_initial_message,
                args.chat_id,
                is_persistent
            )
            
            # Se è una chat persistente, entra nel loop interattivo
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
                        # Chiedi il prossimo messaggio
                        follow_up = (await session.prompt_async("\n💬 Your message: ")).strip()
                        
                        if follow_up.lower() in ['quit', 'exit', 'q']:
                            break
                        
                        if not follow_up:
                            continue
                        
                        # Processa il messaggio per eseguire eventuali comandi
                        processed_message = process_message_with_commands(follow_up)
                        
                        # Se il messaggio è stato modificato, mostra cosa verrà inviato
                        if processed_message != follow_up:
                            print(f"📝 Processed message with command outputs:")
                            print(f"📤 Sending to Agent Zero...")
                        
                        # Invia il messaggio di follow-up (processato)
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
                
                # Termina la chat persistente se abbiamo un chat_id
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