import { io, Socket } from "socket.io-client";

const getApiBaseUrl = (): string => {
  try {
    const env = (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env;
    return env?.VITE_API_BASE_URL || "http://localhost:5001";
  } catch {
    return "http://localhost:5001";
  }
};

let socket: Socket | null = null;

export const getSocket = (): Socket => {
  if (!socket) {
    const apiBaseUrl = getApiBaseUrl();
    socket = io(apiBaseUrl, {
      // websocket을 우선적으로 사용하고, 실패 시에만 polling으로 폴백
      transports: ["websocket", "polling"],
      upgrade: true,  // polling에서 websocket으로 업그레이드 허용
      rememberUpgrade: true,  // 이전에 websocket이 성공했다면 다음에도 websocket 사용
      withCredentials: true,
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 10,  // 재연결 시도 횟수 증가
      timeout: 20000,
      forceNew: false,  // 기존 연결 재사용
    });
    
    socket.on("connect", () => {
      console.log("✅ Socket.IO 연결 성공:", socket?.id, "Transport:", socket.io.engine.transport.name);
    });
    
    socket.on("disconnect", (reason) => {
      console.log("❌ Socket.IO 연결 끊김:", reason);
    });
    
    socket.on("connect_error", (error) => {
      console.error("❌ Socket.IO 연결 오류:", error.message);
      // 연결 실패 시 polling으로 폴백
      if (socket && socket.io.engine) {
        console.log("🔄 Polling으로 폴백 시도 중...");
      }
    });
    
    socket.on("reconnect", (attemptNumber) => {
      console.log("🔄 Socket.IO 재연결 성공 (시도 횟수:", attemptNumber, ")");
    });
    
    socket.on("reconnect_attempt", (attemptNumber) => {
      console.log("🔄 Socket.IO 재연결 시도 중... (시도 횟수:", attemptNumber, ")");
    });
    
    socket.on("reconnect_error", (error) => {
      console.error("❌ Socket.IO 재연결 오류:", error);
    });
    
    socket.on("reconnect_failed", () => {
      console.error("❌ Socket.IO 재연결 실패 - 최대 시도 횟수 초과");
    });
  }
  return socket;
};

export const disconnectSocket = () => {
  if (socket) {
    socket.disconnect();
    socket = null;
    console.log("🔌 WebSocket 연결 종료");
  }
};

