import asyncio
import discord
from discord.ext import commands
import server

# ==========================================
# PASTE YOUR TOKEN BELOW INSIDE THE QUOTES
DISCORD_TOKEN = "YOUR_DISCORD_TOKEN_HERE"
# ==========================================

OWNER_ID = 1456353767606849628

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        # Syncing slash commands globally
        synced = await bot.tree.sync()
        print(f"[bot] synced {len(synced)} slash commands")
    except Exception as e:
        print(f"[bot] sync failed: {e}")

async def main():
    # Start the web server for Render (and for the Lua loader API)
    runner = await server.start_server()
    
    async with bot:
        # Load the panel cog
        await bot.load_extension("cogs.panel")
        
        try:
            # Start the Discord bot
            await bot.start(DISCORD_TOKEN)
        finally:
            # Clean up web server if bot crashes
            await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
