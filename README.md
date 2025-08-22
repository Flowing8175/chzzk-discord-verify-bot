# 치지직-디스코드 인증 봇 사용 안내

이 프로젝트는 치지직 방송과 디스코드 서버를 연동하여 방송 시청자를 디스코드에서 인증하는 봇입니다. 아래 단계에 따라 봇을 등록하고 필요한 정보를 `.env` 파일에 입력하세요.

## 1. 치지직 개발자 센터에서 봇 등록
1. [developers.chzzk.naver.com](https://developers.chzzk.naver.com)에 접속하여 네이버 계정으로 로그인합니다.
2. 상단의 **내 애플리케이션**에서 **애플리케이션 등록**을 선택합니다.
3. `애플리케이션 ID`를 조건에 맞게 입력합니다.
4. `애플리케이션 이름`을 자유롭게 입력합니다. 이 값은 봇 작동에 사용되지 않습니다.
6. `로그인 리디렉션 URL`에는 `http://localhost:8080`을 입력합니다. (토큰 발급에 사용되며, 틀리게 적을 시 봇이 동작하지 않습니다.)
7. 등록이 완료되면 발급되는 **Client ID**와 **Client Secret**을 기록해 둡니다.
8. 연동할 치지직 방송 채널의 UID를 기록해 둡니다.
   - 채널 페이지 주소의 마지막 부분이 채널의 UID 입니다.
   - 예시: `https://chzzk.naver.com/live/**d72aee7fae014776575a355551a5473b**` → `d72aee7fae014776575a355551a5473b`을 기록.

## 2. 디스코드 봇 등록
1. [Discord 개발자 포털](https://discord.com/developers/applications)에 접속하여 로그인합니다.
2. **New Application**을 클릭해 새 애플리케이션을 만들고 이름을 지정합니다.
3. 좌측 메뉴에서 **Bot**을 선택한 뒤 **Add Bot**을 눌러 봇 계정을 생성합니다.
4. 생성된 봇의 **Token**을 복사해 둡니다. (이 값은 외부에 공개하면 안 됩니다)
   - 필요 시 2차인증 방법을 등록하거나, Discord의 보안상 절차로 인해 토큰 초기화(Reset token)가 요구될 수 있습니다.
   - 발급받은 토큰을 분실 시, Reset token을 통해 재발급받아야 합니다. 이미 발급된 토큰을 재확인할 수 없습니다.
5. 좌측의 **OAuth2 > URL Generator**에서 `bot`을 찾아 선택하고 `Administrator` 권한을 체크한 뒤 생성된 URL로 봇을 서버에 초대합니다.
6. 디스코드 앱에서 **사용자 설정 > 고급 > 개발자 모드**를 켠 후, 서버/채널/역할을 우클릭하여 각각의 ID를 복사합니다.
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

모든 값을 입력한 뒤 콘솔 창(cmd, Powershell, 또는 Unix 셸 등)에서 `python main.py`를 실행하면 봇이 시작됩니다.

