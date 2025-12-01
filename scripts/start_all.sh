#!/bin/bash
# SAFE BRIDGE React 프로젝트 통합 시작 스크립트
# Flask 서버 (백엔드 API) + React 앱 (프론트엔드) + ngrok (선택사항)

echo "============================================================"
echo " SAFE BRIDGE React 프로젝트 시작"
echo "============================================================"

# 현재 디렉토리 저장 (프로젝트 루트로 이동)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

# logs 디렉토리 생성
mkdir -p logs

# 기존 프로세스 정리
echo " 기존 프로세스 정리 중..."
pkill -f "backend/app.py" 2>/dev/null
pkill -f "app.py" 2>/dev/null
pkill -f "ngrok.*5001" 2>/dev/null
pkill -f "vite.*5173" 2>/dev/null
pkill -f "node.*vite" 2>/dev/null
sleep 2

# Python 가상환경 확인 및 생성
PYTHON_CMD="python3"
if [ -d "venv" ]; then
    echo "🐍 Python 가상환경 활성화..."
    source venv/bin/activate
    PYTHON_CMD="python3"
    echo " 필수 패키지 확인 중..."
    $PYTHON_CMD -c "import flask" 2>/dev/null || {
        echo "    패키지 설치 중..."
        pip install --upgrade pip > /dev/null 2>&1
        pip install -r backend/requirements.txt > /dev/null 2>&1
    }
elif [ -n "$CONDA_DEFAULT_ENV" ]; then
    echo "🐍 Conda 환경 사용 중: $CONDA_DEFAULT_ENV"
    # Conda 환경의 Python 경로 사용 (conda activate 후 which python 사용)
    if [ -n "$CONDA_PREFIX" ]; then
        PYTHON_CMD="$CONDA_PREFIX/bin/python"
    elif command -v conda &> /dev/null; then
        PYTHON_CMD="$(conda run -n $CONDA_DEFAULT_ENV which python 2>/dev/null || which python3)"
    else
        PYTHON_CMD="$(which python3)"
    fi
    echo "    Python 경로: $PYTHON_CMD"
    echo " 필수 패키지 확인 중..."
    $PYTHON_CMD -c "import flask" 2>/dev/null || {
        echo "    패키지 설치 중..."
        $PYTHON_CMD -m pip install --upgrade pip > /dev/null 2>&1
        $PYTHON_CMD -m pip install -r backend/requirements.txt > /dev/null 2>&1
    }
else
    echo "🐍 Python 가상환경 생성 중..."
    python3 -m venv venv
    source venv/bin/activate
    PYTHON_CMD="python3"
    echo " 필수 패키지 설치 중..."
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r backend/requirements.txt > /dev/null 2>&1
    echo " 가상환경 준비 완료"
fi

# Flask 서버 백그라운드 실행
echo ""
echo " Flask 서버 시작 (포트 5001)..."
if [ ! -f "backend/app.py" ]; then
    echo "    backend/app.py 파일을 찾을 수 없습니다."
    exit 1
fi

# Flask 및 필수 패키지 설치 확인
$PYTHON_CMD -c "import flask, flask_cors, flask_socketio" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "    Flask 및 필수 패키지 설치 중..."
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r backend/requirements.txt > /dev/null 2>&1
fi

cd backend
# Python의 출력 버퍼링 비활성화 (-u 옵션) 및 로그 파일에 즉시 기록
nohup $PYTHON_CMD -u app.py > ../logs/flask_server.log 2>&1 &
cd ..
FLASK_PID=$!
echo "    Flask PID: $FLASK_PID"
echo "    Python 경로: $PYTHON_CMD"

# Flask 서버 준비 대기 (eventlet/gevent는 시작 시간이 더 걸릴 수 있음)
echo "    서버 시작 대기 중..."
sleep 5

# Flask 서버 확인 (여러 번 시도)
MAX_RETRIES=5
RETRY_COUNT=0
SERVER_STARTED=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://localhost:5001 > /dev/null 2>&1; then
        echo "    Flask 서버 정상 실행 중"
        echo "    API URL: http://localhost:5001"
        SERVER_STARTED=1
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo "    서버 시작 대기 중... ($RETRY_COUNT/$MAX_RETRIES)"
            sleep 2
        fi
    fi
done

if [ $SERVER_STARTED -eq 0 ]; then
    echo "    Flask 서버 시작 실패"
    echo "    로그 확인: tail -f logs/flask_server.log"
    echo "    최근 로그:"
    tail -20 logs/flask_server.log 2>/dev/null || echo "    (로그 파일이 비어있습니다)"
    exit 1
fi

# ngrok 자동 실행 (Twilio 콜백용)
echo ""
echo " ngrok 터널 자동 시작 (Tw1ilio 콜백용)..."
NGROK_PATH=""
if [ -f "./ngrok" ]; then
    NGROK_PATH="./ngrok"
elif [ -f "$HOME/Downloads/ngrok" ]; then
    NGROK_PATH="$HOME/Downloads/ngrok"
elif [ -f "/Users/sondongbin/Downloads/ngrok" ]; then
    NGROK_PATH="/Users/sondongbin/Downloads/ngrok"
elif command -v ngrok &> /dev/null; then
    NGROK_PATH="ngrok"
fi

if [ -n "$NGROK_PATH" ]; then
    echo "    ngrok 경로: $NGROK_PATH"
    chmod +x "$NGROK_PATH" 2>/dev/null
    nohup "$NGROK_PATH" http 5001 --log=stdout > logs/ngrok.log 2>&1 &
    NGROK_PID=$!
    echo "    ngrok PID: $NGROK_PID"
    
    sleep 5
    echo " ngrok URL 확인 중..."
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data.get('tunnels') else '')" 2>/dev/null)
    
    if [ -z "$NGROK_URL" ]; then
        echo "     ngrok URL을 가져올 수 없습니다"
        echo "    수동으로 확인: http://localhost:4040"
        NGROK_URL="(확인 필요)"
    else
        echo "    ngrok URL: $NGROK_URL"
        echo "$NGROK_URL" > logs/.ngrok_url
        echo "    URL 저장됨: logs/.ngrok_url"

        if [ -f "scripts/update_twilio_webhook.py" ]; then
            echo "    Twilio 웹훅 업데이트 시도 중..."
            if python3 scripts/update_twilio_webhook.py "$NGROK_URL"; then
                echo "    Twilio VoiceUrl -> ${NGROK_URL}/twilio/gather"
                echo "    Twilio StatusCallback -> ${NGROK_URL}/twilio/status"
            else
                echo "    Twilio 웹훅 업데이트 실패 (환경변수 확인 필요)"
            fi
        fi
    fi
else
    echo "     ngrok 실행 파일을 찾지 못했습니다. (자동 건너뜀)"
    echo "    ngrok 다운로드: https://ngrok.com/download"
    NGROK_URL="(미사용)"
    NGROK_PID=""
fi

# React 앱 디렉토리 확인
REACT_DIR="frontend"
if [ ! -d "$REACT_DIR" ]; then
    echo ""
    echo "    React 앱 디렉토리를 찾을 수 없습니다: $REACT_DIR"
    exit 1
fi

# Node.js 확인
if ! command -v node &> /dev/null; then
    echo ""
    echo "    Node.js가 설치되어 있지 않습니다."
    echo "    Node.js를 설치해주세요: https://nodejs.org/"
    exit 1
fi

# mkcert 설치 확인 및 SSL 인증서 생성 (HTTPS용)
echo ""
echo " mkcert SSL 인증서 확인 중..."
if command -v mkcert &> /dev/null; then
    CERT_DIR="$PROJECT_ROOT/$REACT_DIR"
    CERT_KEY="$CERT_DIR/localhost+3-key.pem"
    CERT_FILE="$CERT_DIR/localhost+3.pem"
    
    # 인증서 파일이 없으면 생성
    if [ ! -f "$CERT_KEY" ] || [ ! -f "$CERT_FILE" ]; then
        echo "    SSL 인증서 생성 중..."
        cd "$CERT_DIR"
        
        # 로컬 CA 설치 (한 번만 필요, 에러 무시)
        mkcert -install 2>/dev/null || echo "    CA 인증서는 이미 설치되어 있거나 수동 설치가 필요합니다."
        
        # 인증서 생성 (localhost, 127.0.0.1, 로컬 IP, IPv6)
        LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "")
        if [ -n "$LOCAL_IP" ]; then
            mkcert localhost 127.0.0.1 "$LOCAL_IP" ::1 > /dev/null 2>&1
        else
            mkcert localhost 127.0.0.1 ::1 > /dev/null 2>&1
        fi
        
        if [ -f "$CERT_KEY" ] && [ -f "$CERT_FILE" ]; then
            echo "    ✅ SSL 인증서 생성 완료"
            echo "    인증서 파일: $CERT_FILE"
        else
            echo "    ⚠️  SSL 인증서 생성 실패 (HTTPS 미사용, HTTP로 실행)"
        fi
    else
        echo "    ✅ SSL 인증서 이미 존재"
    fi
    cd "$PROJECT_ROOT"
else
    echo "    ⚠️  mkcert가 설치되어 있지 않습니다."
    echo "    설치 방법: brew install mkcert"
    echo "    (HTTPS 없이 HTTP로 실행됩니다)"
fi

# React 앱 의존성 확인 및 설치
echo ""
echo "  React 앱 준비 중..."

set -a
source "$PROJECT_ROOT/.env" 2>/dev/null || true
set +a
cd "$REACT_DIR"

if [ ! -d "node_modules" ]; then
    echo "    npm 패키지 설치 중..."
    npm install
    if [ $? -ne 0 ]; then
        echo "    npm 설치 실패"
        exit 1
    fi
fi

# React 앱 백그라운드 실행 (모바일 카메라 접근을 위한 환경 변수 설정)
echo "React 앱 시작 (포트 5173)..."
cd "$PROJECT_ROOT/$REACT_DIR"

# Mac 호스트명 확인 (.local 도메인용)
MAC_HOSTNAME=$(hostname 2>/dev/null || scutil --get ComputerName 2>/dev/null || echo "MacBook-Pro.local")
MAC_HOSTNAME_LOCAL="${MAC_HOSTNAME%.local}.local"

# 모바일 카메라 접근을 위한 환경 변수 설정
# Vite는 host, port를 config에서 설정하므로 환경 변수는 참고용
export HOST=0.0.0.0
export PORT=5173
export VITE_WDS_SOCKET_HOST="$MAC_HOSTNAME_LOCAL"

# React 앱 실행 (환경 변수와 함께)
nohup npm run dev > ../logs/react_app.log 2>&1 &
REACT_PID=$!
echo "    React PID: $REACT_PID"
echo "    모바일 접속 URL: http://$MAC_HOSTNAME_LOCAL:5173"

# React 앱 준비 대기
sleep 5

# React 앱 확인 (HTTPS 우선, 없으면 HTTP)
REACT_PORT="5173"
REACT_PROTOCOL="http"
if curl -s -k https://localhost:5173 > /dev/null 2>&1; then
    REACT_PROTOCOL="https"
    echo "    React 앱 정상 실행 중 (HTTPS)"
    echo "    React URL: https://localhost:$REACT_PORT"
elif curl -s http://localhost:5173 > /dev/null 2>&1 || curl -s http://localhost:5174 > /dev/null 2>&1; then
    REACT_PORT=$(curl -s http://localhost:5173 > /dev/null 2>&1 && echo "5173" || echo "5174")
    echo "    React 앱 정상 실행 중 (HTTP)"
    echo "    React URL: http://localhost:$REACT_PORT"
else
    echo "     React 앱 시작 확인 중... (로그 확인: tail -f logs/react_app.log)"
fi

# PID 저장 (종료 시 사용)
cd "$PROJECT_ROOT"
echo "$FLASK_PID" > .flask_pid
if [ -n "$NGROK_PID" ]; then
    echo "$NGROK_PID" > .ngrok_pid
fi
echo "$REACT_PID" > .react_pid

# 서비스 정보 출력
echo ""
echo "============================================================"
echo " 모든 서비스가 시작되었습니다!"
echo "============================================================"
echo " Flask 서버 (백엔드 API):"
echo "   http://localhost:5001"
echo "   - /api/geo/coord2address"
echo "   - /api/geo/coord2region"
echo "   - /api/geo/address2coord"
echo ""
echo " React 앱 (프론트엔드):"
if [ "$REACT_PROTOCOL" = "https" ]; then
    LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "10.50.1.62")
    MAC_HOSTNAME_LOCAL=$(hostname 2>/dev/null || echo "MacBook-Pro.local")
    echo "   https://localhost:$REACT_PORT (로컬)"
    echo "   https://$LOCAL_IP:$REACT_PORT (네트워크 IP)"
    echo "   http://$MAC_HOSTNAME_LOCAL:$REACT_PORT (모바일 카메라 접근용 .local 도메인)"
else
    MAC_HOSTNAME_LOCAL=$(hostname 2>/dev/null || echo "MacBook-Pro.local")
    echo "   http://localhost:$REACT_PORT"
    echo "   http://$MAC_HOSTNAME_LOCAL:$REACT_PORT (모바일 카메라 접근용 .local 도메인)"
fi
echo ""
if [ "$NGROK_URL" != "(미사용)" ]; then
    echo " ngrok 터널 (Twilio 콜백용):"
    echo "   $NGROK_URL"
    echo "   대시보드: http://localhost:4040"
    echo ""
fi
echo " 로그 파일:"
echo "   - Flask: tail -f flask_server.log"
echo "   - React: tail -f react_app.log"
if [ "$NGROK_URL" != "(미사용)" ]; then
    echo "   - ngrok: tail -f ngrok.log"
fi
echo ""
echo " 서비스 종료: Ctrl+C를 누르세요"
echo "============================================================"
echo ""

# 사용자 입력 대기 (Ctrl+C로 종료)
trap 'cleanup' INT TERM

cleanup() {
    echo ""
    echo " 서비스 종료 중..."
    
    # 저장된 PID로 종료
    if [ -f logs/.flask_pid ]; then
        kill $(cat logs/.flask_pid) 2>/dev/null
    fi
    if [ -f logs/.ngrok_pid ]; then
        kill $(cat logs/.ngrok_pid) 2>/dev/null
    fi
    if [ -f logs/.react_pid ]; then
        kill $(cat logs/.react_pid) 2>/dev/null
    fi
    
    # 프로세스 강제 종료
    pkill -f "backend/app.py" 2>/dev/null
    pkill -f "app.py" 2>/dev/null
    pkill -f "ngrok.*5001" 2>/dev/null
    pkill -f "vite.*5173" 2>/dev/null
    pkill -f "node.*vite" 2>/dev/null
    
    # 임시 파일 정리
    rm -f logs/.flask_pid logs/.ngrok_pid logs/.react_pid logs/.ngrok_url
    
    echo " 모든 서비스가 종료되었습니다."
    exit 0
}

# 포그라운드에서 대기 (Ctrl+C 감지)
wait
