# main.py
import asyncio
import os
from dotenv import load_dotenv
from discord_bot import DiscordBot
from chzzk_api import ChzzkAPI
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    load_dotenv()

    # 필수 환경 변수 확인
    required_vars = [
        "DISCORD_TOKEN", "DISCORD_GUILD_ID", "CHZZK_CHANNEL_ID",
        "DISCORD_AUTH_CHANNEL_ID", "DISCORD_AUTH_ROLE_ID"
    ]
    if not all(os.getenv(var) for var in required_vars):
        logging.error("필수 환경변수가 .env 파일에 설정되지 않았습니다. 프로그램을 종료합니다.")
        logging.error(f"누락된 변수: {[var for var in required_vars if not os.getenv(var)]}")
        return

    # 선택적 환경 변수 (쿠키)
    nid_aut = os.getenv("NID_AUT")
    nid_ses = os.getenv("NID_SES")

    chzzk_api = None
    bot = None

    try:
        # 치지직 API 초기화
        chzzk_api = ChzzkAPI(
            channel_id=os.getenv("CHZZK_CHANNEL_ID"),
            nid_aut=nid_aut,
            nid_ses=nid_ses
        )
        await chzzk_api.initialize()

        # 디스코드 봇 초기화
        bot = DiscordBot(
            chzzk_api=chzzk_api,
            auth_channel_id=int(os.getenv("DISCORD_AUTH_CHANNEL_ID")),
            auth_role_id=int(os.getenv("DISCORD_AUTH_ROLE_ID"))
        )

        # 콜백 함수 설정
        chzzk_api.set_on_auth_message_callback(bot.handle_successful_auth)

        # 봇과 API 리스너 동시 실행
        discord_task = asyncio.create_task(bot.start(os.getenv("DISCORD_TOKEN")))
        chzzk_task = asyncio.create_task(chzzk_api.listen_chat())

        await asyncio.gather(discord_task, chzzk_task)

    except Exception as e:
        logging.error(f"메인 루프에서 처리되지 않은 예외 발생: {e}", exc_info=True)
    finally:
        logging.info("프로그램을 종료합니다.")
        if bot and not bot.is_closed():
            await bot.close()
        if chzzk_api:
            await chzzk_api.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("사용자에 의해 프로그램이 중단되었습니다.")
