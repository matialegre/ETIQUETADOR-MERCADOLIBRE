import React, { useEffect, useMemo, useRef, useState } from 'react'
import { fetchOrders, OrderItem, updateOrderDepositoWithNote, updateOrderComentario } from '../api/client'

type BoolSel = '' | '1' | '0'
type ShippingEstado = '' | 'ready_to_print' | 'printed' | 'cancelled' | 'shipped'

// Depósitos válidos (excluyendo MELI según tu lista)
const DEPOSITOS_VALIDOS = [
  'DEP', 'DEPO', 'MTGBBPS', 'MONBAHIA', 'MUNDOAL', 'MUNDOROC', 'MTGJBJ', 
  'NQNALB', 'MTGROCA', 'MTGCOM', 'MUNDOCAB', 'MDQ', 'DIVIDIDO'
]

const todayIso = () => {
  const d = new Date()
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).toISOString()
}
const yesterdayIso = () => {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).toISOString()
}

export default function Orders({ mode }: { mode?: 'default' | 'acc2' }) {
  const isAcc2 = mode === 'acc2'
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>('')
  const [items, setItems] = useState<OrderItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [limit, setLimit] = useState(100)
  const [acc, setAcc] = useState<'acc1'|'acc2'>(isAcc2 ? 'acc2' : 'acc1')

  // filtros
  const [qSku, setQSku] = useState('')
  const [qTitle, setQTitle] = useState('')
  const [qBarcode, setQBarcode] = useState('')
  const [deposito, setDeposito] = useState('')
  const [depositoKw, setDepositoKw] = useState('')
  const [printed, setPrinted] = useState<BoolSel>('')
  const [rtp, setRtp] = useState<BoolSel>('')
  const [shippingEstado, setShippingEstado] = useState<ShippingEstado>('')
  const [includePrinted, setIncludePrinted] = useState<boolean>(false)
  
  // Estado para cambio de depósito
  const [editingOrderId, setEditingOrderId] = useState<number | null>(null)
  const [newDeposito, setNewDeposito] = useState('')
  const [updating, setUpdating] = useState(false)
  const [message, setMessage] = useState('')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  // Debounce por orden para COMENTARIO
  const comentarioTimers = useRef<Record<number, any>>({})
  // Selección de filas para impresión
  const [selected, setSelected] = useState<Set<number>>(new Set())

  const params = useMemo(()=>({
    page, limit,
    acc,
    q_sku: qSku || undefined,
    q_title: qTitle || undefined,
    q_barcode: qBarcode || undefined,
    deposito_asignado: isAcc2 ? undefined : (deposito || undefined),
    deposito_keywords: isAcc2 ? undefined : (depositoKw || undefined),
    printed: printed || undefined,
    ready_to_print: rtp || undefined,
    shipping_estado: shippingEstado || undefined,
    desde: desde || undefined,
    hasta: hasta || undefined,
    include_printed: includePrinted ? 1 : undefined,
    sort_by: 'id', sort_dir: 'DESC',
  }), [page, limit, acc, qSku, qTitle, qBarcode, deposito, depositoKw, printed, rtp, shippingEstado, includePrinted, desde, hasta, isAcc2])

  useEffect(()=>{
    let alive = true
    async function load(){
      setLoading(true); setError('')
      try {
        const res = await fetchOrders(params)
        if (!alive) return
        setItems(res.items)
        setTotal(res.total)
      } catch (e:any) {
        setError(e.message || 'Error cargando órdenes')
      } finally {
        setLoading(false)
      }
    }
    load()
    return ()=>{ alive = false }
  }, [params])

  function quick(range: 'hoy'|'ayer'|'ult7'){
    if (range === 'hoy') { setDesde(todayIso()); setHasta('') }
    if (range === 'ayer') { setDesde(yesterdayIso()); setHasta(todayIso()) }
    if (range === 'ult7') {
      const d = new Date(); d.setDate(d.getDate() - 7)
      setDesde(d.toISOString()); setHasta('')
    }
    setPage(1)
  }

  async function fetchData() {
    setLoading(true); setError('')
    try {
      const res = await fetchOrders(params)
      setItems(res.items)
      setTotal(res.total)
    } catch (e:any) {
      setError(e.message || 'Error cargando órdenes')
    } finally {
      setLoading(false)
    }
  }

  // Formateo robusto para fechas provenientes del backend (ISO o 'YYYY-MM-DD HH:mm:ss.ffffff')
  function formatFecha(v: any): string {
    if (!v) return '-'
    try {
      const s = String(v)
      if (s.includes('T')) {
        // ISO: 2025-09-04T13:34:29.000Z -> 2025-09-04 13:34:29.000
        return s.replace('T', ' ').replace(/Z$/, '')
      }
      // Ya viene con espacio desde SQL Server: devolver tal cual
      return s
    } catch {
      return '-'
    }
  }

  const handleUpdateDeposito = async (orderId: number) => {
    if (!newDeposito.trim()) return;
    
    setUpdating(true);
    try {
      const result = await updateOrderDepositoWithNote(orderId, newDeposito);
      if (result.ok) {
        setMessage(`✅ Depósito actualizado y nota republicada para orden ${orderId}`);
        // Refrescar datos
        await fetchData();
      } else {
        setMessage(`❌ Error: ${result.note_error || 'Error desconocido'}`);
      }
    } catch (error) {
      console.error('Error updating deposito:', error);
      setMessage(`❌ Error actualizando depósito: ${error}`);
    } finally {
      setUpdating(false);
      setEditingOrderId(null);
      setNewDeposito('');
      // Limpiar mensaje después de 5 segundos
      setTimeout(() => setMessage(''), 5000);
    }
  };

  const handleAsignarDividido = async (orderId: number) => {
    // TODO: Implementar modal para asignación manual de depósitos por artículo
    alert(`Funcionalidad en desarrollo para orden ${orderId}`);
  };

  async function handlePrintRTP(){
    try {
      setLoading(true)
      const q: any = {
        page: 1,
        limit: 1000,
        acc,
        sort_by: 'date_created',
        sort_dir: 'DESC',
      }
      // Respetar filtros actuales: shipping_estado si está, sino forzar ready_to_print=1
      if (shippingEstado) {
        q.shipping_estado = shippingEstado
      } else {
        q.ready_to_print = '1'
      }
      // printed: por defecto 0, a menos que el usuario marcó incluir impresas
      if (!includePrinted) q.printed = '0'
      // Depósito: en ACC2 forzamos MUNDOCAB; si no, preferir keywords o asignado exacto
      if (isAcc2) {
        q.deposito_asignado = 'MUNDOCAB'
      } else {
        if (depositoKw) q.deposito_keywords = depositoKw
        else if (deposito) q.deposito_asignado = deposito
      }
      // Si hay selección, imprimimos solo los seleccionados visibles; si no, buscamos según filtros
      let rows: any[] = []
      if (selected.size > 0) {
        rows = items.filter(it => selected.has(it.order_id)) as any[]
      } else {
        const res = await fetchOrders(q)
        rows = res.items || []
      }
      if (!rows.length) { alert('No hay órdenes READY TO PRINT para el filtro seleccionado.'); return }
      const title = isAcc2
        ? `ACC2 CABA - Ready To Print - MUNDOCAB`
        : `Ready To Print${deposito?` - ${deposito}`: depositoKw?` - ${depositoKw}`:''}`
      const now = new Date().toLocaleString()
      const css = `body{font-family:Arial, sans-serif;padding:16px;background:#fff;color:#000} h1{font-size:18px;margin:0 0 8px} .meta{color:#555;margin-bottom:8px} table{width:100%;border-collapse:collapse} th,td{border:1px solid #ccc;padding:6px 8px;font-size:13px} th{background:#f5f5f5;text-align:left} .small{font-size:12px;color:#777}`
      const thead = `<thead><tr><th>Nombre</th><th>Artículo</th><th>Color</th><th>Talle</th><th>Cant.</th><th>Depósito</th><th>Comentario</th></tr></thead>`
      const tbody = `<tbody>${rows.map((o:any)=>{
        const nombre = o.nombre || ''
        const articulo = o.ARTICULO || ''
        const color = o.COLOR || o.display_color || ''
        const talle = o.TALLE || ''
        const qty = (o.qty ?? o.quantity ?? 1)
        const dep = o.deposito_asignado || ''
        const com = o.COMENTARIO || o.comentario || ''
        return `<tr><td>${nombre}</td><td>${articulo}</td><td>${color}</td><td>${talle}</td><td>${qty}</td><td>${dep}</td><td>${com}</td></tr>`
      }).join('')}</tbody>`
      const html = `<!doctype html><html><head><meta charset="utf-8"/><title>${title}</title><style>${css}</style></head><body><h1>${title}</h1><div class="meta">Generado: ${now}</div><table>${thead}${tbody}</table><p class="small">Fuente: /orders ready_to_print=1, printed=0${isAcc2?`, deposito=MUNDOCAB`:(deposito?`, deposito=${deposito}`: depositoKw?`, deposito_keywords=${depositoKw}`:'')}</p></body></html>`
      const win = window.open('', '_blank')!
      win.document.open(); win.document.write(html); win.document.close(); win.focus();
      setTimeout(()=>{ try{ win.print(); }catch(_){} }, 300)
    } catch (e:any) {
      alert(`Error al generar impresión: ${e.message || e}`)
    } finally {
      setLoading(false)
    }
  }

  const handleComentarioChange = (orderId: number, comentario: string) => {
    // Optimistic UI: actualizar localmente el comentario
    setItems(prev => prev.map(it => it.order_id === orderId ? ({ ...it, COMENTARIO: comentario } as OrderItem) : it))
    // Limpiar timer anterior
    if (comentarioTimers.current[orderId]) {
      clearTimeout(comentarioTimers.current[orderId])
    }
    // Debounce 600ms la llamada al backend
    comentarioTimers.current[orderId] = setTimeout(async () => {
      try {
        await updateOrderComentario(orderId, comentario)
      } catch (e:any) {
        setError(e.message || 'Error actualizando comentario')
      }
    }, 600)
  }

  function startEdit(orderId: number, currentDeposito: string) {
    setEditingOrderId(orderId)
    setNewDeposito(currentDeposito || '')
  }

  return (
    <div className="space-y-4">
      {message && (
        <div className="p-3 bg-zinc-800 rounded">
          {message}
        </div>
      )}

      {error && (
        <div className="p-3 bg-red-900/50 text-red-200 rounded">
          {error}
        </div>
      )}
      <div className="flex flex-wrap gap-2 items-end">
        {!isAcc2 ? (
          <div className="flex flex-col">
            <label className="text-xs text-zinc-400">Cuenta ML</label>
            <select value={acc} onChange={e=>{ setAcc(e.target.value as 'acc1'|'acc2'); setPage(1) }} className="px-2 py-1 bg-zinc-800 rounded">
              <option value='acc1'>acc1</option>
              <option value='acc2'>acc2</option>
            </select>
          </div>
        ) : (
          <div className="flex flex-col">
            <label className="text-xs text-zinc-400">Cuenta</label>
            <span className="px-2 py-1 bg-zinc-800 rounded text-xs">ACC2 CABA</span>
          </div>
        )}
        <div className="flex flex-col">
          <label className="text-xs text-zinc-400">SKU</label>
          <input value={qSku} onChange={e=>setQSku(e.target.value)} className="px-2 py-1 bg-zinc-800 rounded outline-none" placeholder="q_sku"/>
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-zinc-400">Título</label>
          <input value={qTitle} onChange={e=>setQTitle(e.target.value)} className="px-2 py-1 bg-zinc-800 rounded outline-none" placeholder="q_title"/>
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-zinc-400">Barcode</label>
          <input value={qBarcode} onChange={e=>setQBarcode(e.target.value)} className="px-2 py-1 bg-zinc-800 rounded outline-none" placeholder="q_barcode"/>
        </div>
        {!isAcc2 && (
          <>
            <div className="flex flex-col">
              <label className="text-xs text-zinc-400">Depósito</label>
              <input value={deposito} onChange={e=>setDeposito(e.target.value.toUpperCase())} className="px-2 py-1 bg-zinc-800 rounded outline-none" placeholder="DEP, MUNDOAL, ..."/>
            </div>
            <div className="flex flex-col">
              <label className="text-xs text-zinc-400">Depósito (keywords)</label>
              <input value={depositoKw} onChange={e=>setDepositoKw(e.target.value)} className="px-2 py-1 bg-zinc-800 rounded outline-none" placeholder="DEPO,MUNDOAL,MTGBBL..."/>
            </div>
          </>
        )}
        <div className="flex flex-col">
          <label className="text-xs text-zinc-400">Estado Shipping</label>
          <select value={shippingEstado} onChange={e=>setShippingEstado(e.target.value as ShippingEstado)} className="px-2 py-1 bg-zinc-800 rounded">
            <option value=''>Todos</option>
            <option value='ready_to_print'>Ready to Print</option>
            <option value='printed'>Printed</option>
            <option value='cancelled'>Cancelled</option>
            <option value='shipped'>Shipped</option>
          </select>
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-zinc-400">ReadyToPrint</label>
          <select value={rtp} onChange={e=>setRtp(e.target.value as BoolSel)} className="px-2 py-1 bg-zinc-800 rounded">
            <option value=''>--</option>
            <option value='1'>Sí</option>
            <option value='0'>No</option>
          </select>
        </div>
        <div className="flex items-center gap-2 ml-2">
          <input id="incp" type="checkbox" checked={includePrinted} onChange={e=>setIncludePrinted(e.target.checked)} />
          <label htmlFor="incp" className="text-xs text-zinc-400">Incluir impresas</label>
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-zinc-400">Desde</label>
          <input type="datetime-local" value={desde ? desde.slice(0,16) : ''} onChange={e=>setDesde(e.target.value ? new Date(e.target.value).toISOString() : '')} className="px-2 py-1 bg-zinc-800 rounded"/>
        </div>
        <div className="flex flex-col">
          <label className="text-xs text-zinc-400">Hasta</label>
          <input type="datetime-local" value={hasta ? hasta.slice(0,16) : ''} onChange={e=>setHasta(e.target.value ? new Date(e.target.value).toISOString() : '')} className="px-2 py-1 bg-zinc-800 rounded"/>
        </div>
        <div className="flex gap-2 ml-2">
          <button onClick={()=>quick('hoy')} className="px-2 py-1 bg-zinc-800 rounded hover:bg-zinc-700">Hoy</button>
          <button onClick={()=>quick('ayer')} className="px-2 py-1 bg-zinc-800 rounded hover:bg-zinc-700">Ayer</button>
          <button onClick={()=>quick('ult7')} className="px-2 py-1 bg-zinc-800 rounded hover:bg-zinc-700">Últimos 7</button>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button onClick={()=>setSelected(new Set(items.map(i=>i.order_id)))} className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 rounded">Marcar todo</button>
          <button onClick={()=>setSelected(new Set())} className="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 rounded">Limpiar selección</button>
          <span className="text-xs text-zinc-400">Sel: {selected.size}</span>
          <button onClick={handlePrintRTP} className="px-2 py-1 bg-green-700 hover:bg-green-600 rounded">
            Imprimir RTP (PDF)
          </button>
          <span className="text-sm text-zinc-400">Total: {total}</span>
          <select value={limit} onChange={e=>{setLimit(parseInt(e.target.value)); setPage(1)}} className="px-2 py-1 bg-zinc-800 rounded">
            {[50,100,200,500,1000].map(n=> <option key={n} value={n}>{n}/página</option> )}
          </select>
        </div>
      </div>

      {error && <div className="text-red-400 text-sm bg-red-900/20 p-2 rounded">{error}</div>}
      {updating && <div className="text-blue-400 text-sm bg-blue-900/20 p-2 rounded">Actualizando depósito y republicando nota en MercadoLibre...</div>}

      <div className="overflow-auto rounded border border-zinc-800">
        <table className="min-w-full text-sm">
          <thead className="bg-zinc-950 text-zinc-400">
            <tr>
              <th className="text-left px-2 py-2">
                <input
                  type="checkbox"
                  checked={items.length>0 && items.every(i=>selected.has(i.order_id))}
                  onChange={(e)=>{
                    if (e.target.checked) setSelected(new Set(items.map(i=>i.order_id)))
                    else setSelected(new Set())
                  }}
                  aria-label="Seleccionar todo"
                />
              </th>
              <th className="text-left px-2 py-2">order_id</th>
              <th className="text-left px-2 py-2">Cuenta ML</th>
              <th className="text-left px-2 py-2">nombre</th>
              <th className="text-right px-2 py-2">qty</th>
              <th className="text-left px-2 py-2">shipping_estado</th>
              <th className="text-left px-2 py-2">depósito</th>
              <th className="text-left px-2 py-2">mov_depo_numero</th>
              <th className="text-left px-2 py-2">numero_movimiento</th>
              <th className="text-left px-2 py-2">fecha</th>
              <th className="text-left px-2 py-2">nota</th>
              <th className="text-left px-2 py-2">comentario</th>
              {!isAcc2 && (<th className="text-left px-2 py-2">acciones</th>)}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={12} className="px-2 py-6 text-center text-zinc-400">Cargando...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={12} className="px-2 py-6 text-center text-zinc-500">Sin resultados</td></tr>
            ) : (
              items.map((it)=> (
                <tr key={it.order_id} className="border-t border-zinc-800 hover:bg-zinc-800/40">
                  <td className="px-2 py-1">
                    <input type="checkbox" checked={selected.has(it.order_id)} onChange={()=>setSelected(prev=>{ const n=new Set(prev); if(n.has(it.order_id)) n.delete(it.order_id); else n.add(it.order_id); return n; })} />
                  </td>
                  <td className="px-2 py-1">{it.order_id}</td>
                  <td className="px-2 py-1 text-xs">{(it as any).meli_account || acc}</td>
                  <td className="px-2 py-1">{(it as any).nombre || ''}</td>
                  <td className="px-2 py-1 text-right">{it.qty}</td>
                  <td className="px-2 py-1">
                    {(() => {
                      const label = (it as any).shipping_subestado || it.shipping_estado || ''
                      const cls = label === 'ready_to_print' ? 'bg-yellow-900 text-yellow-200'
                        : label === 'printed' ? 'bg-blue-900 text-blue-200'
                        : label === 'shipped' ? 'bg-green-900 text-green-200'
                        : label === 'cancelled' ? 'bg-red-900 text-red-200'
                        : 'bg-zinc-700 text-zinc-300'
                      return (
                        <span className={`px-2 py-1 rounded text-xs ${cls}`}>
                          {label}
                        </span>
                      )
                    })()}
                  </td>
                  <td className="px-2 py-1">
                    {(!isAcc2 && editingOrderId === it.order_id) ? (
                      <div className="flex gap-1 items-center">
                        <select 
                          value={newDeposito} 
                          onChange={e=>setNewDeposito(e.target.value)}
                          className="px-1 py-1 bg-zinc-700 rounded text-xs"
                          disabled={updating}
                        >
                          <option value="">--</option>
                          {DEPOSITOS_VALIDOS.map(dep => (
                            <option key={dep} value={dep}>{dep}</option>
                          ))}
                        </select>
                        <button 
                          onClick={() => handleUpdateDeposito(it.order_id)}
                          disabled={updating || !newDeposito.trim()}
                          className="px-2 py-1 bg-green-700 hover:bg-green-600 disabled:opacity-50 rounded text-xs"
                        >
                          ✓
                        </button>
                        <button 
                          onClick={() => setEditingOrderId(null)}
                          disabled={updating}
                          className="px-2 py-1 bg-red-700 hover:bg-red-600 disabled:opacity-50 rounded text-xs"
                        >
                          ✗
                        </button>
                      </div>
                    ) : (
                      <span className="px-2 py-1 bg-zinc-700 rounded text-xs">{it.deposito_asignado}</span>
                    )}
                  </td>
                  <td className="px-2 py-1 text-xs">
                    <span className="px-2 py-1 bg-zinc-800 rounded text-xs">
                      {(it as any).mov_depo_numero || '-'}
                    </span>
                  </td>
                  <td className="px-2 py-1 text-xs">
                    <span className="px-2 py-1 bg-zinc-800 rounded text-xs">
                      {(it as any).numero_movimiento || '-'}
                    </span>
                  </td>
                  <td className="px-2 py-1 text-xs">
                    {formatFecha((it as any).date_closed || it.date_created)}
                  </td>
                  <td className="px-2 py-1 text-xs">
                    <div className="max-w-xs truncate" title={(it as any).note || ''}>
                      {(it as any).note || '-'}
                    </div>
                  </td>
                  <td className="px-2 py-1 text-xs">
                    <input 
                      type="text"
                      value={(it as any).COMENTARIO || ''}
                      onChange={(e) => handleComentarioChange(it.order_id, e.target.value)}
                      className="w-full px-1 py-1 bg-zinc-700 rounded text-xs"
                      placeholder="Agregar comentario..."
                    />
                  </td>
                  {!isAcc2 && (
                    <td className="px-2 py-1">
                      {editingOrderId !== it.order_id && (
                        <div className="flex gap-1">
                          <button 
                            onClick={() => startEdit(it.order_id, it.deposito_asignado || '')}
                            className="px-2 py-1 bg-blue-700 hover:bg-blue-600 rounded text-xs"
                          >
                            Cambiar Depósito
                          </button>
                          {it.deposito_asignado === 'DIVIDIDO' && (
                            <button 
                              onClick={() => handleAsignarDividido(it.order_id)}
                              className="px-2 py-1 bg-orange-700 hover:bg-orange-600 rounded text-xs whitespace-nowrap"
                            >
                              Asignar Depósito
                            </button>
                          )}
                        </div>
                      )}
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between">
        <button disabled={page<=1} onClick={()=>setPage(p=>Math.max(1, p-1))} className="px-3 py-1 bg-zinc-800 rounded disabled:opacity-50">Prev</button>
        <div className="text-sm text-zinc-400">Página {page}</div>
        <button onClick={()=>setPage(p=>p+1)} className="px-3 py-1 bg-zinc-800 rounded">Next</button>
      </div>
    </div>
  )
}
