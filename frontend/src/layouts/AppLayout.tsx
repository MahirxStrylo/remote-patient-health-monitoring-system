import { useState } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  LayoutDashboard, Users, Activity, Heart, Cpu, Radio, Server, Settings,
  LogOut, AlertTriangle, FileText, ChevronLeft, ChevronRight, Menu, X,
  Sun, Moon, ShieldCheck, Wifi, WifiOff
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { useTheme } from '../hooks/useTheme';
import { api } from '../services/api';

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard', badge: null },
  { to: '/patients', icon: Users, label: 'Patients', badge: null },
  { to: '/prescriptions', icon: FileText, label: 'Prescriptions', badge: 'Directives' },
  { to: '/recordings', icon: Activity, label: 'ECG Sessions', badge: null },
  { to: '/vitals', icon: Heart, label: 'Vitals Trends', badge: null },
  { to: '/devices', icon: Cpu, label: 'Device Registry', badge: null },
  { to: '/device-status', icon: Radio, label: 'Telemetry Health', badge: null },
  { to: '/system-status', icon: Server, label: 'System Status', badge: null },
  { to: '/settings', icon: Settings, label: 'Settings', badge: null },
];

export default function AppLayout() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Periodic health ping for live backend status pill
  const { data: health, isSuccess: isBackendOnline } = useQuery({
    queryKey: ['system-health-pill'],
    queryFn: () => api.getHealth(),
    refetchInterval: 15_000,
  });

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const currentNav = navItems.find(item => location.pathname.startsWith(item.to)) || navItems[0];

  return (
    <div className="flex h-screen bg-navy-950 text-slate-100 overflow-hidden font-sans select-none">
      {/* Mobile Backdrop */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 md:hidden transition-opacity"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar (Desktop + Mobile Drawer) */}
      <aside
        className={`fixed md:static inset-y-0 left-0 z-50 flex flex-col transition-all duration-300 ease-in-out border-r border-charcoal-700/60 bg-navy-900/95 backdrop-blur-md ${
          isCollapsed ? 'w-20' : 'w-64'
        } ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        {/* Brand & Logo Header */}
        <div className="p-4 border-b border-charcoal-700/50 flex items-center justify-between">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-9 h-9 bg-cyan-500/15 border border-cyan-500/40 rounded-xl flex items-center justify-center flex-shrink-0 shadow-glow-cyan">
              <Activity className="w-5 h-5 text-cyan-400 animate-pulse" />
            </div>
            {!isCollapsed && (
              <div className="min-w-0">
                <div className="text-slate-100 font-bold text-sm tracking-tight flex items-center gap-1.5">
                  HealthMonitor
                  <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">v2.0</span>
                </div>
                <div className="text-slate-500 text-[11px] truncate">Rural Cellular Telemetry</div>
              </div>
            )}
          </div>

          {/* Desktop Collapse Toggle */}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="hidden md:flex items-center justify-center w-6 h-6 rounded-md hover:bg-charcoal-800 text-slate-400 hover:text-slate-200 transition-colors"
            title={isCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>

          {/* Mobile Close Button */}
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="md:hidden text-slate-400 hover:text-slate-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {navItems.map(({ to, icon: Icon, label, badge }) => (
            <NavLink
              key={to}
              to={to}
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) =>
                `group relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-xs font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/40 shadow-sm font-semibold'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-charcoal-800/60 border border-transparent'
                } ${isCollapsed ? 'justify-center' : ''}`
              }
              title={isCollapsed ? label : undefined}
            >
              <Icon className="w-4 h-4 flex-shrink-0 transition-transform group-hover:scale-105" />
              {!isCollapsed && (
                <span className="flex-1 truncate">{label}</span>
              )}
              {!isCollapsed && badge && (
                <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                  {badge}
                </span>
              )}
              {isCollapsed && (
                <div className="absolute left-full ml-2 px-2.5 py-1 bg-navy-950 border border-charcoal-700 text-slate-200 text-xs rounded-md shadow-lg pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-50 whitespace-nowrap">
                  {label}
                </div>
              )}
            </NavLink>
          ))}
        </nav>

        {/* User Identity & Logout Footer */}
        <div className="p-3 border-t border-charcoal-700/60 bg-navy-950/60">
          <div className="flex items-center gap-2.5 px-2 py-2 mb-1.5">
            <div className="w-8 h-8 bg-cyan-500/20 border border-cyan-500/30 rounded-full flex items-center justify-center text-cyan-300 text-xs font-bold flex-shrink-0">
              {user?.username?.[0]?.toUpperCase() ?? 'D'}
            </div>
            {!isCollapsed && (
              <div className="flex-1 min-w-0">
                <div className="text-slate-200 text-xs font-semibold truncate leading-tight">
                  {user?.full_name || user?.username}
                </div>
                <div className="text-slate-500 text-[11px] truncate flex items-center gap-1 mt-0.5">
                  <ShieldCheck className="w-3 h-3 text-cyan-400 flex-shrink-0" />
                  {user?.is_admin ? 'Lead Clinician (Admin)' : 'Attending Physician'}
                </div>
              </div>
            )}
          </div>
          <button
            onClick={handleLogout}
            className={`flex items-center gap-2 w-full px-3 py-2 text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 rounded-lg text-xs font-medium transition-colors ${
              isCollapsed ? 'justify-center' : ''
            }`}
            title="Sign out of Clinical Session"
          >
            <LogOut className="w-4 h-4 flex-shrink-0" />
            {!isCollapsed && <span>Sign out</span>}
          </button>
        </div>
      </aside>

      {/* Main View Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Navbar */}
        <header className="h-14 border-b border-charcoal-700/60 bg-navy-900/60 backdrop-blur-md px-4 md:px-6 flex items-center justify-between flex-shrink-0 z-30">
          {/* Left: Mobile hamburger + Breadcrumb */}
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="md:hidden p-1.5 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-charcoal-800"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2">
              <currentNav.icon className="w-4 h-4 text-cyan-400 hidden sm:block" />
              <span className="text-sm font-semibold text-slate-200">{currentNav.label}</span>
              <span className="text-slate-600 text-xs hidden sm:inline">/</span>
              <span className="text-xs text-slate-400 hidden sm:inline">Rural Telemetry Network</span>
            </div>
          </div>

          {/* Right: Telemetry Health + Theme Switcher + Doctor Chip */}
          <div className="flex items-center gap-3">
            {/* Live Backend Connection Indicator */}
            <div
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
                isBackendOnline
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
              }`}
              title={isBackendOnline ? `FastAPI Server Online: ${health?.status || 'Active'}` : 'Backend unreachable on localhost:8000'}
            >
              {isBackendOnline ? (
                <>
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse flex-shrink-0" />
                  <span className="hidden sm:inline font-mono text-[11px]">API 8000 Online</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-3 h-3 text-rose-400" />
                  <span className="hidden sm:inline text-[11px]">API Offline</span>
                </>
              )}
            </div>

            {/* Dark / Light Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg bg-charcoal-800/80 hover:bg-charcoal-700 text-slate-300 hover:text-slate-100 border border-charcoal-700 transition-colors"
              title={`Switch to ${theme === 'dark' ? 'Clinical Light' : 'Midnight Dark'} Theme`}
            >
              {theme === 'dark' ? (
                <Sun className="w-4 h-4 text-amber-400" />
              ) : (
                <Moon className="w-4 h-4 text-cyan-400" />
              )}
            </button>

            {/* Doctor Initials Avatar */}
            <div className="w-7 h-7 rounded-full bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-[11px] font-bold text-cyan-300">
              {user?.username?.[0]?.toUpperCase() ?? 'Dr'}
            </div>
          </div>
        </header>

        {/* Clinical Research Disclaimer Banner */}
        <div className="bg-amber-950/20 border-b border-amber-800/30 px-4 py-1.5 flex items-center justify-between gap-2.5 flex-shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
            <span className="text-amber-300/90 text-[11px] truncate">
              <strong>Clinical Research Prototype:</strong> Designed for low-power edge nodes (ESP32 DevKit V1 + SIM800L GPRS / Wi-Fi). Values are non-evaluative for autonomous diagnostic decisions.
            </span>
          </div>
          <span className="hidden lg:inline text-[10px] text-amber-400/70 font-mono flex-shrink-0">
            Node: ESP32-001 · Bandwidth: 2G GPRS
          </span>
        </div>

        {/* Dynamic Route Content */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 bg-navy-950">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
