# discord_bot.py
import discord
import random
import asyncio
import os

class VerificationView(discord.ui.View):
    def __init__(self, bot, *args, **kwargs):
        # timeout=None으로 설정하여 View가 영구적으로 활성화되도록 함
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="인증하기", style=discord.ButtonStyle.primary, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = interaction.user

        # 이미 인증된 사용자인지 확인
        auth_role_id = int(os.getenv("DISCORD_AUTH_ROLE_ID"))
        auth_role = interaction.guild.get_role(auth_role_id)
        if auth_role and auth_role in user.roles:
            await interaction.response.send_message("이미 인증을 완료하셨습니다.", ephemeral=True)
            return

        # 인증 절차 진행 중인지 확인
        if user.id in self.bot.verifying_users:
            await interaction.response.send_message("이미 인증 절차를 진행 중입니다. 전송된 코드를 확인해주세요.", ephemeral=True)
            return

        auth_code = str(random.randint(100000, 999999))
        self.bot.verifying_users[user.id] = {"code": auth_code}

        print(f"인증 코드 생성: {user.name} ({user.id}) - {auth_code}")

        try:
            await interaction.response.send_message(
                f"**방송 채팅에 `{auth_code}`를 입력해주세요!**\n\n"
                "**주의:** 코드를 다른 사람에게 노출하지 마세요. 3분 내에 입력해야 합니다.",
                ephemeral=True
            )
        except discord.errors.InteractionResponded:
             await interaction.followup.send(
                f"**방송 채팅에 `{auth_code}`를 입력해주세요!**\n\n"
                "**주의:** 코드를 다른 사람에게 노출하지 마세요. 3분 내에 입력해야 합니다.",
                ephemeral=True
            )


        # 3분 후 인증 코드 삭제
        await asyncio.sleep(180)

        if user.id in self.bot.verifying_users and self.bot.verifying_users[user.id]["code"] == auth_code:
            del self.bot.verifying_users[user.id]
            print(f"인증 시간 초과: {user.name} ({user.id})")
            try:
                # ephemeral 메시지는 수정/삭제가 제한적이므로, 후속 메시지 전송
                await interaction.followup.send("인증 시간이 초과되었습니다. '인증하기' 버튼을 다시 눌러주세요.", ephemeral=True)
            except discord.errors.NotFound:
                # 사용자가 상호작용을 닫았을 수 있음
                pass


class DiscordBot(discord.Client):
    def __init__(self, chzzk_api, auth_channel_id, auth_role_id):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(intents=intents)

        self.chzzk_api = chzzk_api
        self.auth_channel_id = auth_channel_id
        self.auth_role_id = auth_role_id
        self.verifying_users = {}  # {discord_user_id: {"code": "123456"}}
        self.announcement_message_id = None
        # View를 인스턴스 변수로 저장하고, custom_id를 지정하여 on_ready에서 한 번만 등록
        self.persistent_view = VerificationView(self)


    async def on_ready(self):
        print(f'{self.user} (ID: {self.user.id})가 성공적으로 로그인했습니다.')
        print('------')

        # View를 봇에 추가. 봇이 재시작되어도 버튼이 동작하도록 함.
        self.add_view(self.persistent_view)

        await self.send_announcement()

    async def send_announcement(self, offline=False):
        channel = self.get_channel(self.auth_channel_id)
        if not channel:
            print(f"오류: 인증 채널을 찾을 수 없습니다 (ID: {self.auth_channel_id})")
            return

        embed = discord.Embed(
            title="치지직-디스코드 연동 인증",
            description="치지직 스트리머 채널과 연동하여 인증된 사용자 역할을 받아보세요!",
            color=discord.Color.blue()
        )

        if offline:
            embed.description = "현재 봇이 오프라인 상태입니다. 인증을 진행할 수 없습니다.\n잠시 후 다시 시도해주세요."
            embed.color = discord.Color.red()
            view = None
        else:
            embed.add_field(name="인증 방법", value="1. 아래 '인증하기' 버튼을 클릭하세요.\n2. 봇이 보내주는 6자리 인증 코드를 확인합니다.\n3. **인증하려는 치지직 계정으로** 방송 채팅창에 해당 인증 코드를 입력해주세요.", inline=False)
            embed.set_footer(text="봇이 온라인 상태일 때만 인증이 가능합니다.")
            view = self.persistent_view

        message = await self.get_announcement_message(channel)

        if message:
            try:
                await message.edit(embed=embed, view=view)
                print("기존 공지 메시지를 수정했습니다.")
            except Exception as e:
                print(f"공지 메시지 수정 중 오류 발생: {e}")
                self.announcement_message_id = None # 메시지 ID가 유효하지 않을 수 있으므로 초기화
                await self.create_new_announcement(channel, embed, view)
        else:
            await self.create_new_announcement(channel, embed, view)

    async def create_new_announcement(self, channel, embed, view):
        try:
            message = await channel.send(embed=embed, view=view)
            self.announcement_message_id = message.id
            with open("announcement_message_id.txt", "w") as f:
                f.write(str(message.id))
            print("새로운 공지 메시지를 전송하고 ID를 저장했습니다.")
        except discord.Forbidden:
            print(f"오류: '{channel.name}' 채널에 메시지를 보낼 권한이 없습니다.")
        except Exception as e:
            print(f"새 공지 메시지 생성 중 오류 발생: {e}")

    async def get_announcement_message(self, channel):
        if not self.announcement_message_id:
            try:
                with open("announcement_message_id.txt", "r") as f:
                    self.announcement_message_id = int(f.read().strip())
            except FileNotFoundError:
                return None

        try:
            return await channel.fetch_message(self.announcement_message_id)
        except discord.NotFound:
            print("저장된 ID의 공지 메시지를 찾을 수 없습니다. 새로 생성합니다.")
            return None
        except discord.Forbidden:
            print("공지 메시지를 가져올 권한이 없습니다.")
            return None

    async def handle_successful_auth(self, chzzk_nickname, auth_code):
        print(f"인증 시도 감지: 닉네임 '{chzzk_nickname}', 코드 '{auth_code}'")

        target_user_id = None
        for user_id, data in self.verifying_users.items():
            if data["code"] == auth_code:
                target_user_id = user_id
                break

        if target_user_id:
            guild_id = os.getenv("DISCORD_GUILD_ID")
            if not guild_id:
                print("오류: DISCORD_GUILD_ID가 .env 파일에 설정되지 않았습니다.")
                return

            guild = self.get_guild(int(guild_id))
            if not guild:
                print(f"오류: 서버를 찾을 수 없습니다 (ID: {guild_id})")
                return

            member = guild.get_member(target_user_id)
            role = guild.get_role(self.auth_role_id)

            if member and role:
                try:
                    # 1. 역할 부여
                    await member.add_roles(role)
                    print(f"'{member.display_name}'님에게 '{role.name}' 역할을 부여했습니다.")

                    # 2. 닉네임 변경
                    # 디스코드 닉네임 길이 제한은 32자
                    base_nickname = f"{chzzk_nickname}({member.display_name})"
                    new_nickname = (base_nickname[:31] + '…') if len(base_nickname) > 32 else base_nickname
                    await member.edit(nick=new_nickname)
                    print(f"'{member.display_name}'님의 닉네임을 '{new_nickname}'으로 변경했습니다.")

                    # 3. 치지직 채팅에 인증 완료 메시지 전송
                    await self.chzzk_api.send_chat(f"\"{chzzk_nickname}\"님 디스코드 연동 인증이 완료되었습니다!")

                    # 4. 인증 과정 완료 처리 (verifying_users에서 삭제)
                    del self.verifying_users[target_user_id]
                    print(f"사용자 {member.display_name}의 인증 절차를 완료했습니다.")

                except discord.Forbidden:
                    print(f"오류: 역할 부여 또는 닉네임 변경에 필요한 권한이 없습니다. (대상: {member.display_name})")
                except Exception as e:
                    print(f"인증 처리 중 오류 발생: {e}")
            else:
                if not member:
                    print(f"오류: 멤버를 찾을 수 없습니다 (ID: {target_user_id})")
                if not role:
                    print(f"오류: 역할을 찾을 수 없습니다 (ID: {self.auth_role_id})")
        # else:
            # print(f"'{auth_code}'에 해당하는 진행 중인 인증을 찾을 수 없습니다.")


    async def close(self):
        print("봇 종료 절차를 시작합니다...")
        try:
            channel = self.get_channel(self.auth_channel_id)
            if channel:
                await self.send_announcement(offline=True)
            else:
                print("종료 공지를 보낼 채널을 찾지 못했습니다.")
        except Exception as e:
            print(f"종료 공지 업데이트 중 오류 발생: {e}")

        await super().close()
        print("봇이 성공적으로 종료되었습니다.")
