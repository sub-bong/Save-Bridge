#!/bin/bash
# SAFE BRIDGE React 프로젝트 통합 시작 스크립트
# Flask 서버 (백엔드 API) + React 앱 (프론트엔드) + ngrok (선택사항)

echo "============================================================"
echo "🚑 SAFE BRIDGE React 프로젝트 시작"
echo "============================================================"

# 현재 디렉토리 저장 (프로젝트 루트로 이동)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

# logs 디렉토리 생성
mkdir -p logs

# 기존 프로세스 정리
echo "📌 기존 프로세스 정리 중..."
pkill -f "backend/app.py" 2>/dev/null
pkill -f "app.py" 2>/dev/null
pkill -f "ngrok.*5001" 2>/dev/null
pkill -f "vite.*5173" 2>/dev/null
pkill -f "node.*vite" 2>/dev/null
sleep 2

# Python 가상환경 확인 및 생성
if [ -d "venv" ]; then
    echo "🐍 Python 가상환경 활성화..."
    source venv/bin/activate
elif [ -n "$CONDA_DEFAULT_ENV" ]; then
    echo "🐍 Conda 환경 사용 중: $CONDA_DEFAULT_ENV"
else
    echo "🐍 Python 가상환경 생성 중..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📦 필수 패키지 설치 중..."
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r backend/requirements.txt > /dev/null 2>&1
    echo "✅ 가상환경 준비 완료"
fi

# Flask 서버 백그라운드 실행
echo ""
echo "🔧 Flask 서버 시작 (포트 5001)..."
if [ ! -f "backend/app.py" ]; then
    echo "   ❌ backend/app.py 파일을 찾을 수 없습니다."
    exit 1
fi

# flask-cors 설치 확인
python3 -c "import flask_cors" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "   📦 flask-cors 설치 중..."
    pip install flask-cors > /dev/null 2>&1
fi

cd backend
nohup python3 app.py > ../logs/flask_server.log 2>&1 &
cd ..
FLASK_PID=$!
echo "   ✅ Flask PID: $FLASK_PID"

# Flask 서버 준비 대기
sleep 3

# Flask 서버 확인
if curl -s http://localhost:5001 > /dev/null; then
    echo "   ✅ Flask 서버 정상 실행 중"
    echo "   📍 API URL: http://localhost:5001"
else
    echo "   ❌ Flask 서버 시작 실패"
    echo "   💡 로그 확인: tail -f logs/flask_server.log"
    exit 1
fi

# ngrok 자동 실행 (Twilio 콜백용)
echo ""
echo "🌐 ngrok 터널 자동 시작 (Twilio 콜백용)..."
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
    echo "   📍 ngrok 경로: $NGROK_PATH"
    chmod +x "$NGROK_PATH" 2>/dev/null
    nohup "$NGROK_PATH" http 5001 --log=stdout > logs/ngrok.log 2>&1 &
    NGROK_PID=$!
    echo "   ✅ ngrok PID: $NGROK_PID"
    
    sleep 5
    echo "🔍 ngrok URL 확인 중..."
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "import sys, json; data = json.load(sys.stdin); print(data['tunnels'][0]['public_url'] if data.get('tunnels') else '')" 2>/dev/null)
    
    if [ -z "$NGROK_URL" ]; then
        echo "   ⚠️  ngrok URL을 가져올 수 없습니다"
        echo "   💡 수동으로 확인: http://localhost:4040"
        NGROK_URL="(확인 필요)"
    else
        echo "   ✅ ngrok URL: $NGROK_URL"
        echo "$NGROK_URL" > logs/.ngrok_url
        echo "   📝 URL 저장됨: logs/.ngrok_url"
    fi
else
    echo "   ⚠️  ngrok 실행 파일을 찾지 못했습니다. (자동 건너뜀)"
    echo "   💡 ngrok 다운로드: https://ngrok.com/download"
    NGROK_URL="(미사용)"
    NGROK_PID=""
fi

# React 앱 디렉토리 확인
REACT_DIR="frontend"
if [ ! -d "$REACT_DIR" ]; then
    echo ""
    echo "   ❌ React 앱 디렉토리를 찾을 수 없습니다: $REACT_DIR"
    exit 1
fi

# Node.js 확인
if ! command -v node &> /dev/null; then
    echo ""
    echo "   ❌ Node.js가 설치되어 있지 않습니다."
    echo "   💡 Node.js를 설치해주세요: https://nodejs.org/"
    exit 1
fi

# React 앱 의존성 확인 및 설치
echo ""
echo "⚛️  React 앱 준비 중..."
cd "$REACT_DIR"

if [ ! -d "node_modules" ]; then
    echo "   📦 npm 패키지 설치 중..."
    npm install
    if [ $? -ne 0 ]; then
        echo "   ❌ npm 설치 실패"
        exit 1
    fi
fi

# React 앱 백그라운드 실행
echo "🚀 React 앱 시작 (포트 5173)..."
cd "$PROJECT_ROOT/$REACT_DIR"
nohup npm run dev > ../logs/react_app.log 2>&1 &
REACT_PID=$!
echo "   ✅ React PID: $REACT_PID"

# React 앱 준비 대기
sleep 5

# React 앱 확인
if curl -s http://localhost:5173 > /dev/null 2>&1 || curl -s http://localhost:5174 > /dev/null 2>&1; then
    REACT_PORT=$(curl -s http://localhost:5173 > /dev/null 2>&1 && echo "5173" || echo "5174")
    echo "   ✅ React 앱 정상 실행 중"
    echo "   📍 React URL: http://localhost:$REACT_PORT"
else
    echo "   ⚠️  React 앱 시작 확인 중... (로그 확인: tail -f logs/react_app.log)"
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
echo "✅ 모든 서비스가 시작되었습니다!"
echo "============================================================"
echo "📍 Flask 서버 (백엔드 API):"
echo "   http://localhost:5001"
echo "   - /api/geo/coord2address"
echo "   - /api/geo/coord2region"
echo "   - /api/geo/address2coord"
echo ""
echo "📍 React 앱 (프론트엔드):"
echo "   http://localhost:$REACT_PORT"
echo ""
if [ "$NGROK_URL" != "(미사용)" ]; then
    echo "📍 ngrok 터널 (Twilio 콜백용):"
    echo "   $NGROK_URL"
    echo "   대시보드: http://localhost:4040"
    echo ""
fi
echo "📋 로그 파일:"
echo "   - Flask: tail -f flask_server.log"
echo "   - React: tail -f react_app.log"
if [ "$NGROK_URL" != "(미사용)" ]; then
    echo "   - ngrok: tail -f ngrok.log"
fi
echo ""
echo "💡 서비스 종료: Ctrl+C를 누르세요"
echo "============================================================"
echo ""

# 사용자 입력 대기 (Ctrl+C로 종료)
trap 'cleanup' INT TERM

cleanup() {
    echo ""
    echo "🛑 서비스 종료 중..."
    
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
    
    echo "✅ 모든 서비스가 종료되었습니다."
    exit 0
}

# 포그라운드에서 대기 (Ctrl+C 감지)
wait
