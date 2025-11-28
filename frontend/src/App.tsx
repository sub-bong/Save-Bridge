import React, { useState, useEffect } from "react";
import { SafeBridgeApp } from "./components/SafeBridgeApp";
import { ERDashboard } from "./components/ERDashboard";
import { LoginPage } from "./components/LoginPage";
import { getCurrentUser } from "./services/api";

type AppMode = "paramedic" | "er";

const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [appMode, setAppMode] = useState<AppMode>("paramedic");

  useEffect(() => {
    // URL 파라미터로 모드 확인
    const urlParams = new URLSearchParams(window.location.search);
    const mode = urlParams.get("mode");
    if (mode === "er") {
      setAppMode("er");
      // 응급실 모드는 인증 불필요 (또는 별도 인증)
      setIsAuthenticated(true);
      setLoading(false);
      return;
    }

    // 앱 시작 시 세션 확인 (구급대원 모드)
    const checkAuth = async () => {
      try {
        const user = await getCurrentUser();
        setIsAuthenticated(user !== null);
      } catch (error) {
        console.error("인증 확인 실패:", error);
        setIsAuthenticated(false);
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, []);

  const handleLoginSuccess = () => {
    setIsAuthenticated(true);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600"></div>
          <p className="mt-4 text-gray-600">로딩 중...</p>
        </div>
      </div>
    );
  }

  // 응급실 모드
  if (appMode === "er") {
    return <ERDashboard />;
  }

  // 구급대원 모드
  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />;
  }

  return <SafeBridgeApp />;
};

export default App;
