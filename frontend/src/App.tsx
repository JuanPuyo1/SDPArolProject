import { Route, Routes } from 'react-router-dom'
import NavBar from '../components/NavBar'
import MachineInfoPage from '../components/MachineInfoPage'
import ManualPage from '../components/ManualPage'
import ChatbotPage from '../components/ChatbotPage'
import './App.css'

function App() {
  return (
    <>
      <NavBar />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<MachineInfoPage />} />
          <Route path="/manual" element={<ManualPage />} />
          <Route path="/chatbot" element={<ChatbotPage />} />
        </Routes>
      </main>
    </>
  )
}

export default App
