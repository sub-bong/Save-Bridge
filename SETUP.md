# 응급실 병상 찾기 서비스 - 설치 및 실행 가이드

## 목차
1. [최초 설치](#1-최초-설치-한-번만-실행)
2. [서비스 실행](#2-서비스-실행-매번-실행)
3. [서비스 종료](#3-서비스-종료)
4. [문제 해결](#4-문제-해결)

---

## 1. 최초 설치 (한 번만 실행)

### Step 1: 작업 디렉토리로 이동
```bash
cd /Users/sondongbin/Downloads
```

### Step 4: Conda 환경 확인 및 패키지 설치
```bash
# conda 환경 활성화
conda activate off_hack

# 필수 패키지 설치
conda install flask openai -y

# pip로 추가 패키지 설치 (conda에서 설치 실패 시)
pip install twilio streamlit pandas pydeck geopy requests
```

### Step 4: ngrok 설치 확인
```bash
# ngrok이 Downloads 폴더에 있는지 확인
ls -la ~/Downloads/ngrok

# 실행 권한 부여
chmod +x ~/Downloads/ngrok

# 버전 확인 (정상 작동 확인)
~/Downloads/ngrok version
```

**출력 예시:**
```
ngrok version ..0
```

### Step 4: 시작 스크립트 실행 권한 부여
```bash
chmod +x /Users/sondongbin/Downloads/start_service.sh
```

---

## 2. 서비스 실행 (매번 실행)

### 방법 A: 자동 실행 (권장 )

**단 하나의 명령어로 모든 것 실행:**

```bash
cd /Users/sondongbin/Downloads && bash start_service.sh
```

**끝!** 이 명령어 하나면 다음이 자동으로 실행됩니다:
-- Flask 서버 시작 (localhost:5001)
- ngrok 터널 생성 및 공개 URL 발급
- ngrok URL 자동 감지 및 저장
-- Streamlit 앱 실행 (자동으로 브라우저 열림)
-- Twilio 콜백 URL 자동 설정

**예상 출력:**
```
============================================================
 응급실 병상 찾기 서비스 시작
============================================================
 기존 프로세스 정리 중...
- Flask 서버 시작 (포트 5001)...
- Flask PID: 
- Flask 서버 정상 실행 중
 ngrok 터널 시작...
   - ngrok PID: 7890
 ngrok URL 확인 중...
   - ngrok URL: https://xxxx.ngrok-free.app
    URL 저장됨: .ngrok_url
============================================================
- Streamlit 앱 시작
============================================================
- Flask 서버: http://localhost:5001
 ngrok URL: https://xxxx.ngrok-free.app
 ngrok 대시보드: http://localhost:4040
============================================================

 서비스 종료: Ctrl+C를 누르세요

  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

---

### 방법 B: 수동 실행 (디버깅용)

각 서비스를 개별 터미널에서 실행하려면:

#### 터미널 1:- Flask 서버
```bash
cd /Users/sondongbin/Downloads
conda activate off_hack
python twilio_flask_server.py
```

**유지! (종료하지 마세요)**

#### 터미널 1: ngrok
```bash
cd /Users/sondongbin/Downloads
./ngrok http 00
```

** ngrok URL 복사하기:**
출력에서 `Forwarding` 줄의 URL을 복사하세요:
```
Forwarding    https://xxxx.ngrok-free.app -> http://localhost:5001
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
              이 부분 복사!
```

**유지! (종료하지 마세요)**

#### 터미널 1:- Streamlit 앱
```bash
cd /Users/sondongbin/Downloads
conda activate off_hack
streamlit run message.py
```

#### 터미널 1: ngrok URL 저장 (선택사항)
수동으로 `.ngrok_url` 파일에 저장하면 앱에서 자동 감지됩니다:
```bash
echo "https://xxxx.ngrok-free.app" > /Users/sondongbin/Downloads/.ngrok_url
```

---

## 3. 서비스 종료

### 자동 실행으로 시작한 경우
터미널에서:
```
Ctrl + C
```

**모든 서비스가 자동으로 종료됩니다!**

---

### 수동 실행으로 시작한 경우

각 터미널에서 `Ctrl + C` 누르거나, 한 번에 종료:

```bash
# 모든 관련 프로세스 종료
pkill -f "twilio_flask_server"
pkill -f "ngrok"
pkill -f "streamlit"

# 임시 파일 정리 (선택사항)
cd /Users/sondongbin/Downloads
rm -f .flask_pid .ngrok_pid .ngrok_url flask_server.log ngrok.log
```

---

## 4. 실행 확인

서비스가 정상적으로 실행되었는지 확인:

### 브라우저에서 확인

| 서비스 | URL | 확인 사항 |
|--------|-----|----------|
| **Streamlit 앱** | http://localhost:8501 | 앱 화면이 보이는지 |
| **Flask 서버** | http://localhost:5001 | "- Twilio- Flask Server 실행 중" 표시 |
| **ngrok 대시보드: http://localhost:4040 | 터널 정보 표시 |
| **ngrok 공개 URL** | https://xxxx.ngrok-free.app | ngrok 안내 페이지 |

###- Streamlit 앱에서 확인

**" 시스템 상태 확인"** 펼치기:
```
- OpenAI API:  설정됨
- Twilio API:  설정됨
- Flask 서버:  실행 중 (localhost:5001)
- Streamlit 버전: ..0
- 마이크 입력:  지원됨
```

**"- Twilio 다이얼 입력 설정"** 확인:
```
 ngrok URL 자동 감지됨!
https://xxxx.ngrok-free.app
 콜백 URL: https://xxxx.ngrok-free.app/twilio/gather
```

**모두 이면 정상입니다!** 

---

##  . 문제 해결

### 문제 : "Port 00 is in use"
**원인:**- Flask 서버가 이미 실행 중

**해결:**
```bash
# 포트 사용 중인 프로세스 확인
lsof -i :00

# 프로세스 종료
kill -9 <PID>

# 또는 한 번에
pkill -f "twilio_flask_server"
```

---

### 문제 : "ngrok: command not found"
**원인:** ngrok이 설치되지 않았거나 경로 문제

**해결:**
```bash
# ngrok 위치 확인
ls -la ~/Downloads/ngrok

# 없으면 다시 다운로드
cd /tmp
curl -O https://bin.equinox.io/c/bNyjmQVYc/ngrok-v-stable-darwin-arm.zip
unzip -o ngrok-v-stable-darwin-arm.zip
mv ngrok ~/Downloads/ngrok
chmod +x ~/Downloads/ngrok

# 버전 확인
~/Downloads/ngrok version
```

---

### 문제 : "Flask 서버:  미실행"
**원인:**- Flask가 설치되지 않았거나 서버가 시작되지 않음

**해결:**
```bash
#- Flask 설치 확인
conda list | grep flask

# 없으면 설치
conda install flask -y

#- Flask 서버 수동 실행 (에러 확인)
cd /Users/sondongbin/Downloads
python twilio_flask_server.py
```

---

### 문제 : "OpenAI API:  미설정"
**원인:**- OpenAI 패키지가 설치되지 않음

**해결:**
```bash
#- OpenAI 설치
conda install openai -y

# 설치 확인
python -c "from openai import- OpenAI; print('- OpenAI 설치됨')"
```

---

### 문제 : "ngrok URL이 자동으로 감지되지 않았습니다"
**원인:** ngrok이 시작되지 않았거나 URL 파일이 생성되지 않음

**해결:**
```bash
# ngrok 수동 실행
cd /Users/sondongbin/Downloads
./ngrok http 00 > ngrok.log >& &

# 초 대기
sleep 

# URL 확인
curl -s http://localhost:5001/api/tunnels | python -c "import sys, json; data = json.load(sys.stdin); print(data['tunnels'][0]['public_url'])"

# URL을 파일에 저장
curl -s http://localhost:5001/api/tunnels | python -c "import sys, json; data = json.load(sys.stdin); print(data['tunnels'][0]['public_url'])" > .ngrok_url

#- Streamlit 새로고침
```

---

### 문제 : 모든 프로세스 초기화

모든 것을 정리하고 다시 시작:

```bash
# . 모든 관련 프로세스 종료
pkill -f "twilio_flask_server"
pkill -f "ngrok"
pkill -f "streamlit"

# . 임시 파일 정리
cd /Users/sondongbin/Downloads
rm -f .flask_pid .ngrok_pid .ngrok_url flask_server.log ngrok.log

# . 포트 확인
lsof -i :00
lsof -i :80

# . 다시 시작
bash start_service.sh
```

---

##  서비스 구조도

```
┌─────────────────────────────────────────────────────────┐
│  start_service.sh (통합 시작 스크립트)                    │
└────────┬────────────────────────────────────────────────┘
         │
         ├─►- Flask 서버 (localhost:5001)
         │   └─►- Twilio 콜백 수신 (/twilio/gather)
         │
         ├─► ngrok (터널)
         │   ├─► 공개 URL 생성 (https://xxxx.ngrok-free.app)
         │   └─► .ngrok_url 파일에 저장
         │
         └─►- Streamlit 앱 (localhost:8501)
             ├─► .ngrok_url 자동 읽기
             ├─►- Twilio API 호출
             └─► 사용자 인터페이스
```

---

##  전체 프로세스 (처음부터 끝까지)

###  최초 회 설정
```bash
# 디렉토리 이동
cd /Users/sondongbin/Downloads

# conda 환경 활성화
conda activate off_hack

# 패키지 설치
conda install flask openai -y

# ngrok 실행 권한
chmod +x ~/Downloads/ngrok

# 시작 스크립트 실행 권한
chmod +x start_service.sh
```

###  매번 실행
```bash
cd /Users/sondongbin/Downloads && bash start_service.sh
```

###  종료
```
Ctrl + C
```

**끝!** 

---

##  추가 팁

### ngrok URL 확인하기
```bash
curl -s http://localhost:5001/api/tunnels | python -c "import sys, json; data = json.load(sys.stdin); print(data['tunnels'][0]['public_url'])"
```

###- Flask 로그 확인하기
```bash
tail -f /Users/sondongbin/Downloads/flask_server.log
```

### ngrok 로그 확인하기
```bash
tail -f /Users/sondongbin/Downloads/ngrok.log
```

### 저장된 다이얼 응답 확인
```bash
# 브라우저에서
open http://localhost:5001/responses
```

---

##  빠른 참조

| 작업 | 명령어 |
|------|--------|
| **서비스 시작** | `cd /Users/sondongbin/Downloads && bash start_service.sh` |
| **서비스 종료** | `Ctrl + C` |
| **모든 프로세스 강제 종료** | `pkill -f "twilio_flask_server"; pkill -f "ngrok"; pkill -f "streamlit"` |
| **Flask 서버 확인** | `curl http://localhost:5001` |
| **ngrok URL 확인** | `curl -s http://localhost:5001/api/tunnels \| python -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])"` |
| **포트 사용 확인** | `lsof -i :00` |
| **로그 확인** | `tail -f flask_server.log` 또는 `tail -f ngrok.log` |

---

**이제 서비스를 실행할 준비가 완료되었습니다!** 

