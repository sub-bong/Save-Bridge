import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',  // ✅ 이 줄 추가 (모든 네트워크 인터페이스에서 접속 허용)
    // HTTPS 설정 (mkcert로 생성한 인증서 사용)
    https: {
      key: fs.readFileSync(path.resolve(__dirname, './localhost+3-key.pem')),
      cert: fs.readFileSync(path.resolve(__dirname, './localhost+3.pem')),
    },
    // ngrok 도메인 및 .local 도메인 허용 (모바일 카메라 접근을 위한 HTTP 우회)
    allowedHosts: [
      '.ngrok-free.app',
      '.ngrok.io',
      'localhost',
      '127.0.0.1',
      '10.50.1.62',
      '.local',  // .local 도메인 허용 (모바일 카메라 접근용)
      'sondongbin-ui-MacBookPro.local',  // Mac 호스트명
    ],
    proxy: {
      // API 요청을 백엔드로 프록시
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        secure: false,
      },
      // Socket.IO 요청도 프록시
      '/socket.io': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        secure: false,
        ws: true,
      },
      // Twilio 콜백도 프록시
      '/twilio': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        secure: false,
      },
      // 이미지 업로드 파일 서빙 프록시
      '/uploads': {
        target: 'http://localhost:5001',
        changeOrigin: true,
        secure: false,
      },
    },
  },
})