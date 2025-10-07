# gui/app_gui_v3_caba.py
"""
GUI específica para CABA - Versión optimizada con filtros para CAB, CABA y MUNDOCAB.
Conecta al servidor remoto de Bahía Blanca y usa la base de datos de CABA.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from datetime import datetime, timedelta
from typing import List
import threading
import time

# Importar configuración específica de CABA
import config_caba

# Importar servicios específicos de CABA
from services.picker_service_caba import PickerServiceCaba
from services.print_service_caba import PrintServiceCaba
from api.dragonfish_api_caba import dragonfish_caba
from utils.db_caba import db_caba

# Importar componentes comunes
from gui.state import GuiState
from gui.order_refresher import OrderRefresher
from utils.logger import get_logger
from utils.daily_stats import get_packages_today, get_picked_today
from models.order import Order

log = get_logger(__name__)

# Filtros específicos para CABA
KEYWORDS_NOTE_CABA = config_caba.KEYWORDS_NOTE_CABA
DEFAULT_MOTIVOS = ["Manchado", "Roto", "No está"]

class AppV3Caba(tb.Window):
    """Aplicación principal para CABA."""
    
    COLS = ("nombre", "cant", "talle", "color")

    def __init__(self) -> None:
        super().__init__(title=config_caba.APP_TITLE, themename="darkly")
        self.geometry("1200x700")

        # --- servicios / estado ---
        self.picker = PickerServiceCaba()
        self.print_service = PrintServiceCaba()
        self.state = GuiState()
        self.refresher = OrderRefresher(
            self.picker, 
            self.state, 
            notification_callback=self._show_new_sale_notification
        )
        self._refresher_started = False

        # Variables de control
        self._current_ids: List[str] = []
        self._current_sku_analysis = {}
        self._last_analyzed_orders = []
        
        # Variables para contadores
        self.progress_var = tk.DoubleVar()
        self.lbl_progress = None
        self.lbl_pending_count = None

        # Construir interfaz
        self._build_widgets()
        self.after(1000, self.poll_state)
        
        # Mostrar información de configuración CABA
        self._show_caba_info()

    def _show_caba_info(self):
        """Muestra información de la configuración CABA al iniciar."""
        info_msg = f"""
🏢 CONFIGURACIÓN CABA ACTIVA

📡 API Dragonfish: {config_caba.DRAGONFISH_BASE_URL}
🗄️ SQL Server: {config_caba.SQL_SERVER}
📊 Base de datos: {config_caba.DATABASE_NAME}
🏷️ Filtros de notas: {', '.join(KEYWORDS_NOTE_CABA)}
🏪 Depósito: {config_caba.DEPOSITO_DISPLAY_NAME}

¡Sistema listo para operar en CABA!
        """
        
        # Mostrar en consola
        print(info_msg)
        
        # Mostrar popup informativo (opcional)
        try:
            messagebox.showinfo("Configuración CABA", info_msg.strip())
        except:
            pass  # Si hay error con el popup, continuar normalmente

    def _build_widgets(self) -> None:
        """Construye la interfaz de usuario."""
        # Frame principal
        main_frame = tb.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=YES)

        # --- SECCIÓN SUPERIOR: Controles de fecha y botones ---
        top_frame = tb.Frame(main_frame)
        top_frame.pack(fill=X, pady=(0, 10))

        # Fechas
        date_frame = tb.Frame(top_frame)
        date_frame.pack(side=LEFT, padx=(0, 20))

        tb.Label(date_frame, text="Desde:", font=("Arial", 10)).grid(row=0, column=0, sticky=W, padx=(0, 5))
        self.date_from = tb.DateEntry(date_frame, dateformat="%Y-%m-%d")
        self.date_from.grid(row=0, column=1, padx=(0, 10))

        tb.Label(date_frame, text="Hasta:", font=("Arial", 10)).grid(row=0, column=2, sticky=W, padx=(0, 5))
        self.date_to = tb.DateEntry(date_frame, dateformat="%Y-%m-%d")
        self.date_to.grid(row=0, column=3, padx=(0, 10))

        # Establecer fechas por defecto (últimos 3 días)
        today = datetime.now()
        self.date_from.entry.delete(0, tk.END)
        self.date_from.entry.insert(0, (today - timedelta(days=3)).strftime("%Y-%m-%d"))
        self.date_to.entry.delete(0, tk.END)
        self.date_to.entry.insert(0, today.strftime("%Y-%m-%d"))

        # Botones principales
        btn_frame = tb.Frame(top_frame)
        btn_frame.pack(side=LEFT, padx=(0, 20))

        self.btn_load = tb.Button(btn_frame, text="🔄 Cargar Pedidos CABA", 
                                 bootstyle=PRIMARY, command=self.on_load_orders)
        self.btn_load.pack(side=LEFT, padx=(0, 10))

        self.btn_refresh = tb.Button(btn_frame, text="♻️ Refrescar", 
                                    bootstyle=INFO, command=self.on_refresh)
        self.btn_refresh.pack(side=LEFT, padx=(0, 10))

        # Filtros específicos CABA
        filter_frame = tb.Frame(top_frame)
        filter_frame.pack(side=LEFT)

        self.var_show_printed = tk.BooleanVar(value=False)
        tb.Checkbutton(filter_frame, text="Mostrar impresos", 
                      variable=self.var_show_printed, 
                      command=self.on_filter_change).pack(side=LEFT, padx=(0, 10))

        self.var_until_13h = tk.BooleanVar(value=False)
        tb.Checkbutton(filter_frame, text="Solo hasta 13hs", 
                      variable=self.var_until_13h, 
                      command=self.on_filter_change).pack(side=LEFT, padx=(0, 10))

        # --- SECCIÓN MEDIA: Tabla de pedidos ---
        table_frame = tb.Frame(main_frame)
        table_frame.pack(fill=BOTH, expand=YES, pady=(0, 10))

        # Crear Treeview
        self.tree = ttk.Treeview(table_frame, columns=self.COLS, show="tree headings", height=15)
        
        # Configurar columnas
        self.tree.heading("#0", text="📦 Pedido", anchor=W)
        self.tree.heading("nombre", text="🏷️ Artículo", anchor=W)
        self.tree.heading("cant", text="📊 Cant", anchor=CENTER)
        self.tree.heading("talle", text="👕 Talle", anchor=CENTER)
        self.tree.heading("color", text="🎨 Color", anchor=CENTER)

        # Configurar anchos
        self.tree.column("#0", width=200, minwidth=150)
        self.tree.column("nombre", width=400, minwidth=300)
        self.tree.column("cant", width=80, minwidth=60)
        self.tree.column("talle", width=100, minwidth=80)
        self.tree.column("color", width=150, minwidth=100)

        # Scrollbars
        v_scroll = ttk.Scrollbar(table_frame, orient=VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(table_frame, orient=HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        # Empaquetar tabla y scrollbars
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Configurar tags de colores para diferentes estados
        self.tree.tag_configure("printed", background="#1b5e20", foreground="white")
        self.tree.tag_configure("ready", background="#5c1b1b", foreground="white")
        self.tree.tag_configure("barcode_found", background="#f57f17", foreground="black")
        self.tree.tag_configure("barcode_custom", background="#ff6f00", foreground="white")
        self.tree.tag_configure("barcode_missing", background="#c62828", foreground="white")

        # --- SECCIÓN INFERIOR: Controles y estadísticas ---
        bottom_frame = tb.Frame(main_frame)
        bottom_frame.pack(fill=X)

        # Frame izquierdo: Botones de acción
        left_frame = tb.Frame(bottom_frame)
        left_frame.pack(side=LEFT, fill=X, expand=True)

        action_frame = tb.Frame(left_frame)
        action_frame.pack(side=LEFT, pady=5)

        # Botones específicos para CABA
        self.btn_print_caba = tb.Button(action_frame, text="🖨️ Imprimir PDF CABA", 
                                       bootstyle=SUCCESS, command=self.on_print_caba_pdf)
        self.btn_print_caba.pack(side=LEFT, padx=(0, 10))

        self.btn_test_connections = tb.Button(action_frame, text="🔧 Test Conexiones", 
                                             bootstyle=WARNING, command=self.on_test_connections)
        self.btn_test_connections.pack(side=LEFT, padx=(0, 10))

        # Frame derecho: Estadísticas y contadores
        right_frame = tb.Frame(bottom_frame)
        right_frame.pack(side=RIGHT, padx=(20, 0))

        stats_frame = tb.Frame(right_frame)
        stats_frame.pack(side=RIGHT)

        # Contador de pedidos pendientes
        self.lbl_pending_count = tb.Label(stats_frame, text="📋 Artículos pendientes: 0", 
                                         font=("Arial", 10, "bold"))
        self.lbl_pending_count.pack(anchor=E, pady=(0, 5))

        # Barra de progreso
        progress_frame = tb.Frame(stats_frame)
        progress_frame.pack(anchor=E, pady=(0, 5))

        self.lbl_progress = tb.Label(progress_frame, text="📊 Progreso del día: 0% (0/0)", 
                                    font=("Arial", 9))
        self.lbl_progress.pack(anchor=E)

        progress_bar = tb.Progressbar(progress_frame, variable=self.progress_var, 
                                     length=200, mode='determinate')
        progress_bar.pack(anchor=E, pady=(2, 0))

        # Estadísticas diarias
        daily_stats_frame = tb.Frame(stats_frame)
        daily_stats_frame.pack(anchor=E)

        self.lbl_daily_stats = tb.Label(daily_stats_frame, 
                                       text=f"📦 Paquetes hoy: {get_packages_today()} | 📋 Artículos: {get_picked_today()}", 
                                       font=("Arial", 9))
        self.lbl_daily_stats.pack(anchor=E)

        # Eventos
        self.tree.bind("<Double-1>", self.on_item_double_click)

    def on_load_orders(self):
        """Carga pedidos con filtros específicos de CABA."""
        try:
            date_from = datetime.strptime(self.date_from.entry.get(), "%Y-%m-%d")
            date_to = datetime.strptime(self.date_to.entry.get(), "%Y-%m-%d")
            
            # Mostrar mensaje de carga
            self.btn_load.configure(text="🔄 Cargando...", state=DISABLED)
            self.update()
            
            # Cargar pedidos
            orders = self.picker.load_orders(date_from, date_to)
            
            # Filtrar por keywords de CABA
            filtered_orders = []
            for order in orders:
                note = (order.notes or "").upper()
                if any(keyword in note for keyword in KEYWORDS_NOTE_CABA):
                    filtered_orders.append(order)
            
            self.state.visibles = filtered_orders
            
            # Actualizar tabla
            self.populate_tree(filtered_orders)
            
            # Restaurar botón
            self.btn_load.configure(text="🔄 Cargar Pedidos CABA", state=NORMAL)
            
            # Mostrar resultado
            messagebox.showinfo("Carga Completa", 
                              f"✅ {len(filtered_orders)} pedidos CABA cargados\n"
                              f"📊 Total original: {len(orders)}")
            
        except Exception as e:
            log.error(f"Error cargando pedidos CABA: {e}")
            messagebox.showerror("Error", f"Error cargando pedidos: {str(e)}")
            self.btn_load.configure(text="🔄 Cargar Pedidos CABA", state=NORMAL)

    def on_print_caba_pdf(self):
        """Imprime PDF filtrado por keywords de CABA."""
        try:
            if not hasattr(self.state, 'visibles') or not self.state.visibles:
                messagebox.showwarning("Sin datos", "No hay pedidos cargados para imprimir")
                return
            
            # Filtrar pedidos para impresión
            rows = []
            for order in self.state.visibles:
                note = (order.notes or "").upper()
                
                # Solo procesar si tiene keywords de CABA y está listo para imprimir
                if (any(keyword in note for keyword in KEYWORDS_NOTE_CABA) and 
                    order.shipping_substatus == 'ready_to_print'):
                    
                    for item in order.items:
                        rows.append({
                            'pedido': f"#{order.pack_id or order.id}",
                            'articulo': item.title or 'Sin título',
                            'sku': item.sku or 'Sin SKU',
                            'cantidad': item.quantity or 1,
                            'talle': getattr(item, 'size', '') or '',
                            'color': getattr(item, 'color', '') or '',
                            'deposito': config_caba.DEPOSITO_DISPLAY_NAME
                        })
            
            if not rows:
                messagebox.showwarning("Sin datos", 
                                     f"No hay pedidos listos para imprimir con filtros CABA\n"
                                     f"Keywords: {', '.join(KEYWORDS_NOTE_CABA)}")
                return
            
            # Generar PDF
            self.print_service.generate_and_open_pdf(rows)
            messagebox.showinfo("PDF Generado", 
                              f"✅ PDF CABA generado exitosamente\n"
                              f"📊 {len(rows)} artículos incluidos")
            
        except Exception as e:
            log.error(f"Error generando PDF CABA: {e}")
            messagebox.showerror("Error", f"Error generando PDF: {str(e)}")

    def on_test_connections(self):
        """Prueba las conexiones remotas."""
        try:
            results = []
            
            # Test API Dragonfish
            api_ok = dragonfish_caba.test_connection()
            results.append(f"📡 API Dragonfish: {'✅ OK' if api_ok else '❌ FALLO'}")
            
            # Test Base de datos
            db_ok = db_caba.test_connection()
            results.append(f"🗄️ Base de datos: {'✅ OK' if db_ok else '❌ FALLO'}")
            
            # Mostrar resultados
            result_msg = "\n".join(results)
            if api_ok and db_ok:
                messagebox.showinfo("Test de Conexiones", f"🎉 Todas las conexiones OK\n\n{result_msg}")
            else:
                messagebox.showwarning("Test de Conexiones", f"⚠️ Algunas conexiones fallaron\n\n{result_msg}")
                
        except Exception as e:
            log.error(f"Error en test de conexiones: {e}")
            messagebox.showerror("Error", f"Error probando conexiones: {str(e)}")

    def populate_tree(self, orders):
        """Puebla la tabla con los pedidos."""
        # Limpiar tabla
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        for order in orders:
            # Determinar tag según estado
            if order.shipping_substatus == 'printed':
                tag = "printed"
            else:
                tag = "ready"
            
            # Insertar pedido principal
            order_id = f"#{order.pack_id or order.id}"
            parent = self.tree.insert("", "end", text=f"{order_id} - {order.buyer}", 
                                    values=("", "", "", ""), tags=(tag,))
            
            # Insertar artículos
            for item in order.items:
                nombre = item.title or "Sin título"
                cantidad = item.quantity or 1
                talle = getattr(item, 'size', '') or ''
                color = getattr(item, 'color', '') or ''
                
                self.tree.insert(parent, "end", text="", 
                               values=(nombre, cantidad, talle, color), 
                               tags=(tag,))
        
        # Actualizar contadores
        self._update_pending_counter()
        self._update_progress_bar()

    def _update_pending_counter(self):
        """Actualiza el contador de artículos pendientes."""
        if hasattr(self.state, 'visibles') and self.state.visibles:
            pending_count = sum(
                len(order.items) for order in self.state.visibles 
                if order.shipping_substatus != 'printed'
            )
        else:
            pending_count = 0
        
        self.lbl_pending_count.config(text=f"📋 Artículos pendientes CABA: {pending_count}")

    def _update_progress_bar(self):
        """Actualiza la barra de progreso."""
        try:
            if not hasattr(self.state, 'visibles') or not self.state.visibles:
                self.progress_var.set(0)
                self.lbl_progress.config(text="📊 Progreso CABA: 0% (0/0)")
                return
            
            total_orders = len(self.state.visibles)
            completed_orders = sum(
                1 for order in self.state.visibles 
                if order.shipping_substatus == 'printed'
            )
            
            if total_orders > 0:
                progress_percent = (completed_orders / total_orders) * 100
                self.progress_var.set(progress_percent)
                self.lbl_progress.config(
                    text=f"📊 Progreso CABA: {progress_percent:.1f}% ({completed_orders}/{total_orders})"
                )
            else:
                self.progress_var.set(0)
                self.lbl_progress.config(text="📊 Progreso CABA: 0% (0/0)")
                
        except Exception as e:
            log.error(f"Error actualizando progreso: {e}")

    def on_refresh(self):
        """Refresca la vista actual."""
        if hasattr(self.state, 'visibles') and self.state.visibles:
            self.populate_tree(self.state.visibles)

    def on_filter_change(self):
        """Maneja cambios en los filtros."""
        # Implementar lógica de filtrado si es necesario
        pass

    def on_item_double_click(self, event):
        """Maneja doble clic en un artículo."""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            messagebox.showinfo("Detalle", f"Artículo: {item['values']}")

    def _show_new_sale_notification(self, new_orders):
        """Muestra notificación de nuevas ventas CABA."""
        try:
            # Filtrar solo ventas CABA
            caba_orders = [
                order for order in new_orders 
                if any(keyword in (order.notes or "").upper() for keyword in KEYWORDS_NOTE_CABA)
            ]
            
            if caba_orders:
                messagebox.showinfo("Nueva Venta CABA", 
                                  f"🎉 {len(caba_orders)} nueva(s) venta(s) CABA detectada(s)")
        except Exception as e:
            log.error(f"Error en notificación CABA: {e}")

    def poll_state(self):
        """Polling del estado de la aplicación."""
        try:
            # Actualizar estadísticas diarias
            packages_today = get_packages_today()
            picked_today = get_picked_today()
            self.lbl_daily_stats.config(
                text=f"📦 Paquetes hoy: {packages_today} | 📋 Artículos: {picked_today}"
            )
        except Exception as e:
            log.error(f"Error en polling: {e}")
        
        # Programar siguiente polling
        self.after(5000, self.poll_state)

def launch_gui_v3_caba():
    """Lanza la GUI específica para CABA."""
    app = AppV3Caba()
    app.mainloop()

if __name__ == "__main__":
    launch_gui_v3_caba()
