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
from urllib.parse import urlparse, parse_qs

TOKEN_CACHE_FILE = ".chzzk_token_cache.json"

class ChzzkAPI:
    def __init__(self, channel_id, nid_aut, nid_ses):
        self.channel_id = channel_id
        self.nid_aut = nid_aut or os.getenv("NID_AUT")
        self.nid_ses = nid_ses or os.getenv("NID_SES")
        self.client_id = os.getenv("CHZZK_CLIENT_ID")
        self.client_secret = os.getenv("CHZZK_CLIENT_SECRET")
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        self.access_token, self.refresh_token, self.token_expiry_time = None, None, None
        self.chat_channel_id, self.websocket, self.on_message_callback = None, None, None
        self.session = requests.Session()
        self.is_listening = False
        self._load_tokens_from_cache()

    def _load_tokens_from_cache(self):
        if os.path.exists(TOKEN_CACHE_FILE):
            try:
                with open(TOKEN_CACHE_FILE, "r") as f:
                    data = json.load(f)
                self.access_token, self.refresh_token = data.get("accessToken"), data.get("refreshToken")
                self.token_expiry_time = datetime.fromisoformat(data.get("expiryTime"))
                print("캐시에서 토큰을 성공적으로 불러왔습니다.")
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                print(f"토큰 캐시 파일 로딩 오류: {e}. 캐시를 무시합니다.")
                self.access_token, self.refresh_token, self.token_expiry_time = None, None, None

    def _save_tokens_to_cache(self):
        if all([self.access_token, self.refresh_token, self.token_expiry_time]):
            data = {"accessToken": self.access_token, "refreshToken": self.refresh_token, "expiryTime": self.token_expiry_time.isoformat()}
            with open(TOKEN_CACHE_FILE, "w") as f:
                json.dump(data, f)
            print("파일에 새로운 토큰을 캐시했습니다.")

    async def initialize(self):
        await self.get_access_token()
        if not self.access_token:
            print("초기 토큰 발급에 실패하여 봇을 시작할 수 없습니다.")
            return
        self.chat_channel_id = await self.get_chat_channel_id()

    async def get_access_token(self, verbose=True):
        if self.access_token and self.token_expiry_time and (self.token_expiry_time - datetime.now() > timedelta(minutes=10)):
            if verbose: print("캐시된 액세스 토큰이 아직 유효합니다.")
            return
        if self.refresh_token:
            if verbose: print("액세스 토큰이 만료되어 Refresh Token으로 재발급을 시도합니다.")
            if await self._refresh_with_refresh_token():
                return

        if verbose: print("유효한 Refresh Token이 없거나 재발급에 실패하여, 전체 인증을 시작합니다.")
        await self._get_token_with_auth_code()

    async def _refresh_with_refresh_token(self):
        print("[*] Refresh Token 사용...")
        token_url = "https://openapi.chzzk.naver.com/auth/v1/token"
        payload = {"grantType": "refresh_token", "refreshToken": self.refresh_token, "clientId": self.client_id, "clientSecret": self.client_secret}
        response = await asyncio.get_event_loop().run_in_executor(None, lambda: self.session.post(token_url, json=payload))
        if response.status_code == 200:
            content = response.json().get("content", {})
            self.access_token, self.refresh_token = content.get("accessToken"), content.get("refreshToken")
            self.token_expiry_time = datetime.now() + timedelta(seconds=content.get("expiresIn", 86400))
            self._save_tokens_to_cache()
            print("Refresh Token을 사용하여 액세스 토큰 재발급 성공.")
            return True
        else:
            print(f"Refresh Token 사용 실패: {response.status_code}, {response.text}")
            self.access_token, self.refresh_token, self.token_expiry_time = None, None, None
            if os.path.exists(TOKEN_CACHE_FILE):
                os.remove(TOKEN_CACHE_FILE)
            return False

    async def _get_token_with_auth_code(self):
        print("[*] 전체 인증 절차 시작 (Selenium 사용)...")
        if not self.client_id or not self.client_secret:
            print("오류: .env 파일에 CHZZK_CLIENT_ID 또는 CHZZK_CLIENT_SECRET이 없습니다."); return

        driver = None
        try:
            options = Options(); options.add_argument("--no-sandbox"); options.add_argument("--disable-dev-shm-usage")
            service = Service()
            driver = webdriver.Chrome(service=service, options=options)

            if self.nid_aut and self.nid_ses:
                driver.get("https://chzzk.naver.com/"); driver.add_cookie({"name": "NID_AUT", "value": self.nid_aut}); driver.add_cookie({"name": "NID_SES", "value": self.nid_ses})
            else:
                print("쿠키 정보가 없습니다. 브라우저에서 로그인해주세요...")
                driver.get("https://nid.naver.com/nidlogin.login")
                WebDriverWait(driver, 120).until(lambda d: "nid.naver.com/nidlogin.login" not in d.current_url)
                print("로그인 성공. 쿠키를 저장합니다.")
                for cookie in driver.get_cookies():
                    if cookie['name'] == 'NID_AUT': set_key(".env", "NID_AUT", cookie['value'])
                    if cookie['name'] == 'NID_SES': set_key(".env", "NID_SES", cookie['value'])
                load_dotenv(override=True); self.nid_aut = os.getenv("NID_AUT"); self.nid_ses = os.getenv("NID_SES")

            print("[1/2] Selenium으로 임시 코드 발급 시도...")
            state = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            req = requests.Request('GET', "https://chzzk.naver.com/account-interlock", params={"clientId": self.client_id, "redirectUri": "http://localhost:8080", "state": state})
            driver.get(req.prepare().url)
            WebDriverWait(driver, 30).until(EC.url_contains("http://localhost:8080"))

            query_params = parse_qs(urlparse(driver.current_url).query)
            auth_code, returned_state = query_params.get("code", [None])[0], query_params.get("state", [None])[0]
            driver.quit()

            if not auth_code or returned_state != state:
                print(f"리디렉션 URL에서 code 또는 state를 찾을 수 없습니다."); return
            print("임시 코드 발급 성공.")

            print("[2/2] 최종 액세스 토큰 발급 요청...")
            token_url = "https://openapi.chzzk.naver.com/auth/v1/token"
            token_payload = {"grantType": "authorization_code", "clientId": self.client_id, "clientSecret": self.client_secret, "code": auth_code, "state": returned_state}
            response = await asyncio.get_event_loop().run_in_executor(None, lambda: self.session.post(token_url, json=token_payload))

            if response.status_code == 200:
                token_data = response.json()
                content = token_data.get("content", {})
                self.access_token, self.refresh_token = content.get("accessToken"), content.get("refreshToken")
                self.token_expiry_time = datetime.now() + timedelta(seconds=content.get("expiresIn", 86400))
                if self.access_token: self._save_tokens_to_cache(); print("최종 액세스 토큰 발급 성공.")
                else: print(f"액세스 토큰 발급 응답 오류: {token_data}")
            else:
                print(f"액세스 토큰 발급 실패: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"전체 토큰 발급 과정 중 예외 발생: {e}")
            if driver: driver.quit()

    async def get_chat_channel_id(self):
        url = f"https://api.chzzk.naver.com/polling/v2/channels/{self.channel_id}/live-status"
        response = await asyncio.get_event_loop().run_in_executor(None, lambda: self.session.get(url, headers=self.headers))
        if response.status_code == 200 and response.json().get("code") == 200:
            return response.json().get("content", {}).get("chatChannelId")
        print("채팅 채널 ID를 가져오는데 실패했습니다."); return None

    def set_on_message_callback(self, callback): self.on_message_callback = callback

    async def listen_chat(self):
        self.is_listening = True
        first_connection = True
        while self.is_listening:
            await self.get_access_token(verbose=first_connection)
            if not self.access_token: print("액세스 토큰이 없어 채팅 서버에 연결할 수 없습니다. 1분 후 재시도합니다."); await asyncio.sleep(60); continue
            if not self.chat_channel_id: self.chat_channel_id = await self.get_chat_channel_id();
            if not self.chat_channel_id: print("채팅 채널 ID가 없어 연결할 수 없습니다. 1분 후 재시도합니다."); await asyncio.sleep(60); continue
            uri = f"wss://kr-ss{random.randint(1, 9)}.chat.naver.com/chat"
            try:
                async with websockets.connect(uri) as websocket:
                    self.websocket = websocket
                    await websocket.send(json.dumps({"ver": "3", "cmd": 100, "svcid": "game", "cid": self.chat_channel_id, "bdy": {"uid": None, "devType": 2001, "accTkn": self.access_token, "auth": "READ"}, "tid": 1}))
                    if first_connection:
                        print("치지직 채팅 서버에 연결되었습니다.")
                        first_connection = False

                    while self.is_listening:
                        message_json = await asyncio.wait_for(websocket.recv(), timeout=60)
                        message = json.loads(message_json)
                        if message.get("cmd") == 10000: await websocket.send(json.dumps({"ver": "2", "cmd": 0}))
                        elif message.get("cmd") == 93101:
                            for msg_item in message.get("bdy", []):
                                profile = json.loads(msg_item.get("profile", "{}"))
                                if self.on_message_callback: await self.on_message_callback(profile, msg_item.get("msg"))
            except asyncio.TimeoutError:
                print("웹소켓 PING 전송...");
                try: await self.websocket.send(json.dumps({"ver": "2", "cmd": 0}))
                except: pass
            except websockets.exceptions.ConnectionClosed as e:
                if e.code != 1000:
                    print(f"웹소켓 연결이 비정상적으로 종료되었습니다: {e}. 5초 후 재연결합니다.")
                    await asyncio.sleep(5)
                # Normal closure (code 1000) will be silent and just loop to reconnect.
            except Exception as e:
                print(f"채팅 리스닝 중 오류: {e}. 5초 후 재연결합니다.")
                await asyncio.sleep(5)

    async def send_chat(self, message):
        await self.get_access_token()
        if not self.access_token or not self.chat_channel_id:
            print("액세스 토큰 또는 채팅 채널 ID가 없어 메시지를 보낼 수 없습니다.")
            return

        url = "https://openapi.chzzk.naver.com/open/v1/chats/send"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        payload = {
            "chatChannelId": self.chat_channel_id,
            "message": message
        }

        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.session.post(url, headers=headers, json=payload)
        )

        if response.status_code == 200:
            print(f"치지직 채팅 전송 성공: {message}")
        else:
            print(f"치지직 채팅 전송 실패: {response.status_code}, {response.text}")

    async def close(self):
        self.is_listening = False
        if self.websocket and self.websocket.open: await self.websocket.close()
        self.session.close(); print("ChzzkAPI 세션을 종료했습니다.")
