import React, { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { chat, ChatResponse, getSavedToken, saveToken } from '../api/client'

interface Msg { role: 'user' | 'assistant'; content: string }

export default function Chat(){
  const [history, setHistory] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [token, setToken] = useState(getSavedToken())
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(()=>{ endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [history])

  async function send(){
    if (!input.trim()) return
    const text = input.trim()
    setInput('')
    setHistory(h=>[...h, {role:'user', content:text}])
    setLoading(true); setError('')
    try {
      const res = await chat({ text })
      setHistory(h=>[...h, {role:'assistant', content: res.answer || ''}])
    } catch(e:any){
      setError(e.message || 'Error en chat')
    } finally{ setLoading(false) }
  }

  function onSaveToken(){ saveToken(token) }

  return (
    <div className="grid grid-rows-[auto_1fr_auto] h-[calc(100vh-120px)] gap-3">
      <div className="flex items-center gap-3">
        <input value={token} onChange={e=>setToken(e.target.value)} placeholder="SERVER_API_TOKEN (opcional)" className="px-2 py-1 bg-zinc-800 rounded flex-1"/>
        <button onClick={onSaveToken} className="px-3 py-1 bg-zinc-800 rounded hover:bg-zinc-700">Guardar token</button>
      </div>

      <div className="overflow-auto border border-zinc-800 rounded p-3 space-y-3">
        {history.length===0 && <div className="text-zinc-400 text-sm">Tip: "me podés dar las últimas ventas?", "del último día de hoy", "cuantos se vendieron de NDPMB0E770AR048"</div>}
        {history.map((m,i)=> (
          <div key={i} className={m.role==='user'? 'text-zinc-100' : 'bg-zinc-800/60 p-3 rounded'}>
            {m.role==='assistant' ? <ReactMarkdown>{m.content}</ReactMarkdown> : <div>{m.content}</div>}
          </div>
        ))}
        <div ref={endRef} />
      </div>

      <div className="flex items-center gap-2">
        <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{ if(e.key==='Enter') send() }}
               className="px-3 py-2 bg-zinc-800 rounded flex-1" placeholder="Escribí tu pregunta..."/>
        <button disabled={loading} onClick={send} className="px-4 py-2 bg-brand-500 rounded text-black disabled:opacity-50">Enviar</button>
        {loading && <div className="text-sm text-zinc-400">Pensando...</div>}
        {error && <div className="text-sm text-red-400">{error}</div>}
      </div>
    </div>
  )
}
