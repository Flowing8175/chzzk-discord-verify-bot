# 치지직-디스코드 인증 봇 사용 안내

이 프로젝트는 치지직 방송과 디스코드 서버를 연동하여 방송 시청자를 디스코드에서 인증하는 봇입니다. 아래 단계에 따라 봇을 등록하고 필요한 정보를 `.env` 파일에 입력하세요.

## 1. 치지직 개발자 센터에서 봇 등록
1. [developers.chzzk.naver.com](https://developers.chzzk.naver.com)에 접속하여 네이버 계정으로 로그인합니다.
2. 상단의 **내 애플리케이션**에서 **애플리케이션 등록**을 선택합니다.
3. 애플리케이션 이름을 입력하고, 서비스 유형은 **게임**으로 설정합니다.
4. "리디렉션 URL"에는 `http://localhost:8080`을 입력합니다. (코드 인증에 사용됨)
5. 등록이 완료되면 발급되는 **Client ID**와 **Client Secret**을 기록해 둡니다.
6. 본인 채널 페이지 주소의 마지막 부분이 `CHZZK_CHANNEL_ID`입니다. 예시: `https://chzzk.naver.com/live/**12345678**` → `12345678`

## 2. 디스코드 봇 등록
1. [Discord 개발자 포털](https://discord.com/developers/applications)에 접속하여 로그인합니다.
2. **New Application**을 클릭해 새 애플리케이션을 만들고 이름을 지정합니다.
3. 좌측 메뉴에서 **Bot**을 선택한 뒤 **Add Bot**을 눌러 봇 계정을 생성합니다.
4. 생성된 봇의 **Token**을 복사해 둡니다. (이 값은 외부에 공개하면 안 됩니다)
5. 같은 화면에서 **SERVER MEMBERS INTENT**와 **MESSAGE CONTENT INTENT**를 활성화합니다.
6. 좌측의 **OAuth2 > URL Generator**에서 `bot` 범위를 선택하고 필요한 권한을 체크한 뒤 생성된 URL로 봇을 서버에 초대합니다.
7. 디스코드 앱에서 **사용자 설정 > 고급 > 개발자 모드**를 켠 후, 서버/채널/역할을 우클릭하여 각각의 ID를 복사합니다.
   - 서버 ID → `DISCORD_GUILD_ID`
   - 인증 채널 ID → `DISCORD_AUTH_CHANNEL_ID`
   - 인증 역할 ID → `DISCORD_AUTH_ROLE_ID`

## 3. `.env` 파일에 환경 변수 추가
프로젝트 루트에 `.env` 파일을 만들고 아래와 같이 값을 채워 넣습니다.

```env
DISCORD_TOKEN=디스코드 봇 토큰
DISCORD_GUILD_ID=디스코드 서버 ID
DISCORD_AUTH_CHANNEL_ID=인증 채널 ID
DISCORD_AUTH_ROLE_ID=인증 완료 역할 ID
CHZZK_CHANNEL_ID=치지직 채널 ID
CHZZK_CLIENT_ID=치지직 클라이언트 ID
CHZZK_CLIENT_SECRET=치지직 클라이언트 Secret
NID_AUT=네이버 로그인 쿠키 (선택)
NID_SES=네이버 로그인 쿠키 (선택)
```

모든 값을 입력한 뒤 `python main.py`를 실행하면 봇이 시작됩니다.

