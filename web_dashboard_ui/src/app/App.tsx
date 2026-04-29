import { useEffect } from 'react';
import { RouterProvider } from 'react-router';
import { router } from './routes';
import { AuthGate } from './components/AuthGate';

export default function App() {
  useEffect(() => {
    const saved = window.localStorage.getItem('dashboard_theme');
    const theme = saved === 'light' ? 'light' : 'dark';
    document.documentElement.classList.toggle('dark', theme === 'dark');
    document.documentElement.style.colorScheme = theme;
  }, []);

  return (
    <AuthGate>
      <RouterProvider router={router} />
    </AuthGate>
  );
}
