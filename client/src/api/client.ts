export type HttpMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

export interface ApiOptions {
  method?: HttpMethod
  headers?: Record<string, string>
  body?: any
  token?: string
}

const DEFAULT_BASE = '' // same origin

function getToken(explicit?: string) {
  if (explicit) return explicit
  try {
    return localStorage.getItem('SERVER_API_TOKEN') || ''
  } catch {
    return ''
  }
}

export async function api<T = any>(path: string, opts: ApiOptions = {}): Promise<T> {
  const base = DEFAULT_BASE
  const token = getToken(opts.token)
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers || {}),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(base + path, {
    method: opts.method || 'GET',
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text().catch(()=> '')
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return res.json()
  // @ts-ignore
  return res.text()
}

export interface OrderItem {
  order_id: number
  sku?: string
  qty?: number
  shipping_estado?: string
  shipping_subestado?: string
  printed?: number
  ready_to_print?: number
  deposito_asignado?: string
  date_created?: string
  // Extended fields used by Orders.tsx UI (optional)
  note?: string
  numero_movimiento?: string | number
  mov_depo_numero?: string | number
  tracking_number?: string | number
  // Movimiento LOCAL (nuevo)
  MOV_LOCAL_HECHO?: 0|1
  MOV_LOCAL_NUMERO?: string | number
  MOV_LOCAL_OBS?: string
  COMENTARIO?: string
  // Computed in backend to indicate which ML account the record belongs to
  meli_account?: 'acc1' | 'acc2'
}

export interface OrdersResponse {
  items: OrderItem[]
  total: number
}

export async function fetchOrders(params: Record<string, any> = {}): Promise<OrdersResponse> {
  const q = new URLSearchParams()
  Object.entries(params).forEach(([k,v])=>{ if (v !== undefined && v !== null && v !== '') q.set(k, String(v)) })
  // Backend expone GET /orders (no /api/orders) y devuelve {orders, total}
  const res = await api<{ orders: OrderItem[]; total: number }>(`/orders?${q.toString()}`)
  return { items: res.orders || [], total: res.total || 0 }
}

export interface ChatRequest { text: string; model?: string }
export interface ChatResponse { answer: string, used_llm: boolean }
export async function chat(payload: ChatRequest): Promise<ChatResponse> {
  // Backend espera { model?, messages: [{role, content}] }
  const body: any = {
    model: payload.model || 'deepseek/deepseek-chat',
    messages: [{ role: 'user', content: payload.text }]
  }
  const res = await api<any>(`/api/chat`, { method: 'POST', body })
  // OpenRouter y el atajo local devuelven { choices: [ { message: { content } } ] }
  const content = res?.choices?.[0]?.message?.content || ''
  const used_llm = !!res?.id // OpenRouter típicamente incluye un id
  return { answer: content, used_llm }
}

export function saveToken(token: string) {
  try { localStorage.setItem('SERVER_API_TOKEN', token) } catch {}
}
export function getSavedToken() {
  try { return localStorage.getItem('SERVER_API_TOKEN') || '' } catch { return '' }
}

// Actualizar depósito asignado
export async function updateOrderDeposito(orderId: number, deposito: string, acc?: 'acc1'|'acc2'): Promise<{ok: boolean, affected: number}> {
  const q = acc ? `?acc=${acc}` : ''
  return api(`/orders/${orderId}${q}`, {
    method: 'POST',
    body: { deposito_asignado: deposito }
  })
}

// Actualizar depósito asignado y republicar nota en MercadoLibre
export async function updateOrderDepositoWithNote(orderId: number, deposito: string, acc?: 'acc1'|'acc2'): Promise<{
  ok: boolean, 
  affected: number, 
  note_published: boolean, 
  note_error?: string
}> {
  const q = acc ? `?acc=${acc}` : ''
  return api(`/orders/${orderId}/update-deposito-with-note${q}`, {
    method: 'POST',
    body: { deposito_asignado: deposito }
  })
}

// Actualizar comentario (COMENTARIO) de una orden
export async function updateOrderComentario(orderId: number, comentario: string, acc?: 'acc1'|'acc2'): Promise<{
  ok: boolean,
  affected: number,
}> {
  const q = acc ? `?acc=${acc}` : ''
  return api(`/orders/${orderId}${q}`, {
    method: 'POST',
    body: { COMENTARIO: comentario }
  })
}

// Registrar solo movimiento (sin imprimir), acepta tracking_number o mov_depo_numero
export async function postMovement(
  orderId: number,
  payload: {
    mov_depo_hecho?: 0|1|boolean,
    mov_depo_numero?: string | number,
    tracking_number?: string | number,
    mov_depo_obs?: string,
    // Movimiento LOCAL (nuevo)
    MOV_LOCAL_HECHO?: 0|1|boolean,
    MOV_LOCAL_NUMERO?: string | number,
    MOV_LOCAL_OBS?: string,
    asignacion_detalle?: string,
  },
  acc?: 'acc1'|'acc2'
): Promise<{ ok: boolean; affected: number }> {
  const q = acc ? `?acc=${acc}` : ''
  return api(`/orders/${orderId}/movement${q}`, {
    method: 'POST',
    body: payload,
  })
}

// Opcional: marcar printed + movimiento en una sola llamada (no usado por clientes que no imprimen)
export async function postPrintedMoved(
  orderId: number,
  payload: {
    printed?: 0|1|boolean,
    mov_depo_hecho?: 0|1|boolean,
    mov_depo_numero?: string | number,
    tracking_number?: string | number,
    mov_depo_obs?: string,
    // Movimiento LOCAL (nuevo)
    MOV_LOCAL_HECHO?: 0|1|boolean,
    MOV_LOCAL_NUMERO?: string | number,
    MOV_LOCAL_OBS?: string,
    asignacion_detalle?: string,
  },
  acc?: 'acc1'|'acc2'
): Promise<{ ok: boolean; order_id?: string; updated_at?: string }> {
  const q = acc ? `?acc=${acc}` : ''
  return api(`/orders/${orderId}/printed-moved${q}`, {
    method: 'POST',
    body: payload,
  })
}
