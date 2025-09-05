# main.py
import asyncio
import os
from dotenv import load_dotenv
from chzzk_api import ChzzkAPI
from queue_manager import QueueManager
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 전역 인스턴스
chzzk_api = None
queue_manager = QueueManager()

def is_authorized(profile):
    """스트리머 또는 관리자인지 확인"""
    auths = profile.get("privileges", [])
    badge = profile.get("badge", {}).get("imageUrl")
    is_streamer = badge and "streamer" in badge
    return "channel_manager" in auths or "streamer" in auths or is_streamer

async def on_chat_message(profile, message):
    """채팅 메시지 처리"""
    nickname = profile.get("nickname", "알 수 없는 사용자")

    if message == "!시참":
        if queue_manager.add_user(nickname):
            logging.info(f"'{nickname}'님이 시참 대기열에 추가되었습니다.")
            # Optionally, send a confirmation message
            # await chzzk_api.send_chat(f"{nickname}님, 대기열에 추가되었습니다!")
        else:
            logging.info(f"'{nickname}'님은 이미 대기열에 있습니다.")

    elif message.startswith("!pop"):
        if not is_authorized(profile):
            logging.warning(f"권한 없는 사용자 '{nickname}'의 !pop 시도.")
            return

        parts = message.split()
        count = 1
        if len(parts) > 1 and parts[1].isdigit():
            count = int(parts[1])

        if queue_manager.is_empty():
            await chzzk_api.send_chat("시참 인원 없다 하@꼬쉑ㅋ")
            logging.info("대기열이 비어있어 !pop 명령을 처리할 수 없습니다.")
            return

        popped_users = queue_manager.pop_users(count)

        if popped_users:
            announcement = ", ".join(popped_users) + "님 참여 순서입니다!"
            await chzzk_api.send_chat(announcement)
            logging.info(f"{count}명을 뽑았습니다: {', '.join(popped_users)}")

async def main():
    global chzzk_api
    load_dotenv()

    # 필수 환경 변수 확인
    required_vars = ["CHZZK_CHANNEL_ID"]
    if not all(os.getenv(var) for var in required_vars):
        logging.error("필수 환경변수가 .env 파일에 설정되지 않았습니다. 프로그램을 종료합니다.")
        logging.error(f"누락된 변수: {[var for var in required_vars if not os.getenv(var)]}")
        return

    # 선택적 환경 변수 (쿠키)
    nid_aut = os.getenv("NID_AUT")
    nid_ses = os.getenv("NID_SES")

    try:
        # 치지직 API 초기화
        chzzk_api = ChzzkAPI(
            channel_id=os.getenv("CHZZK_CHANNEL_ID"),
            nid_aut=nid_aut,
            nid_ses=nid_ses
        )
        await chzzk_api.initialize()

        # 콜백 함수 설정
        chzzk_api.set_on_message_callback(on_chat_message)

        # chzzk_api 리스너 실행
        logging.info("치지직 큐 봇을 시작합니다.")
        await chzzk_api.listen_chat()

    except Exception as e:
        logging.error(f"메인 루프에서 처리되지 않은 예외 발생: {e}", exc_info=True)
    finally:
        logging.info("프로그램을 종료합니다.")
        if chzzk_api:
            await chzzk_api.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("사용자에 의해 프로그램이 중단되었습니다.")
