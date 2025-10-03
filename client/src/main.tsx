import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './index.css'
import App from './App'
import Orders from './pages/Orders'
import Chat from './pages/Chat'

const Root = () => (
  <BrowserRouter basename="/ui">
    <Routes>
      <Route path="/" element={<App />}> 
        <Route index element={<Navigate to="/orders" replace />} />
        <Route path="/orders" element={<Orders />} />
        <Route path="/caba-orders" element={<Orders mode="acc2" />} />
        <Route path="/chat" element={<Chat />} />
      </Route>
    </Routes>
  </BrowserRouter>
)

createRoot(document.getElementById('root')!).render(<Root />)
