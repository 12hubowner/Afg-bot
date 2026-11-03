
import time
import discord
from discord.ext import commands
from discord import app_commands
import db
import sqlite3

OWNER_ID = 1456353767606849628

def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ Owner only.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

class RedeemModal(discord.ui.Modal, title="Redeem a key"):
    key_input = discord.ui.TextInput(label="Enter script key below:", placeholder="XXXX-XXXX-XXXX-XXXX", required=True, max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        key = self.key_input.value.strip().upper()
        row = await db.get_key(key)
        
        if not row:
            await interaction.response.send_message("❌ Invalid key.", ephemeral=True)
            return
        if row["blacklisted"]:
            await interaction.response.send_message("❌ This key is blacklisted.", ephemeral=True)
            return
        if row["discord_id"] != interaction.user.id:
            await interaction.response.send_message("❌ This key belongs to someone else.", ephemeral=True)
            return

        await interaction.response.send_message("✅ Key redeemed successfully! Click **Get Script**.", ephemeral=True)

class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Redeem Key", style=discord.ButtonStyle.success, emoji="🔑", custom_id="panel:redeem", row=0)
    async def redeem(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RedeemModal())

    @discord.ui.button(label="Get Script", style=discord.ButtonStyle.primary, emoji="📜", custom_id="panel:getscript", row=0)
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = await db.get_user_key(interaction.user.id)
        if not row: return await interaction.response.send_message("❌ You don't have a key.", ephemeral=True)
        if row["blacklisted"]: return await interaction.response.send_message("❌ You are blacklisted.", ephemeral=True)
        if row["auth_expire"] and int(time.time()) >= row["auth_expire"]: return await interaction.response.send_message("❌ Your key has expired.", ephemeral=True)

        loadstring_payload = f'script_key = "{row["key"]}"\nloadstring(game:HttpGet("https://afg-bot.onrender.com/loader"))()'
        try:
            await interaction.user.send(f"**Your script:**\n```lua\n{loadstring_payload}\n```")
            await interaction.response.send_message("✅ Sent to your DMs.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I can't DM you. Enable DMs.", ephemeral=True)

    @discord.ui.button(label="Get Role", style=discord.ButtonStyle.secondary, emoji="👤", custom_id="panel:getrole", row=0)
    async def get_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_id_str = await db.get_setting("buyer_role_id")
        if not role_id_str: return await interaction.response.send_message("❌ Role not configured.", ephemeral=True)
        role = interaction.guild.get_role(int(role_id_str))
        if not role: return await interaction.response.send_message("❌ Role not found.", ephemeral=True)

        row = await db.get_user_key(interaction.user.id)
        if not row or row["blacklisted"]:
            embed = discord.Embed(title="Not whitelisted!", description="You need to be whitelisted to get this role.\nIf you have a script key, click on the Redeem button below to redeem it", color=discord.Color.red())
            embed.set_footer(text=f"Today at {time.strftime('%I:%M %p')}")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Role {role.mention} assigned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I can't give that role.", ephemeral=True)

    @discord.ui.button(label="Reset HWID", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="panel:resethwid", row=1)
    async def reset_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok = await db.reset_hwid(interaction.user.id)
        if ok: await interaction.response.send_message("✅ HWID reset.", ephemeral=True)
        else: await interaction.response.send_message("❌ No key found.", ephemeral=True)

    @discord.ui.button(label="Get Stats", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="panel:getstats", row=1)
    async def get_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = await db.get_user_key(interaction.user.id)
        if not row: return await interaction.response.send_message("❌ No key found.", ephemeral=True)
        
        hwid_status = f"`{row['hwid'][:10]}...`" if row["hwid"] else "Not bound"
        expires = f"<t:{row['auth_expire']}:R>" if row["auth_expire"] else "Never"
        status = "Blacklisted" if row["blacklisted"] else "Active"

        embed = discord.Embed(title="📊 Account Stats", color=discord.Color.blue())
        embed.add_field(name="Key", value=f"||`{row['key']}`||", inline=False)
        embed.add_field(name="Status", value=status)
        embed.add_field(name="Expires", value=expires)
        embed.add_field(name="HWID", value=hwid_status)
        await interaction.response.send_message(embed=embed, ephemeral=True)

class Panel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure): return
        msg = f"Error: `{error}`"
        if interaction.response.is_done(): await interaction.followup.send(msg, ephemeral=True)
        else: await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="setup", description="Sets up the bot for the current server")
    @is_owner()
    async def setup_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ Bot is setup and ready to use.", ephemeral=True)

    @app_commands.command(name="login", description="Connects this discord server to your Luarmor account")
    @is_owner()
    @app_commands.describe(api_key="Luarmor API key to log in")
    async def login(self, interaction: discord.Interaction, api_key: str):
        await db.set_setting("api_key", api_key)
        await interaction.response.send_message(f"✅ Logged in successfully. API Key saved.", ephemeral=True)

    @app_commands.command(name="setpanel", description="Sends the control panel message in this channel")
    @is_owner()
    @app_commands.describe(loader_script="The loader.lua file users receive", manager_role="Role required to manage keys")
    async def setpanel(self, interaction: discord.Interaction, loader_script: discord.Attachment, manager_role: discord.Role):
        if not loader_script.filename.endswith(".lua"): return await interaction.response.send_message("❌ Must be .lua", ephemeral=True)
        
        raw = await loader_script.read()
        with open("loader.lua", "wb") as f: f.write(raw)

        embed = discord.Embed(title="GreenDuels Control Panel", description="This control panel is for the project: **GreenDuels**\nIf you're a buyer, click on the buttons below to redeem your key, get the script or get your role", color=discord.Color.from_rgb(240, 160, 0))
        embed.set_footer(text=f"Sent by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed, view=PanelView())
        await interaction.followup.send(f"✅ Panel posted. Manager role set to {manager_role.mention}.", ephemeral=True)

    @app_commands.command(name="whitelist", description="Whitelists a user")
    @is_owner()
    @app_commands.describe(member="User", days="Days (0 = never)")
    async def whitelist(self, interaction: discord.Interaction, member: discord.Member, days: int = 0):
        await interaction.response.defer(ephemeral=True)
        key_days = days if days > 0 else None
        key = await db.create_key(member.id, key_days)
        try:
            await member.send(f"🔑 You've been whitelisted.\n**Key:** `{key}`\nClick **Redeem Key** in the server.")
            await interaction.followup.send(f"✅ Whitelisted {member.mention}. Key: `{key}` (DM sent).", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(f"✅ Whitelisted {member.mention}. Key: `{key}` (DM failed).", ephemeral=True)

    @app_commands.command(name="unwhitelist", description="Unwhitelists the user")
    @is_owner()
    async def unwhitelist(self, interaction: discord.Interaction, member: discord.Member):
        n = await db.delete_user_keys(member.id)
        if n > 0: await interaction.response.send_message(f"✅ Unwhitelisted {member.mention}.", ephemeral=True)
        else: await interaction.response.send_message(f"❌ No key found.", ephemeral=True)

    @app_commands.command(name="blacklist", description="Blacklists the user")
    @is_owner()
    async def blacklist(self, interaction: discord.Interaction, member: discord.Member):
        n = await db.blacklist_user(member.id)
        if n > 0: await interaction.response.send_message(f"✅ Blacklisted {member.mention}.", ephemeral=True)
        else: await interaction.response.send_message(f"❌ No key found.", ephemeral=True)

    @app_commands.command(name="deletekey", description="Deletes a specific key")
    @is_owner()
    @app_commands.describe(key="The exact key string")
    async def deletekey(self, interaction: discord.Interaction, key: str):
        ok = await db.delete_specific_key(key.upper())
        if ok: await interaction.response.send_message("✅ Key deleted.", ephemeral=True)
        else: await interaction.response.send_message("❌ Key not found.", ephemeral=True)

    @app_commands.command(name="checkkey", description="Checks info about a specific key")
    @is_owner()
    async def checkkey(self, interaction: discord.Interaction, key: str):
        row = await db.get_key(key.upper())
        if not row: return await interaction.response.send_message("❌ Invalid key.", ephemeral=True)
        
        embed = discord.Embed(title="Key Info", color=discord.Color.blue())
        embed.add_field(name="Key", value=row["key"])
        embed.add_field(name="Discord ID", value=row["discord_id"])
        embed.add_field(name="HWID", value=row["hwid"] or "Not bound")
        embed.add_field(name="Blacklisted", value="Yes" if row["blacklisted"] else "No")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="mass-generate", description="Generates multiple keys")
    @is_owner()
    async def mass_generate(self, interaction: discord.Interaction, amount: int, days: int = 0):
        await interaction.response.defer(ephemeral=True)
        keys = [await db.create_key(OWNER_ID, days if days > 0 else None, "Mass Gen") for _ in range(amount)]
        text = "\n".join([f"`{k}`" for k in keys[:20]])
        await interaction.followup.send(f"**Generated {amount} keys:**\n{text}", ephemeral=True)

    @app_commands.command(name="compensate", description="Adds days to everyone")
    @is_owner()
    async def compensate(self, interaction: discord.Interaction, days: int):
        await interaction.response.defer(ephemeral=True)
        conn = sqlite3.connect(db.DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE keys SET auth_expire = auth_expire + ? WHERE auth_expire IS NOT NULL AND blacklisted = 0", (days * 86400,))
        conn.commit()
        n = c.rowcount
        conn.close()
        await interaction.followup.send(f"✅ Compensated {n} users by {days} days.", ephemeral=True)

    @app_commands.command(name="force-resethwid", description="Resets the HWID of a user")
    @is_owner()
    async def force_resethwid(self, interaction: discord.Interaction, member: discord.Member):
        ok = await db.reset_hwid(member.id)
        if ok: await interaction.response.send_message(f"✅ HWID forcefully reset for {member.mention}.", ephemeral=True)
        else: await interaction.response.send_message(f"❌ No key found.", ephemeral=True)

    @app_commands.command(name="stats", description="Shows panel statistics")
    @is_owner()
    async def stats(self, interaction: discord.Interaction):
        total, active, blacklisted = await db.get_all_stats()
        embed = discord.Embed(title="📊 Project Stats", color=discord.Color.green())
        embed.add_field(name="Total Keys", value=str(total))
        embed.add_field(name="Active (HWID Bound)", value=str(active))
        embed.add_field(name="Blacklisted", value=str(blacklisted))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="reset-cooldown", description="Resets the HWID reset cooldown for a user")
    @is_owner()
    async def reset_cooldown(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.send_message(f"✅ Cooldown reset for {member.mention}.", ephemeral=True)

async def setup(bot):
    bot.add_view(PanelView())
    await bot.add_cog(Panel(bot))
