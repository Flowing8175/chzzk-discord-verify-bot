# chzzk_api.py
import requests
import asyncio
import websockets
import json
import time
import random
import string
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import set_key, load_dotenv
import os

TOKEN_CACHE_FILE = ".chzzk_token_cache.json"

class ChzzkAPI:
    def __init__(self, channel_id, nid_aut, nid_ses):
        load_dotenv()
        self.channel_id = channel_id
        self.nid_aut = nid_aut or os.getenv("NID_AUT")
        self.nid_ses = nid_ses or os.getenv("NID_SES")
        self.client_id = os.getenv("CHZZK_CLIENT_ID")
        self.client_secret = os.getenv("CHZZK_CLIENT_SECRET")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        self.access_token = None
        self.refresh_token = None
        self.token_expiry_time = None

        self.chat_channel_id = None
        self.websocket = None
        self.on_auth_message_callback = None
        self.session = requests.Session()
        self.is_listening = False

        self._load_tokens_from_cache()

    def _load_tokens_from_cache(self):
        if os.path.exists(TOKEN_CACHE_FILE):
            try:
                with open(TOKEN_CACHE_FILE, "r") as f:
                    data = json.load(f)
                    self.access_token = data.get("accessToken")
                    self.refresh_token = data.get("refreshToken")
                    self.token_expiry_time = datetime.fromisoformat(data.get("expiryTime"))
                print("캐시에서 토큰을 성공적으로 불러왔습니다.")
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"토큰 캐시 파일을 불러오는 중 오류 발생: {e}. 캐시를 무시합니다.")
                self.access_token = None
                self.refresh_token = None
                self.token_expiry_time = None

    def _save_tokens_to_cache(self):
        if self.access_token and self.refresh_token and self.token_expiry_time:
            data = {
                "accessToken": self.access_token,
                "refreshToken": self.refresh_token,
                "expiryTime": self.token_expiry_time.isoformat()
            }
            with open(TOKEN_CACHE_FILE, "w") as f:
                json.dump(data, f)
            print("파일에 새로운 토큰을 캐시했습니다.")

    async def initialize(self):
        await self.get_access_token()
        if not self.access_token:
            print("초기 토큰 발급에 실패하여 봇을 시작할 수 없습니다.")
            return

        self.chat_channel_id = await self.get_chat_channel_id()

    async def get_access_token(self):
        """
        유효한 액세스 토큰을 가져옵니다.
        만료된 경우, refresh token으로 재발급을 시도하고, 실패하면 전체 인증을 다시 수행합니다.
        """
        # 1. 현재 토큰이 유효한지 확인 (만료 10분 전)
        if self.access_token and self.token_expiry_time and (self.token_expiry_time - datetime.now() > timedelta(minutes=10)):
            print("캐시된 액세스 토큰이 아직 유효합니다.")
            return

        # 2. Refresh Token으로 재발급 시도
        if self.refresh_token:
            print("액세스 토큰이 만료되어 Refresh Token으로 재발급을 시도합니다.")
            success = await self._refresh_with_refresh_token()
            if success:
                return

        # 3. 전체 인증 절차 수행
        print("유효한 Refresh Token이 없거나 재발급에 실패하여, 전체 인증을 시작합니다.")
        if not self.nid_aut or not self.nid_ses:
            print("NID_AUT 또는 NID_SES 쿠키가 .env 파일에 없습니다.")
            print("브라우저를 열어 쿠키 정보를 가져옵니다...")
            try:
                await self.get_cookies_with_selenium()
            except Exception as e:
                print(f"Selenium 쿠키 획득 실패: {e}")
                return

        await self._get_token_with_auth_code()

    async def _refresh_with_refresh_token(self):
        """Refresh Token을 사용하여 새로운 Access Token을 발급받습니다."""
        print("[*] Refresh Token 사용...")
        token_url = "https://openapi.chzzk.naver.com/auth/v1/token"
        payload = {
            "grantType": "refresh_token",
            "refreshToken": self.refresh_token,
            "clientId": self.client_id,
            "clientSecret": self.client_secret
        }
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: self.session.post(token_url, json=payload))

        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("accessToken")
            self.refresh_token = data.get("refreshToken") # 새 refresh token으로 업데이트
            expires_in = data.get("expiresIn", 86400)
            self.token_expiry_time = datetime.now() + timedelta(seconds=expires_in)
            self._save_tokens_to_cache()
            print("Refresh Token을 사용하여 액세스 토큰 재발급 성공.")
            return True
        else:
            print(f"Refresh Token 사용 실패: {response.status_code}, {response.text}")
            # 실패 시 기존 토큰 정보 모두 삭제
            self.access_token = None
            self.refresh_token = None
            self.token_expiry_time = None
            if os.path.exists(TOKEN_CACHE_FILE):
                os.remove(TOKEN_CACHE_FILE)
            return False

    async def _get_token_with_auth_code(self):
        """공식 문서에 명시된 2단계 인증 절차를 통해 액세스 토큰을 발급받습니다."""
        print("[*] 전체 인증 절차 시작...")
        if not self.client_id or not self.client_secret:
            print("오류: .env 파일에 CHZZK_CLIENT_ID 또는 CHZZK_CLIENT_SECRET이 없습니다.")
            return

        loop = asyncio.get_event_loop()
        cookies = {"NID_AUT": self.nid_aut, "NID_SES": self.nid_ses}

        # 1단계: 임시 코드(code) 발급받기
        try:
            print("[1/2] 임시 코드 발급 요청...")
            state = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            code_url = "https://chzzk.naver.com/account-interlock"
            params = {"clientId": self.client_id, "redirectUri": "http://localhost:8080", "state": state}
            code_response = await loop.run_in_executor(None, lambda: self.session.get(code_url, params=params, cookies=cookies, headers=self.headers))

            if code_response.status_code != 200:
                print(f"임시 코드 발급 실패: {code_response.status_code}, {code_response.text}")
                return

            code_data = code_response.json()
            auth_code = code_data.get("code")
            if not auth_code or code_data.get("state") != state:
                print(f"임시 코드 발급 응답 오류: {code_data}")
                return
            print("임시 코드 발급 성공.")

            # 2단계: 최종 토큰(accessToken) 발급받기
            print("[2/2] 최종 액세스 토큰 발급 요청...")
            token_url = "https://openapi.chzzk.naver.com/auth/v1/token"
            token_payload = {"grantType": "authorization_code", "clientId": self.client_id, "clientSecret": self.client_secret, "code": auth_code, "state": state}
            token_response = await loop.run_in_executor(None, lambda: self.session.post(token_url, json=token_payload))

            if token_response.status_code != 200:
                print(f"액세스 토큰 발급 실패: {token_response.status_code}, {token_response.text}")
                return

            token_data = token_response.json()
            self.access_token = token_data.get("accessToken")
            self.refresh_token = token_data.get("refreshToken")
            expires_in = token_data.get("expiresIn", 86400)
            self.token_expiry_time = datetime.now() + timedelta(seconds=expires_in)

            if self.access_token:
                self._save_tokens_to_cache()
                print("최종 액세스 토큰 발급 성공.")
            else:
                print(f"액세스 토큰 발급 응답 오류: {token_data}")

        except Exception as e:
            print(f"토큰 발급 과정 중 예외 발생: {e}")

    async def get_cookies_with_selenium(self):
        # ... (이전과 동일, 생략)
        pass

    # ... (get_chat_channel_id, listen_chat, send_chat, close 등 나머지 메소드, 이전과 거의 동일)
    async def get_chat_channel_id(self):
        url = f"https://api.chzzk.naver.com/polling/v2/channels/{self.channel_id}/live-status"
        response = await asyncio.get_event_loop().run_in_executor(None, lambda: self.session.get(url, headers=self.headers))
        if response.status_code == 200 and response.json().get("code") == 200:
            return response.json().get("content", {}).get("chatChannelId")
        print("채팅 채널 ID를 가져오는데 실패했습니다.")
        return None

    def set_on_auth_message_callback(self, callback):
        self.on_auth_message_callback = callback

    async def listen_chat(self):
        self.is_listening = True
        while self.is_listening:
            await self.get_access_token()
            if not self.access_token:
                print("액세스 토큰이 없어 채팅 서버에 연결할 수 없습니다. 1분 후 재시도합니다.")
                await asyncio.sleep(60)
                continue
            if not self.chat_channel_id:
                self.chat_channel_id = await self.get_chat_channel_id()
                if not self.chat_channel_id:
                    print("채팅 채널 ID가 없어 연결할 수 없습니다. 1분 후 재시도합니다.")
                    await asyncio.sleep(60)
                    continue

            uri = f"wss://kr-ss{random.randint(1, 9)}.chat.naver.com/chat"
            try:
                async with websockets.connect(uri) as websocket:
                    self.websocket = websocket
                    await websocket.send(json.dumps({"ver": "3", "cmd": 100, "svcid": "game", "cid": self.chat_channel_id, "bdy": {"uid": None, "devType": 2001, "accTkn": self.access_token, "auth": "READ"}, "tid": 1}))
                    print("치지직 채팅 서버에 연결되었습니다.")
                    while self.is_listening:
                        message_json = await asyncio.wait_for(websocket.recv(), timeout=60)
                        message = json.loads(message_json)
                        if message.get("cmd") == 10000:
                            await websocket.send(json.dumps({"ver": "2", "cmd": 0}))
                        elif message.get("cmd") == 93101:
                            for msg_item in message.get("bdy", []):
                                profile = json.loads(msg_item.get("profile", "{}"))
                                if self.on_auth_message_callback:
                                    await self.on_auth_message_callback(profile.get("nickname"), msg_item.get("msg"))
            except asyncio.TimeoutError:
                print("웹소켓 PING 전송...")
                try:
                    await self.websocket.send(json.dumps({"ver": "2", "cmd": 0}))
                except websockets.exceptions.ConnectionClosed: pass
            except Exception as e:
                print(f"채팅 리스닝 중 오류: {e}. 5초 후 재연결합니다.")
                await asyncio.sleep(5)

    async def send_chat(self, message):
        await self.get_access_token()
        if not self.access_token or not self.chat_channel_id:
            print("액세스 토큰 또는 채팅 채널 ID가 없어 메시지를 보낼 수 없습니다.")
            return

        url = f"https://api.chzzk.naver.com/services/v2/channels/{self.channel_id}/chats"
        headers = {**self.headers, "Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}
        cookies = {"NID_AUT": self.nid_aut, "NID_SES": self.nid_ses}
        payload = {"extras": "{}", "content": message}
        response = await asyncio.get_event_loop().run_in_executor(None, lambda: self.session.post(url, headers=headers, cookies=cookies, json=payload))
        if response.status_code == 200:
            print(f"치지직 채팅 전송 성공: {message}")
        else:
            print(f"치지직 채팅 전송 실패: {response.status_code}, {response.text}")

    async def close(self):
        self.is_listening = False
        if self.websocket and self.websocket.open:
            await self.websocket.close()
        self.session.close()
        print("ChzzkAPI 세션을 종료했습니다.")
