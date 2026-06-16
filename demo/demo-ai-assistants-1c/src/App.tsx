import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import DemoPage from './pages/DemoPage'
import LiveDemoPage from './pages/LiveDemoPage'
import './App.css'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LiveDemoPage />} />
        <Route path="/demo" element={<DemoPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
