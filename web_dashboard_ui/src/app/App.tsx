import { RouterProvider } from 'react-router';
import { router } from './routes';
import { AuthGate } from './components/AuthGate';

export default function App() {
  return (
    <AuthGate>
      <RouterProvider router={router} />
    </AuthGate>
  );
}
