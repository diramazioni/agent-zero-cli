#!/usr/bin/env python3

import asyncio
import sys
import argparse
import json
from fastmcp import Client

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
    
    print("📨 Agent Zero Response:")
    
    # Estrai il chat_id dalla risposta se presente
    current_chat_id = chat_id
    if isinstance(result, dict):
        print(json.dumps(result, indent=2))
        if 'chat_id' in result:
            current_chat_id = result['chat_id']
    else:
        print(result)
    
    return result, current_chat_id

async def main():
    parser = argparse.ArgumentParser(description='Agent Zero CLI Client')
    parser.add_argument('message', help='Message to send to Agent Zero')
    parser.add_argument('-p', '--persistent', action='store_true',
                       help='Use persistent chat (allows follow-up questions)')
    parser.add_argument('--chat-id', help='Continue existing chat with this ID')
    
    args = parser.parse_args()
    
    # URL del server Agent Zero MCP
    server_url = "http://localhost:5000/mcp/t-0/sse"
    
    print(f"🔗 Connecting to Agent Zero at: {server_url}")
    print(f"💬 Message: {args.message}")
    if args.persistent:
        print("🔄 Using persistent chat - you can ask follow-up questions")
    if args.chat_id:
        print(f"📝 Continuing chat: {args.chat_id}")
    
    try:
        # Crea il client FastMCP con transport HTTP
        client = Client(server_url)
        
        async with client:
            print("✅ Connected to Agent Zero")
            
            # Invia il primo messaggio
            result, chat_id = await send_message_to_agent(
                client,
                args.message,
                args.chat_id,
                args.persistent
            )
            
            # Se è una chat persistente, entra nel loop interattivo
            if args.persistent:
                if chat_id:
                    print(f"\n💾 Chat ID: {chat_id}")
                
                print("\n" + "="*50)
                print("🔄 Persistent chat mode - Type your follow-up questions")
                print("Type 'quit', 'exit', or press Ctrl+C to end the session")
                print("="*50)
                
                while True:
                    try:
                        # Chiedi il prossimo messaggio
                        follow_up = input("\n💬 Your message: ").strip()
                        
                        if follow_up.lower() in ['quit', 'exit', 'q']:
                            break
                        
                        if not follow_up:
                            continue
                        
                        # Invia il messaggio di follow-up
                        result, chat_id = await send_message_to_agent(
                            client,
                            follow_up,
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