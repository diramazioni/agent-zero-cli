#!/usr/bin/env python3

import asyncio
import sys
from fastmcp import Client

async def main():
    if len(sys.argv) != 2:
        print("Usage: ./agent_zero_cli_fastmcp.py 'Your message here'")
        sys.exit(1)
    
    message = sys.argv[1]
    
    # URL del server Agent Zero MCP
    server_url = "http://localhost:5000/mcp/t-0/sse"
    
    print(f"🔗 Connecting to Agent Zero at: {server_url}")
    print(f"💬 Message: {message}")
    
    try:
        # Crea il client FastMCP con transport HTTP
        client = Client(server_url)
        
        async with client:
            print("✅ Connected to Agent Zero")
            
            # Chiama il tool send_message
            result = await client.call_tool(
                "send_message",
                {
                    "message": message,
                    "attachments": None,
                    "chat_id": None,
                    "persistent_chat": None
                }
            )
            
            print("📨 Agent Zero Response:")
            print(result)
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())