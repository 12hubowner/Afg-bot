import time
import discord
from discord.ext import commands
from discord import app_commands
import db
import sqlite3

OWNER_ID = 1456353767606849628
DB_PATH = "keyhub.db"

def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message("❌ Owner only.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

# ---------------- MODALS ----------------

class RedeemModal(discord.ui.Modal, title="Redeem a key"):
    key_input = discord.ui.TextInput(
        label="Enter script key below:",
        placeholder="VZeGvax...",
        required=True,
        max_length=50,
    )

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

        await interaction.response.send_message("✅ Key redeemed successfully! Click **Get Script** to get your loader.", ephemeral=True)

# ---------------- PANEL VIEW ----------------

class PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Redeem Key", style=discord.ButtonStyle.success, emoji="🔑", custom_id="panel:redeem", row=0)
    async def redeem(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RedeemModal())

    @discord.ui.button(label="Get Script", style=discord.ButtonStyle.primary, emoji="📜", custom_id="panel:getscript", row=0)
    async def get_script(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = await db.get_user_key(interaction.user.id)
        if not row:
            await interaction.response.send_message("❌ You don't have a key. Click **Redeem Key** first.", ephemeral=True)
            return
        if row["blacklisted"]:
            await interaction.response.send_message("❌ You are blacklisted.", ephemeral=True)
            return
        if row["auth_expire"] and int(time.time()) >= row["auth_expire"]:
            await interaction.response.send_message("❌ Your key has expired.", ephemeral=True)
            return

        loadstring_payload = (
            f'script_key = "{row["key"]}"\n'
            f'loadstring(game:HttpGet("https://afg-bot.onrender.com/loader"))()'
        )
        try:
            await interaction.user.send(f"**Your script:**\n```lua\n{loadstring_payload}\n```")
            await interaction.response.send_message("✅ Sent to your DMs.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I can't DM you. Enable DMs.", ephemeral=True)

    @discord.ui.button(label="Get Role", style=discord.ButtonStyle.secondary, emoji="👤", custom_id="panel:getrole", row=0)
    async def get_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_id_str = await db.get_setting("buyer_role_id")
        if not role_id_str:
            await interaction.response.send_message("❌ Role not configured. Ask owner to run /setuprole.", ephemeral=True)
            return

        role = interaction.guild.get_role(int(role_id_str))
        if not role:
            await interaction.response.send_message("❌ Role not found in server.", ephemeral=True)
            return

        row = await db.get_user_key(interaction.user.id)
        if not row or row["blacklisted"]:
            embed = discord.Embed(
                title="Not whitelisted!",
                description="You need to be whitelisted to get this role.\nIf you have a script key, click on the Redeem button below to redeem it",
                color=discord.Color.red()
            )
            embed.set_footer(text=f"Today at {time.strftime('%I:%M %p')}")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Role {role.mention} assigned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to give that role.", ephemeral=True)

    @discord.ui.button(label="Reset HWID", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="panel:resethwid", row=1)
    async def reset_hwid(self, interaction: discord.Interaction, button: discord.ui.Button):
        ok = await db.reset_hwid(interaction.user.id)
        if ok:
            await interaction.response.send_message("✅ HWID reset. Your key will bind to a new machine.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ No key found to reset.", ephemeral=True)

    @discord.ui.button(label="Get Stats", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="panel:getstats", row=1)
    async def get_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        row = await db.get_user_key(interaction.user.id)
        if not row:
            await interaction.response.send_message("❌ No key found.", ephemeral=True)
            return

        hwid_status = f"`{row['hwid'][:10]}...`" if row["hwid"] else "Not bound"
        expires = f"<t:{row['auth_expire']}:R>" if row["auth_expire"] else "Never"
        status = "Blacklisted" if row["blacklisted"] else "Active"

        embed = discord.Embed(title="📊 Account Stats", color=discord.Color.blue())
        embed.add_field(name="Key", value=f"||`{row['key']}`||", inline=False)
        embed.add_field(name="Status", value=status)
        embed.add_field(name="Expires", value=expires)
        embed.add_field(name="HWID", value=hwid_status)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ---------------- COMMANDS ----------------

class Panel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_app_command_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.CheckFailure):
            return
        if interaction.response.is_done():
            await interaction.followup.send(f"Error: `{error}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"Error: `{error}`", ephemeral=True)

    @app_commands.command(name="login", description="Connects this discord server to your Luarmor account")
    @is_owner()
    @app_commands.describe(api_key="Luarmor API key to log in")
    async def login(self, interaction: discord.Interaction, api_key: str):
        await db.set_setting("api_key", api_key)
        await interaction.response.send_message(f"✅ Logged in successfully. API Key saved.", ephemeral=True)

    @app_commands.command(name="setpanel", description="Sends the control panel message in this channel")
    @is_owner()
    @app_commands.describe(loader_script="The loader.lua file", manager_role="Role required to manage")
    async def setpanel(self, interaction: discord.Interaction, loader_script: discord.Attachment, manager_role: discord.Role):
        if not loader_script.filename.endswith(".lua"):
            await interaction.response.send_message("❌ Attachment must be a .lua file.", ephemeral=True)
            return

        raw = await loader_script.read()
        with open("loader.lua", "wb") as f:
            f.write(raw)

        embed = discord.Embed(
            title="SAE Control Panel",
            description=(
                "This control panel is for the project: **SAE**\n"
                "If you're a buyer, click on the buttons below to redeem your key, get the script or get your role"
            ),
            color=discord.Color.from_rgb(240, 160, 0) 
        )
        embed.set_footer(text=f"Sent by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed, view=PanelView())
        await interaction.followup.send(f"✅ Panel posted. Manager role set to {manager_role.mention}.", ephemeral=True)

    @app_commands.command(name="whitelist", description="Whitelists a user")
    @is_owner()
    @app_commands.describe(member="User to whitelist", days="Days until expiry (0 = never)")
    async def whitelist(self, interaction: discord.Interaction, member: discord.Member, days: int = 0):
        await interaction.response.defer(ephemeral=True)
        key_days = days if days > 0 else None
        key = await db.create_key(member.id, key_days)

        try:
            await member.send(f"🔑 You've been whitelisted.\n**Key:** `{key}`\n**Expires in:** {days if days > 0 else 'never'}\n\nClick **Redeem Key** in the server.")
            await interaction.followup.send(f"✅ Whitelisted {member.mention}. Key: `{key}` (DM sent).", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(f"✅ Whitelisted {member.mention}. Key: `{key}` (couldn't DM).", ephemeral=True)

    @app_commands.command(name="unwhitelist", description="Unwhitelists the user from a project")
    @is_owner()
    async def unwhitelist(self, interaction: discord.Interaction, member: discord.Member):
        n = await db.delete_user_keys(member.id)
        if n > 0:
            await interaction.response.send_message(f"✅ Unwhitelisted {member.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No key found.", ephemeral=True)

    @app_commands.command(name="blacklist", description="Blacklists the user from a project")
    @is_owner()
    async def blacklist(self, interaction: discord.Interaction, member: discord.Member):
        n = await db.blacklist_user(member.id)
        if n > 0:
            await interaction.response.send_message(f"✅ Blacklisted {member.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No key found.", ephemeral=True)

    @app_commands.command(name="mass-generate", description="Generates multiple keys. Make sure DMs are ENABLED.")
    @is_owner()
    @app_commands.describe(amount="How many keys to generate", days="Days until expiry (0 = never)")
    async def mass_generate(self, interaction: discord.Interaction, amount: int, days: int = 0):
        await interaction.response.defer(ephemeral=True)
        key_days = days if days > 0 else None
        keys = []
        for _ in range(amount):
            k = await db.create_key(OWNER_ID, key_days, "Mass Gen")
            keys.append(k)
        
        chunk_size = 20
        chunks = [keys[i:i + chunk_size] for i in range(0, len(keys), chunk_size)]
        for chunk in chunks:
            text = "\n".join([f"`{k}`" for k in chunk])
            await interaction.followup.send(f"**Generated Keys:**\n{text}", ephemeral=True)

    @app_commands.command(name="compensate", description="Adds days to everyone in a project.")
    @is_owner()
    @app_commands.describe(days="Number of days to add to all active keys")
    async def compensate(self, interaction: discord.Interaction, days: int):
        await interaction.response.defer(ephemeral=True)
        add_seconds = days * 86400
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE keys SET auth_expire = auth_expire + ? WHERE auth_expire IS NOT NULL AND blacklisted = 0", (add_seconds,))
        conn.commit()
        n = c.rowcount
        conn.close()

        await interaction.followup.send(f"✅ Compensated {n} active users by {days} days.", ephemeral=True)

    @app_commands.command(name="force-resethwid", description="Resets the HWID of a user, ignores cooldown")
    @is_owner()
    async def force_resethwid(self, interaction: discord.Interaction, member: discord.Member):
        ok = await db.reset_hwid(member.id)
        if ok:
            await interaction.response.send_message(f"✅ HWID forcefully reset for {member.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ No key found.", ephemeral=True)

async def setup(bot):
    bot.add_view(PanelView())
    await bot.add_cog(Panel(bot))
