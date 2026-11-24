import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Activity } from 'lucide-react';
import { AuthProvider, useAuth } from './hooks/useAuth';
import { ThemeProvider } from './hooks/useTheme';
import AppLayout from './layouts/AppLayout';

// Lazy-loaded page routes for optimal bundle splitting
const LoginPage = React.lazy(() => import('./pages/LoginPage'));
const DashboardPage = React.lazy(() => import('./pages/DashboardPage'));
const PatientsPage = React.lazy(() => import('./pages/PatientsPage'));
const PrescriptionsPage = React.lazy(() => import('./pages/PrescriptionsPage'));
const PatientDetailPage = React.lazy(() => import('./pages/PatientDetailPage'));
const ECGViewerPage = React.lazy(() => import('./pages/ECGViewerPage'));
const RecordingsPage = React.lazy(() => import('./pages/RecordingsPage'));
const VitalsHistoryPage = React.lazy(() => import('./pages/VitalsHistoryPage'));
const DevicesPage = React.lazy(() => import('./pages/DevicesPage'));
const DeviceStatusPage = React.lazy(() => import('./pages/DeviceStatusPage'));
const SystemStatusPage = React.lazy(() => import('./pages/SystemStatusPage'));
const SettingsPage = React.lazy(() => import('./pages/SettingsPage'));

function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="text-slate-500 flex items-center gap-2 text-sm font-medium">
        <Activity className="w-4 h-4 text-cyan-400 animate-pulse" />
        Loading module…
      </div>
    </div>
  );
}

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AppLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="patients" element={<PatientsPage />} />
              <Route path="patients/:patientId" element={<PatientDetailPage />} />
              <Route path="prescriptions" element={<PrescriptionsPage />} />
              <Route path="ecg/:recordingId" element={<ECGViewerPage />} />
              <Route path="recordings" element={<RecordingsPage />} />
              <Route path="vitals" element={<VitalsHistoryPage />} />
              <Route path="devices" element={<DevicesPage />} />
              <Route path="device-status" element={<DeviceStatusPage />} />
              <Route path="system-status" element={<SystemStatusPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>
  </ThemeProvider>
);
}
