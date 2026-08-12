import { Route, Routes, Navigate } from 'react-router-dom'
import NavBar from '../components/NavBar'
import MachineInfoPage from '../components/MachineInfoPage'
import ManualPage from '../components/ManualPage'
import ChatbotPage from '../components/ChatbotPage'
import WelcomePage from '../components/WelcomePage'
import ProfilePage from '../components/ProfilePage'
import OrdersPage from '../components/OrdersPage'
import MaintenanceTicketsPage from '../components/MaintenanceTicketsPage'
import ProtectedRoute from '../components/ProtectedRoute'
import VisibilityRoute from '../components/VisibilityRoute'
import { useAuth } from './hooks/useAuth'
import './App.css'

function AppShell() {
  const { user, loading } = useAuth()

  return (
    <>
      {!loading && user && <NavBar />}
      <main className="app-main">
        <Routes>
          <Route path="/" element={<WelcomePage />} />
          <Route path="/login" element={<Navigate to="/" replace />} />
          <Route
            path="/machine"
            element={
              <ProtectedRoute>
                <MachineInfoPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/manual"
            element={
              <ProtectedRoute>
                <ManualPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/orders"
            element={
              <VisibilityRoute allowed={['full', 'commercial']}>
                <OrdersPage />
              </VisibilityRoute>
            }
          />
          <Route
            path="/maintenance"
            element={
              <VisibilityRoute allowed={['full', 'technician']}>
                <MaintenanceTicketsPage />
              </VisibilityRoute>
            }
          />
          <Route
            path="/chatbot"
            element={
              <ProtectedRoute>
                <ChatbotPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/profile"
            element={
              <ProtectedRoute>
                <ProfilePage />
              </ProtectedRoute>
            }
          />
        </Routes>
      </main>
    </>
  )
}

export default function App() {
  return <AppShell />
}
