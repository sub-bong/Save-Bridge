#!/bin/bash
# SAFE BRIDGE 응급실 대시보드 실행 스크립트
# Flask 서버 (백엔드 API) + React 앱 (응급실 대시보드 모드)

echo "============================================================"
echo " SAFE BRIDGE 응급실 대시보드 시작"
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
    $PYTHON_CMD -m pip install --upgrade pip > /dev/null 2>&1
    $PYTHON_CMD -m pip install -r backend/requirements.txt > /dev/null 2>&1
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

# React 앱 의존성 확인 및 설치
echo ""
echo "  React 앱 준비 중..."
cd "$REACT_DIR"

if [ ! -d "node_modules" ]; then
    echo "    npm 패키지 설치 중..."
    npm install
    if [ $? -ne 0 ]; then
        echo "    npm 설치 실패"
        exit 1
    fi
fi

# React 앱 백그라운드 실행
echo "React 앱 시작 (포트 5173, 응급실 대시보드 모드)..."
cd "$PROJECT_ROOT/$REACT_DIR"
nohup npm run dev > ../logs/react_app.log 2>&1 &
REACT_PID=$!
echo "    React PID: $REACT_PID"

# React 앱 준비 대기
sleep 5

# React 앱 확인
if curl -s http://localhost:5173 > /dev/null 2>&1 || curl -s http://localhost:5174 > /dev/null 2>&1; then
    REACT_PORT=$(curl -s http://localhost:5173 > /dev/null 2>&1 && echo "5173" || echo "5174")
    echo "    React 앱 정상 실행 중"
    echo "    React URL: http://localhost:$REACT_PORT?mode=er"
else
    echo "     React 앱 시작 확인 중... (로그 확인: tail -f logs/react_app.log)"
    REACT_PORT="5173"
fi

# PID 저장 (종료 시 사용)
cd "$PROJECT_ROOT"
echo "$FLASK_PID" > .flask_pid
echo "$REACT_PID" > .react_pid

# 서비스 정보 출력
echo ""
echo "============================================================"
echo " 응급실 대시보드가 시작되었습니다!"
echo "============================================================"
echo " Flask 서버 (백엔드 API):"
echo "   http://localhost:5001"
echo ""
echo " 응급실 대시보드:"
echo "   http://localhost:$REACT_PORT?mode=er"
echo ""
echo " 로그 파일:"
echo "   - Flask: tail -f logs/flask_server.log"
echo "   - React: tail -f logs/react_app.log"
echo ""
echo " 서비스 종료: Ctrl+C를 누르세요"
echo "============================================================"
echo ""

# 브라우저 자동 열기 (선택사항)
if command -v open &> /dev/null; then
    sleep 2
    open "http://localhost:$REACT_PORT?mode=er" 2>/dev/null
elif command -v xdg-open &> /dev/null; then
    sleep 2
    xdg-open "http://localhost:$REACT_PORT?mode=er" 2>/dev/null
fi

# 사용자 입력 대기 (Ctrl+C로 종료)
trap 'cleanup' INT TERM

cleanup() {
    echo ""
    echo " 서비스 종료 중..."
    
    # 저장된 PID로 종료
    if [ -f .flask_pid ]; then
        kill $(cat .flask_pid) 2>/dev/null
    fi
    if [ -f .react_pid ]; then
        kill $(cat .react_pid) 2>/dev/null
    fi
    
    # 프로세스 강제 종료
    pkill -f "backend/app.py" 2>/dev/null
    pkill -f "app.py" 2>/dev/null
    pkill -f "vite.*5173" 2>/dev/null
    pkill -f "node.*vite" 2>/dev/null
    
    # 임시 파일 정리
    rm -f .flask_pid .react_pid
    
    echo " 모든 서비스가 종료되었습니다."
    exit 0
}

# 포그라운드에서 대기 (Ctrl+C 감지)
wait

