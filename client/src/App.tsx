import React, { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

export default function App() {
  const [user, setUser] = useState<string>('')

  useEffect(()=>{
    try { setUser(localStorage.getItem('UI_USER') || '') } catch {}
  }, [])

  function login(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const fd = new FormData(e.currentTarget)
    const u = String(fd.get('user') || '').trim().toLowerCase()
    const p = String(fd.get('pass') || '').trim()
    const ok = (u === 'valen' && p === 'valen') || (u === 'admin' && p === 'admin')
    if (ok) {
      try { localStorage.setItem('UI_USER', u) } catch {}
      setUser(u)
    } else {
      alert('Credenciales inválidas')
    }
  }
  function logout(){ try { localStorage.removeItem('UI_USER') } catch {}; setUser('') }

  if (!user) {
    return (
      <div className="min-h-screen grid place-items-center bg-zinc-950 text-zinc-100">
        <form onSubmit={login} className="bg-zinc-900 p-6 rounded border border-zinc-800 w-[320px]">
          <h1 className="text-lg mb-4">Ingresar</h1>
          <label className="block text-sm mb-1 text-zinc-400">Usuario</label>
          <input name="user" className="w-full px-3 py-2 rounded bg-zinc-800 border border-zinc-700 outline-none" />
          <label className="block text-sm mb-1 text-zinc-400 mt-3">Contraseña</label>
          <input name="pass" type="password" className="w-full px-3 py-2 rounded bg-zinc-800 border border-zinc-700 outline-none" />
          <button type="submit" className="mt-4 w-full bg-green-700 hover:bg-green-600 px-3 py-2 rounded">Entrar</button>
          <p className="text-xs text-zinc-500 mt-3">Acceso simple local.</p>
        </form>
      </div>
    )
  }
  return (
    <div className="min-h-screen grid grid-rows-[auto_1fr]">
      <header className="border-b border-zinc-800 bg-zinc-950/60 backdrop-blur sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-4">
          <div className="text-lg font-semibold text-brand-500">MEGA API</div>
          <nav className="flex items-center gap-3 text-sm">
            <NavLink to="/orders" className={({isActive})=>`px-2 py-1 rounded ${isActive? 'bg-zinc-800 text-white':'text-zinc-300 hover:text-white'}`}>Órdenes</NavLink>
            <NavLink to="/caba-orders" className={({isActive})=>`px-2 py-1 rounded ${isActive? 'bg-zinc-800 text-white':'text-zinc-300 hover:text-white'}`}>CABA</NavLink>
            <NavLink to="/chat" className={({isActive})=>`px-2 py-1 rounded ${isActive? 'bg-zinc-800 text-white':'text-zinc-300 hover:text-white'}`}>Chat IA</NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm text-zinc-300">
            <span className="px-2 py-1 bg-zinc-800 rounded">{user}</span>
            <button onClick={logout} className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 rounded">Salir</button>
          </div>
        </div>
      </header>
      <main className="max-w-7xl mx-auto w-full px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
