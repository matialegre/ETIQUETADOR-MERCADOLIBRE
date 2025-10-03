(() => {
  const $ = (id) => document.getElementById(id);

  function getConf() {
    return {
      base: $("apiBase").value || location.origin,
      token: $("apiToken").value || "",
    };
  }

  // Cambio de depósito con fallback automático a force=1 si el backend devuelve 409 (write-once)
  async function onChangeDeposito() {
    const id = $("u_order_id").value.trim();
    const depo = $("u_deposito_asignado").value.trim();
    if (!id) { alert("Falta order_id"); return; }
    if (!depo) { alert("Falta deposito_asignado"); return; }
    const path = `/orders/${encodeURIComponent(id)}/update-deposito-with-note`;
    try {
      $("status").textContent = "Actualizando depósito...";
      await apiPost(path, { deposito_asignado: depo });
      $("status").textContent = `OK: depósito cambiado a ${depo}`;
    } catch (e) {
      // Detectar 409 y reintentar con force=1
      const msg = String(e && e.message || "");
      const is409 = msg.startsWith("409 ");
      if (is409) {
        try {
          $("status").textContent = "Reintentando con override (force=1)...";
          await apiPost(path, { deposito_asignado: depo, force: 1 });
          $("status").textContent = `OK (FORZADO): depósito cambiado a ${depo}`;
          return;
        } catch (e2) {
          $("status").textContent = `Error (force): ${e2.message}`;
          return;
        }
      }
      $("status").textContent = `Error: ${e.message}`;
    }
  }

  function saveConf() {
    localStorage.setItem("apiBase", $("apiBase").value);
    localStorage.setItem("apiToken", $("apiToken").value);
  }

  function loadConf() {
    $("apiBase").value = localStorage.getItem("apiBase") || location.origin;
    $("apiToken").value = localStorage.getItem("apiToken") || "";
  }

  async function apiGet(path) {
    const { base, token } = getConf();
    const res = await fetch(`${base}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return res.json();
  }

  async function apiPost(path, body) {
    const { base, token } = getConf();
    const res = await fetch(`${base}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body || {}),
    });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
    return res.json();
  }

  function qs(obj) {
    const p = new URLSearchParams();
    Object.entries(obj).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") p.append(k, v);
    });
    return p.toString();
  }

  function buildQuery() {
    // default fields for simplified UI if input is empty
    const defaultFields = "order_id,nombre,qty,shipping_status,deposito_asignado,date_created";
    const effectiveFields = $("fields").value && $("fields").value.trim() !== ""
      ? $("fields").value.trim()
      : defaultFields;
    return qs({
      fields: effectiveFields,
      order_id: $("order_id").value,
      pack_id: $("pack_id").value,
      sku: $("sku").value,
      seller_sku: $("seller_sku").value,
      barcode: $("barcode").value,
      deposito_asignado: $("deposito_asignado").value,
      shipping_estado: $("shipping_estado").value,
      shipping_subestado: $("shipping_subestado").value,
      desde: $("desde").value,
      hasta: $("hasta").value,
      cerrado_desde: $("cerrado_desde").value,
      cerrado_hasta: $("cerrado_hasta").value,
      q_sku: $("q_sku").value,
      q_barcode: $("q_barcode").value,
      q_comentario: $("q_comentario").value,
      q_title: $("q_title").value,
      ready_to_print: $("ready_to_print").value,
      printed: $("printed").value,
      agotamiento_flag: $("agotamiento_flag").value,
      qty: $("qty").value,
      sort_by: $("sort_by").value,
      sort_dir: $("sort_dir").value,
      page: $("page").value,
      limit: $("limit").value,
    });
  }

  function applyPreset(name) {
    const now = new Date();
    if (name === "ultimas") {
      $("page").value = 1;
      $("limit").value = 200;
      $("sort_by").value = "id";
      $("sort_dir").value = "DESC";
      $("ready_to_print").value = "";
      $("printed").value = "";
      $("deposito_asignado").value = "";
    } else if (name === "rtp") {
      $("ready_to_print").value = "1";
      $("printed").value = "0";
      $("sort_by").value = "date_created";
      $("sort_dir").value = "DESC";
    } else if (name === "sin_asignar") {
      $("deposito_asignado").value = "";
      $("q_comentario").value = "";
      $("ready_to_print").value = "";
      $("printed").value = "";
      $("sort_by").value = "id";
      $("sort_dir").value = "DESC";
    } else if (name === "hoy") {
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      $("desde").value = start.toISOString();
      $("hasta").value = "";
      $("page").value = 1;
      $("limit").value = 200;
    }
  }

  async function sendChat() {
    const txt = $("chatInput").value.trim();
    if (!txt) return;
    const model = $("chatModel").value;
    appendChat("user", txt);
    $("chatInput").value = "";
    try {
      const res = await apiPost("/api/chat", {
        model,
        messages: [
          { role: "system", content: "Sos un asistente de inventario MELI." },
          { role: "user", content: txt },
        ],
      });
      const content = res?.choices?.[0]?.message?.content || JSON.stringify(res);
      appendChat("assistant", content);
    } catch (e) {
      appendChat("assistant", `Error: ${e.message}`);
    }
  }

  function appendChat(role, text) {
    const box = $("chatBox");
    const el = document.createElement("div");
    el.className = `msg ${role}`;
    el.innerHTML = renderMarkdownSafe(text);
    box.appendChild(el);
    box.scrollTop = box.scrollHeight;
  }

  // Minimal Markdown renderer (safe): supports headings (##), bold **, lists -, and tables con '|'
  function renderMarkdownSafe(input) {
    const esc = (s) => String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
    const text = esc(input || "");

    const lines = text.split(/\r?\n/);
    const html = [];
    let i = 0;

    const pushParagraph = (buf) => {
      if (!buf.length) return;
      const joined = buf.join(" ");
      html.push(`<p>${inline(joined)}</p>`);
      buf.length = 0;
    };

    const inline = (s) => {
      // bold **text**
      s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1<\/strong>');
      // inline code `x`
      s = s.replace(/`([^`]+)`/g, '<code>$1<\/code>');
      return s;
    };

    const parseTable = (start) => {
      const header = lines[start];
      const next = lines[start + 1] || "";
      if (!header.includes("|")) return null;
      // Permitir tablas sin línea separadora ---
      const hasSep = /^\s*[-|\s]+$/.test(next) && next.includes("|");
      const rows = [];
      let idx = start + (hasSep ? 2 : 1);
      while (idx < lines.length && lines[idx].includes("|")) {
        rows.push(lines[idx]);
        idx++;
      }
      const th = header.split("|").map((c) => c.trim()).filter(Boolean);
      const tr = rows.map(r => r.split("|").map((c) => c.trim()).filter(Boolean));
      let out = '<div class="md-table"><table><thead><tr>' + th.map(h=>`<th>${h}</th>`).join("") + '</tr></thead><tbody>';
      tr.forEach(r => { out += '<tr>' + r.map(c=>`<td>${c}</td>`).join("") + '</tr>'; });
      out += '</tbody></table></div>';
      return { html: out, next: idx };
    };

    while (i < lines.length) {
      const line = lines[i];
      // headings
      const hx = line.match(/^#{1,3}\s+(.+)$/);
      if (hx) {
        const content = hx[1];
        const pipeIdx = content.indexOf('|');
        if (pipeIdx >= 0) {
          // Caso: heading + tabla inline en la misma línea. Render heading y reinyectar línea de tabla.
          const headText = content.slice(0, pipeIdx).trim();
          const rest = content.slice(pipeIdx).trim();
          const level = (line.match(/^#+/)[0] || '#').length;
          const tag = level === 1 ? 'h1' : level === 2 ? 'h2' : 'h3';
          html.push(`<${tag}>${inline(headText)}</${tag}>`);
          // Reemplazar la línea actual por el inicio de la tabla y continuar sin incrementar i
          lines[i] = rest;
          // Intentar parsear la tabla inmediatamente
          const tbl = parseTable(i);
          if (tbl) { html.push(tbl.html); i = tbl.next; continue; }
          // si no se pudo, seguimos al flujo normal
        } else {
          const level = (line.match(/^#+/)[0] || '#').length;
          const tag = level === 1 ? 'h1' : level === 2 ? 'h2' : 'h3';
          html.push(`<${tag}>${inline(content)}</${tag}>`);
          i++; continue;
        }
      }

      // tables (pipe with separator line next)
      const tbl = parseTable(i);
      if (tbl) { html.push(tbl.html); i = tbl.next; continue; }

      // lists
      if (/^\s*[-*]\s+/.test(line)) {
        const items = [];
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { items.push(lines[i].replace(/^\s*[-*]\s+/, "")); i++; }
        html.push('<ul>' + items.map(x=>`<li>${inline(x)}</li>`).join("") + '</ul>');
        continue;
      }

      // blank line
      if (!line.trim()) { html.push('<br />'); i++; continue; }

      // paragraph accumulation
      const buf = [line.trim()];
      i++;
      while (i < lines.length && lines[i].trim() && !/^\s*[-*]\s+/.test(lines[i]) && !/^#{1,3}\s+/.test(lines[i]) && !lines[i].includes('|')) {
        buf.push(lines[i].trim());
        i++;
      }
      pushParagraph(buf);
    }

    const out = html.join("\n");
    // Fallback: si el texto tiene muchas '|' pero no pudimos estructurar, mostrar como <pre>
    const pipeCount = (text.match(/\|/g) || []).length;
    if (pipeCount >= 6 && !out.includes('<table')) {
      return `<pre>${text}</pre>`;
    }
    return out;
  }

  function renderTable(data) {
    const tbl = $("tbl");
    tbl.innerHTML = "";
    const orders = data.orders || [];
    if (!orders.length) {
      tbl.innerHTML = "<tr><td>Sin resultados</td></tr>";
      return;
    }
    // fixed columns as requested
    const cols = [
      "order_id",
      "nombre",
      "qty",
      "shipping_status",
      "deposito_asignado",
      "date_created",
    ];
    tbl.insertAdjacentHTML(
      "beforeend",
      `<thead><tr>${cols.map((c) => `<th>${c}</th>`).join("")}</tr></thead>`
    );
    const body = orders
      .map((o) => `<tr>${cols.map((c) => {
        let v = o[c];
        // simple fallbacks for legacy keys
        if (c === "shipping_status" && (v === undefined || v === null)) v = o["shipping_estado"];
        if (c === "qty" && (v === undefined || v === null)) v = o["quantity"] ?? 1;
        return `<td>${v ?? ""}</td>`;
      }).join("")}</tr>`)
      .join("");
    tbl.insertAdjacentHTML("beforeend", `<tbody>${body}</tbody>`);
    $("status").textContent = `page=${data.page} total=${data.total}`;
  }

  async function onBuscar() {
    try {
      $("status").textContent = "Buscando...";
      const query = buildQuery();
      const data = await apiGet(`/orders?${query}`);
      renderTable(data);
    } catch (e) {
      $("status").textContent = `Error: ${e.message}`;
    }
  }

  async function onUpdate() {
    const id = $("u_order_id").value;
    if (!id) {
      alert("Falta order_id");
      return;
    }
    const body = {
      deposito_asignado: $("u_deposito_asignado").value || undefined,
      COMENTARIO: $("u_COMENTARIO").value || undefined,
      mov_depo_hecho: $("u_mov_depo_hecho").value || undefined,
      mov_depo_obs: $("u_mov_depo_obs").value || undefined,
      mov_depo_numero: $("u_mov_depo_numero").value || undefined,
      printed: $("u_printed").value || undefined,
      ready_to_print: $("u_ready_to_print").value || undefined,
    };
    Object.keys(body).forEach((k) => body[k] === undefined && delete body[k]);

    try {
      $("status").textContent = "Actualizando...";
      const res = await apiPost(`/orders/${encodeURIComponent(id)}`, body);
      $("status").textContent = `OK: ${JSON.stringify(res)}`;
    } catch (e) {
      $("status").textContent = `Error: ${e.message}`;
    }
  }

  function bind() {
    $("btnSaveConf").addEventListener("click", () => {
      saveConf();
      alert("Guardado");
    });
    $("btnBuscar").addEventListener("click", onBuscar);
    $("btnUpdate").addEventListener("click", onUpdate);
    const btnForce = $("btnChangeDeposito");
    if (btnForce) btnForce.addEventListener("click", onChangeDeposito);
    $("presetUltimas").addEventListener("click", () => { applyPreset("ultimas"); onBuscar(); });
    $("presetRTP").addEventListener("click", () => { applyPreset("rtp"); onBuscar(); });
    $("presetSinAsignar").addEventListener("click", () => { applyPreset("sin_asignar"); onBuscar(); });
    $("presetHoy").addEventListener("click", () => { applyPreset("hoy"); onBuscar(); });
    $("btnChatSend").addEventListener("click", sendChat);
    $("chatInput").addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });

    // Print Ready To Print (client-side PDF via browser print)
    $("btnPrintRTP").addEventListener("click", async () => {
      try {
        const depo = $("deposito_asignado").value.trim();
        const baseQuery = {
          fields: "order_id,nombre,ARTICULO,COLOR,TALLE,qty,deposito_asignado",
          ready_to_print: "1",
          printed: "0",
          sort_by: "date_created",
          sort_dir: "DESC",
          page: 1,
          limit: 1000,
        };
        if (depo) baseQuery.deposito_asignado = depo;
        const query = qs(baseQuery);
        $("status").textContent = "Generando listado para imprimir...";
        const data = await apiGet(`/orders?${query}`);
        const rows = (data && data.orders) || [];
        if (!rows.length) { alert("No hay órdenes READY TO PRINT para el filtro seleccionado."); return; }
        // Build printable HTML
        const win = window.open("", "_blank");
        const title = `Ready To Print${depo ? ` - ${depo}` : ""}`;
        const now = new Date().toLocaleString();
        const css = `body{font-family:Arial, sans-serif;padding:16px} h1{font-size:18px;margin:0 0 8px} .meta{color:#555;margin-bottom:8px} table{width:100%;border-collapse:collapse} th,td{border:1px solid #ccc;padding:6px 8px;font-size:13px} th{background:#f5f5f5;text-align:left} .small{font-size:12px;color:#777}`;
        const headerHtml = `<h1>${title}</h1><div class="meta">Generado: ${now}</div>`;
        const thead = `<thead><tr><th>order_id</th><th>Nombre</th><th>Artículo</th><th>Color</th><th>Talle</th><th>Cant.</th><th>Depósito</th></tr></thead>`;
        const tbody = `<tbody>${rows.map(o => {
          const nombre = o.nombre || "";
          const articulo = o.ARTICULO || "";
          const color = o.COLOR || o.display_color || "";
          const talle = o.TALLE || "";
          const qty = (o.qty ?? o.quantity ?? 1);
          const dep = o.deposito_asignado || "";
          const id = o.order_id || "";
          return `<tr><td>${id}</td><td>${nombre}</td><td>${articulo}</td><td>${color}</td><td>${talle}</td><td>${qty}</td><td>${dep}</td></tr>`;
        }).join("")}</tbody>`;
        const html = `<!doctype html><html><head><meta charset="utf-8"/><title>${title}</title><style>${css}</style></head><body>${headerHtml}<table>${thead}${tbody}</table><p class="small">Fuente: /orders ready_to_print=1, printed=0${depo?`, deposito=${depo}`:""}</p></body></html>`;
        win.document.open();
        win.document.write(html);
        win.document.close();
        win.focus();
        // Delay print to allow rendering
        setTimeout(() => { try { win.print(); } catch(_) {} }, 300);
      } catch (e) {
        alert(`Error al generar impresión: ${e.message}`);
      }
    });
  }

  loadConf();
  // cargar tips del backend y renderizarlos en el panel lateral
  (async () => {
    try {
      const tips = await apiGet("/api/chat/tips");
      const list = document.getElementById("chatTips");
      if (list && tips && Array.isArray(tips.tips)) {
        list.innerHTML = "";
        tips.tips.forEach((t) => {
          const wrap = document.createElement("div");
          wrap.className = "tip";
          const pre = document.createElement("pre");
          pre.textContent = t;
          const actions = document.createElement("div");
          const btnCopy = document.createElement("button");
          btnCopy.textContent = "Copiar";
          btnCopy.addEventListener("click", async () => {
            try { await navigator.clipboard.writeText(t); btnCopy.textContent = "Copiado"; setTimeout(()=>btnCopy.textContent="Copiar",1200);} catch(_){}
          });
          const btnUse = document.createElement("button");
          btnUse.textContent = "Pegar en input";
          btnUse.addEventListener("click", () => { $("chatInput").value = t; $("chatInput").focus(); });
          actions.appendChild(btnCopy);
          actions.appendChild(btnUse);
          wrap.appendChild(pre);
          wrap.appendChild(actions);
          list.appendChild(wrap);
        });
      }
    } catch (e) {
      // silencioso
    }
  })();
  bind();
})();
