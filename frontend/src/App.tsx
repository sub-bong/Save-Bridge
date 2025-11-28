import React, { useState, useEffect } from "react";
import { SafeBridgeApp } from "./components/SafeBridgeApp";
import { LoginPage } from "./components/LoginPage";
import { getCurrentUser } from "./services/api";

const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 앱 시작 시 세션 확인
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

  if (!isAuthenticated) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />;
  }

  return <SafeBridgeApp />;
};

export default App;
