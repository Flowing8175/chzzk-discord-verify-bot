import os
import asyncio
import logging
import random
import string
import json
import socketio

import discord
from discord.ext import tasks
from dotenv import load_dotenv

from chzzk_api import ChzzkAPI

# --- Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# --- Environment Variable Validation ---
required_vars = [
    'DISCORD_BOT_TOKEN', 'DISCORD_GUILD_ID', 'DISCORD_CHANNEL_ID',
    'DISCORD_ROLE_ID', 'CHZZK_CHANNEL_ID', 'CHZZK_ACCESS_TOKEN',
    'CHZZK_REFRESH_TOKEN', 'CHZZK_CLIENT_ID', 'CHZZK_CLIENT_SECRET'
]
env_vars = {}
missing_vars = False
for var in required_vars:
    value = os.getenv(var)
    if not value:
        logging.error(f"Missing required environment variable: {var}")
        missing_vars = True
    env_vars[var] = value

if missing_vars:
    exit("Exiting due to missing environment variables.")

# --- Globals ---
intents = discord.Intents.default()
intents.members = True
bot = discord.Bot(intents=intents)

chzzk_client = ChzzkAPI(
    client_id=env_vars['CHZZK_CLIENT_ID'],
    client_secret=env_vars['CHZZK_CLIENT_SECRET'],
    access_token=env_vars['CHZZK_ACCESS_TOKEN'],
    refresh_token=env_vars['CHZZK_REFRESH_TOKEN']
)

# { "123456": 1234567890 (discord_user_id) }
verification_codes = {}
ANNOUNCEMENT_MESSAGE_ID_FILE = "announcement_message_id.txt"
announcement_message_id = None

sio = socketio.AsyncClient()

# --- Helper Functions ---
def save_message_id(message_id: int):
    global announcement_message_id
    announcement_message_id = message_id
    with open(ANNOUNCEMENT_MESSAGE_ID_FILE, 'w') as f:
        f.write(str(message_id))

def load_message_id() -> int | None:
    global announcement_message_id
    if os.path.exists(ANNOUNCEMENT_MESSAGE_ID_FILE):
        with open(ANNOUNCEMENT_MESSAGE_ID_FILE, 'r') as f:
            try:
                message_id = int(f.read().strip())
                announcement_message_id = message_id
                return message_id
            except (ValueError, TypeError):
                return None
    return None

def generate_code() -> str:
    """Generates a 6-digit unique verification code."""
    while True:
        code = ''.join(random.choices(string.digits, k=6))
        if code not in verification_codes:
            return code

def get_verification_embed(online: bool, error: bool = False) -> discord.Embed:
    """Creates the embed for the verification message."""
    if error:
        title = "❌ 인증 봇 오프라인"
        description = "봇에 오류가 발생하여 현재 인증을 진행할 수 없습니다.\n관리자에게 문의해주세요."
        color = discord.Color.red()
    elif online:
        title = "✅ 치지직-디스코드 연동 인증"
        description = "치지직 계정과 디스코드 계정을 연동하여 인증된 역할을 받으세요!\n\n**인증하기** 버튼을 눌러 6자리 코드를 발급받고, 방송 채팅창에 입력해주세요."
        color = discord.Color.green()
    else: # Offline
        title = "💤 인증 봇 오프라인"
        description = "봇이 현재 오프라인 상태입니다.\n인증을 진행할 수 없습니다. 잠시 후 다시 시도해주세요."
        color = discord.Color.greyple()

    embed = discord.Embed(title=title, description=description, color=color)
    embed.set_footer(text="치지직 인증 봇")
    return embed

# --- Discord UI Views ---
class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="인증하기", style=discord.ButtonStyle.primary, custom_id="chzzk_verify_button")
    async def button_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        code = generate_code()
        verification_codes[code] = interaction.user.id
        logging.info(f"Generated code {code} for user {interaction.user.name} ({interaction.user.id})")

        await interaction.response.send_message(
            f"**인증 코드가 발급되었습니다!**\n> 방송 채팅에 `{code}`를 입력해주세요!\n\n(이 메시지는 다른 사람에게 보이지 않습니다.)",
            ephemeral=True
        )

# --- Tasks ---
@tasks.loop(hours=20)
async def refresh_chzzk_token():
    logging.info("Attempting to refresh Chzzk access token...")
    success = await chzzk_client.refresh_access_token()
    if not success:
        logging.error("Failed to refresh token. The bot may stop working correctly.")
        # Optionally, notify the admin via Discord message

# --- Chzzk WebSocket Handlers ---
@sio.event
async def connect():
    logging.info("Socket.IO connected.")
    # The 'SYSTEM' event with type 'connected' will provide the session key
    # which we need to subscribe to chat events.

@sio.event
async def disconnect():
    logging.warning("Socket.IO disconnected. Will attempt to reconnect.")

@sio.event
async def SYSTEM(data):
    logging.info(f"Received SYSTEM event: {data}")
    if data.get('type') == 'connected':
        session_key = data.get('data', {}).get('sessionKey')
        if session_key:
            logging.info(f"Got sessionKey: {session_key}. Subscribing to chat.")
            await chzzk_client.subscribe_to_chat(session_key)

@sio.event
async def CHAT(data):
    # The data from socketio is a string, needs to be parsed
    chat_info = json.loads(data)

    # According to docs, chat messages are in a list
    for chat in chat_info.get('b', []):
        message = chat.get('m')
        sender_profile = json.loads(chat.get('p'))
        sender_nickname = sender_profile.get('nickname')

        if not message or not sender_nickname:
            continue

        logging.debug(f"Chzzk Chat: [{sender_nickname}] {message}")

        if message in verification_codes:
            discord_user_id = verification_codes[message]
            logging.info(f"Verification code '{message}' from Chzzk user '{sender_nickname}' matches Discord user ID {discord_user_id}.")

            guild = bot.get_guild(int(env_vars['DISCORD_GUILD_ID']))
            if not guild:
                logging.error(f"Could not find guild {env_vars['DISCORD_GUILD_ID']} for verification.")
                return

            member = guild.get_member(discord_user_id)
            if not member:
                logging.warning(f"Could not find member with ID {discord_user_id} in the guild.")
                return

            role_to_add = guild.get_role(int(env_vars['DISCORD_ROLE_ID']))
            if not role_to_add:
                logging.error(f"Could not find role with ID {env_vars['DISCORD_ROLE_ID']}.")
                return

            try:
                # Truncate nickname if necessary (Discord limit is 32)
                new_nick = f"{sender_nickname}({member.display_name})"
                if len(new_nick) > 32:
                    new_nick = new_nick[:29] + "...)"

                await member.edit(nick=new_nick)
                await member.add_roles(role_to_add)

                # Send confirmation to Chzzk chat
                await chzzk_client.send_chat_message(f"{sender_nickname} 님 인증되었습니다!")

                logging.info(f"Successfully verified user {member.name}. Nickname changed and role assigned.")

                # Clean up
                del verification_codes[message]

            except discord.Forbidden:
                logging.error("Bot lacks permissions to change nickname or assign roles. Please check permissions.")
            except Exception as e:
                logging.error(f"An error occurred during verification for user {discord_user_id}: {e}")


async def chzzk_listener_task():
    """Connects to the Chzzk WebSocket and listens for events."""
    while True:
        try:
            ws_url = await chzzk_client.get_websocket_url()
            if not ws_url:
                logging.error("Could not get WebSocket URL. Retrying in 60 seconds.")
                await asyncio.sleep(60)
                continue

            logging.info(f"Connecting to Chzzk WebSocket: {ws_url}")
            await sio.connect(ws_url, transports=['websocket'])
            await sio.wait() # Wait until disconnection

        except socketio.exceptions.ConnectionError as e:
            logging.error(f"Socket.IO connection error: {e}. Retrying...")
        except Exception as e:
            logging.error(f"An unexpected error occurred in the listener task: {e}. Retrying...")

        if sio.connected:
            await sio.disconnect() # Ensure we are disconnected before retrying

        await asyncio.sleep(30) # Wait before attempting to reconnect

# --- Bot Events ---
@bot.event
async def on_ready():
    global announcement_message_id
    logging.info(f"Logged in as {bot.user}")

    # Add persistent view
    bot.add_view(VerificationView())

    # Start background tasks
    if not refresh_chzzk_token.is_running():
        refresh_chzzk_token.start()

    # Start the Chzzk listener
    asyncio.create_task(chzzk_listener_task())

    # Setup announcement message
    guild = bot.get_guild(int(env_vars['DISCORD_GUILD_ID']))
    if not guild:
        logging.error(f"Could not find guild with ID {env_vars['DISCORD_GUILD_ID']}")
        return

    channel = guild.get_channel(int(env_vars['DISCORD_CHANNEL_ID']))
    if not channel:
        logging.error(f"Could not find channel with ID {env_vars['DISCORD_CHANNEL_ID']}")
        return

    message_id = load_message_id()
    message = None
    if message_id:
        try:
            message = await channel.fetch_message(message_id)
        except discord.NotFound:
            logging.warning("Saved message ID not found. Will create a new message.")
            message = None

    embed = get_verification_embed(online=True)
    view = VerificationView()

    if message:
        await message.edit(embed=embed, view=view)
        logging.info("Edited existing announcement message.")
    else:
        new_message = await channel.send(embed=embed, view=view)
        save_message_id(new_message.id)
        logging.info(f"Sent new announcement message with ID {new_message.id}")

@bot.event
async def on_close():
    logging.info("Bot is shutting down...")
    if sio.connected:
        await sio.disconnect()
        logging.info("Socket.IO client disconnected.")

    if announcement_message_id:
        try:
            # We need a new session to send one last message, or handle this better.
            # For simplicity, we assume the bot object is still somewhat alive.
            guild = bot.get_guild(int(env_vars['DISCORD_GUILD_ID']))
            channel = guild.get_channel(int(env_vars['DISCORD_CHANNEL_ID']))
            if guild and channel:
                message = await channel.fetch_message(announcement_message_id)
                await message.edit(embed=get_verification_embed(online=False), view=None)
                logging.info("Edited announcement message to show bot is offline.")
        except Exception as e:
            logging.error(f"Failed to edit message on shutdown: {e}")

    await chzzk_client.close()
    logging.info("Chzzk API client session closed.")

if __name__ == "__main__":
    bot.run(env_vars['DISCORD_BOT_TOKEN'])
