import { useState } from 'react';
import { NavLink } from 'react-router';
import { 
  LayoutDashboard, 
  Video, 
  Bell, 
  Radio, 
  BarChart3, 
  Settings,
  Router,
  X,
  LogOut
} from 'lucide-react';
import { useAuth } from './AuthGate';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Live Monitoring', href: '/live', icon: Video },
  { name: 'Events & Alerts', href: '/events', icon: Bell },
  { name: 'Sensors & Nodes', href: '/sensors', icon: Radio },
  { name: 'Statistics', href: '/statistics', icon: BarChart3 },
  { name: 'Node Onboarding', href: '/onboarding', icon: Router },
  { name: 'Settings', href: '/settings', icon: Settings },
];

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
  desktopHidden?: boolean;
  onDesktopToggle?: () => void;
}

export function Sidebar({ isOpen = true, onClose, desktopHidden = false, onDesktopToggle }: SidebarProps) {
  const { user, logout } = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);

  const handleLogout = async () => {
    if (loggingOut) {
      return;
    }
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      setLoggingOut(false);
    }
  };

  const handleHideSidebar = () => {
    if (onDesktopToggle) {
      onDesktopToggle();
      return;
    }
    onClose?.();
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}
      
      {/* Sidebar */}
      <div className={`
        fixed lg:static inset-y-0 left-0 z-50
        w-56 sm:w-64 lg:flex-none bg-gray-900 text-white flex flex-col h-screen
        transform transition-[transform,width,opacity] duration-300 ease-in-out
        ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        ${desktopHidden ? 'lg:-translate-x-full lg:w-0 lg:opacity-0 lg:pointer-events-none' : 'lg:translate-x-0 lg:w-64 lg:opacity-100'}
      `}
      id="app-sidebar"
      >
        {/* Logo/Brand */}
        <div className="px-6 py-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
                <Radio className="w-6 h-6" />
              </div>
              <div>
                <h2 className="font-semibold">Thesis Monitor</h2>
                <p className="text-xs text-gray-400">Intruder + Fire</p>
              </div>
            </div>
            {/* Close/hide button */}
            <button
              onClick={handleHideSidebar}
              className="hidden lg:inline-flex items-center justify-center rounded-md border border-gray-700 p-1.5 text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
              aria-label="Hide navigation menu"
              title="Hide navigation menu"
            >
              <X className="w-4 h-4" />
            </button>
            <button
              onClick={onClose}
              className="lg:hidden inline-flex items-center justify-center rounded-md border border-gray-700 p-1.5 text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
              aria-label="Close navigation menu"
              title="Close navigation menu"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3">
          <p className="px-3 pb-2 text-[11px] uppercase tracking-wider text-gray-500">Navigation</p>
          <ul className="space-y-1">
            {navigation.map((item) => (
              <li key={item.name}>
                <NavLink
                  to={item.href}
                  end={item.href === '/'}
                  onClick={onClose}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-4 py-2.5 rounded-lg transition-all ${
                      isActive
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                    }`
                  }
                >
                  <item.icon className="w-5 h-5" />
                  <span className="font-medium">{item.name}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        {/* System Info */}
        <div className="px-6 py-4 border-t border-gray-800">
          <div className="text-xs text-gray-400">
            <p>Windows local-first stack</p>
            <p className="mt-1">Sensor transport: HTTP</p>
          </div>
          <button
            onClick={() => {
              void handleLogout();
            }}
            disabled={loggingOut}
            className="mt-4 w-full inline-flex items-center gap-2 rounded-md border border-rose-700/70 bg-rose-900/40 px-3 py-2 text-sm font-medium text-rose-100 hover:bg-rose-800/60 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            aria-label={`Logout ${user.username}`}
            title={`Logout ${user.username}`}
          >
            <LogOut className="w-4 h-4" />
            <span>{loggingOut ? 'Logging out...' : 'Logout'}</span>
            <span className="ml-auto rounded-full bg-rose-950/60 px-2 py-0.5 text-[10px] text-rose-200">
              {user.username}
            </span>
          </button>
        </div>
      </div>
    </>
  );
}
