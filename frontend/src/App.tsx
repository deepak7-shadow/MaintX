import { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppLayout } from './components/Layout';
import { DashboardPage } from './pages/DashboardPage';
import { MachinesPage, MachineDetailPage } from './pages/MachinesPage';
import { MaintenancePage, MaintenanceDetailPage } from './pages/MaintenancePage';
import { PLCIntegrityPage } from './pages/PLCIntegrityPage';
import { ChangeInvestigationPage } from './pages/ChangeInvestigationPage';
import { LogbookPage } from './pages/LogbookPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { ReportsPage } from './pages/ReportsPage';
import { NotificationsPage } from './pages/NotificationsPage';
import { LoginPage } from './pages/LoginPage';
import { IntroExperience } from './pages/intro/IntroExperience';
import type { UserRole } from './lib/types';

interface AuthUser {
  name: string;
  role: UserRole;
  email: string;
}

const DEFAULT_USER: AuthUser = {
  name: 'SOC Lead Controller',
  role: 'ADMIN',
  email: 'admin@maintx.internal',
};

export function App() {
  const [user, setUser] = useState<AuthUser | null>(() => {
    try {
      const stored = localStorage.getItem('maintx_auth_user');
      return stored ? JSON.parse(stored) : DEFAULT_USER;
    } catch {
      return DEFAULT_USER;
    }
  });

  const handleLogin = (newUser: AuthUser) => {
    setUser(newUser);
    try {
      localStorage.setItem('maintx_auth_user', JSON.stringify(newUser));
    } catch (e) {
      console.warn('LocalStorage error:', e);
    }
  };

  const handleLogout = () => {
    setUser(null);
    try {
      localStorage.removeItem('maintx_auth_user');
    } catch (e) {
      console.warn('LocalStorage error:', e);
    }
  };

  return (
    <BrowserRouter>
      <Routes>
        {/* Cinematic Intro Experience */}
        <Route path="/" element={<IntroExperience />} />
        <Route path="/intro" element={<IntroExperience />} />

        {/* Public Login Route */}
        <Route
          path="/login"
          element={
            user ? (
              <Navigate to="/dashboard" replace />
            ) : (
              <LoginPage onLogin={handleLogin} />
            )
          }
        />

        {/* Protected SOC Routes */}
        <Route
          path="/*"
          element={
            !user ? (
              <Navigate to="/login" replace />
            ) : (
              <AppLayout currentUser={user} onLogout={handleLogout}>
                <Routes>
                  <Route path="/dashboard" element={<DashboardPage />} />
                  <Route path="/machines" element={<MachinesPage />} />
                  <Route path="/machines/:code" element={<MachineDetailPage />} />
                  <Route path="/maintenance" element={<MaintenancePage />} />
                  <Route path="/maintenance/:id" element={<MaintenanceDetailPage />} />
                  <Route path="/plc-integrity" element={<PLCIntegrityPage />} />
                  <Route path="/changes" element={<ChangeInvestigationPage />} />
                  <Route path="/logbook" element={<LogbookPage />} />
                  <Route path="/analytics" element={<AnalyticsPage />} />
                  <Route path="/reports" element={<ReportsPage />} />
                  <Route path="/notifications" element={<NotificationsPage />} />
                  <Route path="*" element={<Navigate to="/dashboard" replace />} />
                </Routes>
              </AppLayout>
            )
          }
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
