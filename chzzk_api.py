# chzzk_api.py
import requests
import asyncio
import websockets
import json
import time
import random
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import set_key, load_dotenv
import os

class ChzzkAPI:
    def __init__(self, channel_id, nid_aut, nid_ses):
        load_dotenv()
        self.channel_id = channel_id
        self.nid_aut = nid_aut or os.getenv("NID_AUT")
        self.nid_ses = nid_ses or os.getenv("NID_SES")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
        }
        self.access_token = None
        self.chat_channel_id = None
        self.websocket = None
        self.on_auth_message_callback = None
        self.last_token_refresh = None
        self.session = requests.Session()
        self.is_listening = False


    async def initialize(self):
        if not self.nid_aut or not self.nid_ses:
            print("NID_AUT 또는 NID_SES 쿠키가 .env 파일에 없습니다.")
            print("브라우저를 열어 쿠키 정보를 가져옵니다...")
            await self.get_cookies_with_selenium()

        await self.refresh_token()
        self.chat_channel_id = await self.get_chat_channel_id()


    async def get_cookies_with_selenium(self):
        try:
            print("웹드라이버를 설정하는 중입니다...")
            options = Options()
            # Docker 또는 CI 환경에서는 headless와 no-sandbox 옵션이 필요할 수 있습니다.
            # options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)

            print("네이버 로그인 페이지로 이동합니다. 2단계 인증을 포함하여 로그인을 완료해주세요.")
            driver.get("https://nid.naver.com/nidlogin.login")

            # 사용자가 로그인할 때까지 대기 (최대 2분)
            print("로그인 완료를 기다리는 중... (최대 2분)")
            wait = WebDriverWait(driver, 120)
            # 로그인 성공 시 chzzk.naver.com으로 이동하거나, 네이버 메인페이지의 로그인된 상태를 확인
            wait.until(EC.url_contains("chzzk.naver.com") or EC.presence_of_element_located((By.ID, "account")))

            print("로그인 성공. 치지직으로 이동하여 쿠키를 가져옵니다.")
            driver.get("https://chzzk.naver.com/")
            await asyncio.sleep(5) # 페이지 로딩 대기

            # 쿠키 가져오기
            cookies = driver.get_cookies()
            found_nid_aut = False
            found_nid_ses = False
            for cookie in cookies:
                if cookie['name'] == 'NID_AUT':
                    self.nid_aut = cookie['value']
                    set_key(".env", "NID_AUT", self.nid_aut)
                    found_nid_aut = True
                if cookie['name'] == 'NID_SES':
                    self.nid_ses = cookie['value']
                    set_key(".env", "NID_SES", self.nid_ses)
                    found_nid_ses = True

            driver.quit()

            if found_nid_aut and found_nid_ses:
                print(".env 파일에 NID_AUT와 NID_SES 쿠키를 성공적으로 저장했습니다.")
                # .env 파일 다시 로드
                load_dotenv(override=True)
                self.nid_aut = os.getenv("NID_AUT")
                self.nid_ses = os.getenv("NID_SES")
            else:
                raise Exception("NID_AUT 또는 NID_SES 쿠키를 찾지 못했습니다. 로그인에 실패했거나 쿠키 이름이 변경되었을 수 있습니다.")

        except Exception as e:
            print(f"Selenium으로 쿠키를 가져오는 중 오류 발생: {e}")
            raise


    async def refresh_token(self):
        """24시간마다 토큰을 재발급합니다."""
        now = datetime.now()
        should_refresh = False
        if self.last_token_refresh is None:
            should_refresh = True
        else:
            if now - self.last_token_refresh > timedelta(hours=23, minutes=50):
                should_refresh = True

        if not should_refresh:
            # print("토큰이 아직 유효합니다.")
            return

        print("치지직 액세스 토큰을 발급 또는 재발급합니다...")
        url = "https://api.chzzk.naver.com/manage/v1/auth/access-token"
        cookies = {"NID_AUT": self.nid_aut, "NID_SES": self.nid_ses}

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: self.session.get(url, cookies=cookies, headers=self.headers))

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 200:
                content = data.get("content", {})
                self.access_token = content.get("accessToken")
                self.last_token_refresh = now
                print("액세스 토큰 발급/재발급 성공.")
            else:
                print(f"API 오류로 토큰 발급 실패: {data.get('message')}")
                self.access_token = None
        else:
            print(f"HTTP 오류로 토큰 발급 실패: {response.status_code}")
            self.access_token = None

    async def get_chat_channel_id(self):
        url = f"https://api.chzzk.naver.com/polling/v2/channels/{self.channel_id}/live-status"

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: self.session.get(url, headers=self.headers))

        if response.status_code == 200:
            data = response.json()
            if data.get("code") == 200:
                chat_channel_id = data.get("content", {}).get("chatChannelId")
                return chat_channel_id
        print("채팅 채널 ID를 가져오는데 실패했습니다.")
        return None

    def set_on_auth_message_callback(self, callback):
        self.on_auth_message_callback = callback

    async def listen_chat(self):
        self.is_listening = True
        while self.is_listening:
            if not self.chat_channel_id:
                print("채팅 채널 ID가 없습니다. 10초 후 재시도합니다.")
                await asyncio.sleep(10)
                self.chat_channel_id = await self.get_chat_channel_id()
                continue

            await self.refresh_token()
            if not self.access_token:
                print("액세스 토큰이 없습니다. 10초 후 재시도합니다.")
                await asyncio.sleep(10)
                continue

            server_id = str(random.randint(1, 9))
            uri = f"wss://kr-ss{server_id}.chat.naver.com/chat"

            try:
                async with websockets.connect(uri) as websocket:
                    self.websocket = websocket
                    await self.websocket.send(json.dumps({
                        "ver": "3",
                        "cmd": 100,
                        "svcid": "game",
                        "cid": self.chat_channel_id,
                        "bdy": {
                            "uid": None,
                            "devType": 2001,
                            "accTkn": self.access_token,
                            "auth": "READ"
                        },
                        "tid": 1
                    }))
                    print("치지직 채팅 서버에 연결되었습니다.")

                    while self.is_listening:
                        message_json = await asyncio.wait_for(self.websocket.recv(), timeout=60)
                        message = json.loads(message_json)

                        if message.get("cmd") == 10000:
                            await self.websocket.send(json.dumps({"ver": "2", "cmd": 0}))

                        if message.get("cmd") == 93101:
                            for msg_item in message.get("bdy", []):
                                profile_json = msg_item.get("profile", "{}")
                                profile = json.loads(profile_json)
                                chzzk_nickname = profile.get("nickname")
                                msg = msg_item.get("msg")

                                if msg and msg.isdigit() and len(msg) == 6 and self.on_auth_message_callback:
                                    await self.on_auth_message_callback(chzzk_nickname, msg)

            except asyncio.TimeoutError:
                print("웹소켓에서 60초 동안 메시지가 없어 PING을 보냅니다.")
                try:
                    await self.websocket.send(json.dumps({"ver": "2", "cmd": 0}))
                except websockets.exceptions.ConnectionClosed:
                    print("PING 전송 중 연결이 끊겼음을 확인했습니다.")
            except websockets.exceptions.ConnectionClosed as e:
                print(f"웹소켓 연결이 끊어졌습니다: {e}. 5초 후 재연결합니다.")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"채팅 리스닝 중 오류 발생: {e}. 5초 후 재연결합니다.")
                await asyncio.sleep(5)

            if self.is_listening:
                print("재연결을 시도합니다.")
                await self.refresh_token()

    async def send_chat(self, message):
        await self.refresh_token()
        if not self.access_token or not self.chat_channel_id:
            print("액세스 토큰 또는 채팅 채널 ID가 없어 메시지를 보낼 수 없습니다.")
            return

        url = f"https://api.chzzk.naver.com/services/v2/channels/{self.channel_id}/chats"

        headers_with_auth = self.headers.copy()
        headers_with_auth["Authorization"] = f"Bearer {self.access_token}"
        cookies = {"NID_AUT": self.nid_aut, "NID_SES": self.nid_ses}

        payload = {
            "extras": "{}",
            "content": message
        }

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: self.session.post(url, headers=headers_with_auth, cookies=cookies, json=payload))

        if response.status_code == 200:
            print(f"치지직 채팅 전송 성공: {message}")
        else:
            print(f"치지직 채팅 전송 실패: {response.status_code}, {response.text}")


    async def close(self):
        self.is_listening = False
        if self.websocket and self.websocket.open:
            await self.websocket.close()
            print("웹소켓 연결을 종료했습니다.")
        self.session.close()
        print("HTTP 세션을 종료했습니다.")
