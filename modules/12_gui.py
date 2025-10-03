"""
PASO 12: GUI Monitor - PIPELINE 4
=================================

Monitor visual con Tkinter + ttkbootstrap para visualizar órdenes en tiempo real.
Conecta via WebSocket para updates automáticos.
"""

import json
import threading
import tkinter as tk
from tkinter import ttk
import pyodbc
from datetime import datetime
from typing import Optional

try:
    import ttkbootstrap as tb
    from ttkbootstrap import Style
    BOOTSTRAP_AVAILABLE = True
except ImportError:
    print("ttkbootstrap no disponible, usando tkinter estándar")
    BOOTSTRAP_AVAILABLE = False

try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    print("websocket-client no disponible, usando polling")
    WEBSOCKET_AVAILABLE = False

class PipelineGUI:
    def __init__(self):
        # Crear ventana principal
        if BOOTSTRAP_AVAILABLE:
            self.root = tb.Window(themename="darkly")
            self.style = Style(theme="darkly")
        else:
            self.root = tk.Tk()
            
        self.root.title("Pipeline Monitor - PIPELINE 4")
        self.root.geometry("1200x800")
        
        # Connection string
        self.conn_str = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=.\\SQLEXPRESS;DATABASE=meli_stock;Trusted_Connection=yes;'
        
        # WebSocket
        self.ws: Optional[websocket.WebSocketApp] = None
        self.ws_connected = False
        
        self.setup_ui()
        self.setup_websocket()
        self.refresh_data()
        
        # Auto-refresh cada 5 segundos como respaldo
        self.auto_refresh()
    
    def setup_ui(self):
        """Configura la interfaz de usuario."""
        
        # Frame principal
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Título y estadísticas
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill='x', pady=(0, 10))
        
        title_label = ttk.Label(title_frame, text="🔥 PIPELINE 4 - MONITOR DE ÓRDENES", font=('Arial', 16, 'bold'))
        title_label.pack(side='left')
        
        self.status_label = ttk.Label(title_frame, text="Conectando...", font=('Arial', 10))
        self.status_label.pack(side='right')
        
        # Frame de estadísticas
        stats_frame = ttk.LabelFrame(main_frame, text="Estadísticas", padding=10)
        stats_frame.pack(fill='x', pady=(0, 10))
        
        self.stats_text = ttk.Label(stats_frame, text="Cargando estadísticas...")
        self.stats_text.pack()
        
        # Treeview para órdenes
        tree_frame = ttk.LabelFrame(main_frame, text="Órdenes", padding=10)
        tree_frame.pack(fill='both', expand=True)
        
        # Definir columnas
        columns = ("order_id", "sku", "deposito", "subestado", "shipping", "qty", "resultante", "fecha")
        
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)
        
        # Configurar headers
        headers = {
            "order_id": "Order ID",
            "sku": "SKU", 
            "deposito": "Depósito",
            "subestado": "Subestado",
            "shipping": "Shipping",
            "qty": "Qty",
            "resultante": "Stock",
            "fecha": "Fecha"
        }
        
        for col in columns:
            self.tree.heading(col, text=headers[col])
            
        # Configurar anchos de columna
        widths = {
            "order_id": 150,
            "sku": 120,
            "deposito": 100,
            "subestado": 120,
            "shipping": 100,
            "qty": 50,
            "resultante": 60,
            "fecha": 120
        }
        
        for col in columns:
            self.tree.column(col, width=widths[col])
        
        # Scrollbar para treeview
        scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Configurar colores por estado
        self.setup_colors()
        
        # Frame de botones
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(button_frame, text="🔄 Actualizar", command=self.refresh_data).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="📊 Estadísticas", command=self.show_stats).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="🔌 Reconectar WS", command=self.reconnect_websocket).pack(side='left')
        
        # Label de última actualización
        self.last_update_label = ttk.Label(button_frame, text="")
        self.last_update_label.pack(side='right')
    
    def setup_colors(self):
        """Configura colores por estado."""
        if BOOTSTRAP_AVAILABLE:
            # Colores con ttkbootstrap
            self.tree.tag_configure("ready", background="#28a745", foreground="white")  # Verde
            self.tree.tag_configure("printed", background="#007bff", foreground="white")  # Azul
            self.tree.tag_configure("shipped", background="#6c757d", foreground="white")  # Gris
            self.tree.tag_configure("stock_zero", background="#dc3545", foreground="white")  # Rojo
            self.tree.tag_configure("normal", background="#ffffff", foreground="black")  # Blanco
        else:
            # Colores estándar
            self.tree.tag_configure("ready", background="#90EE90")  # Verde claro
            self.tree.tag_configure("printed", background="#87CEEB")  # Azul claro
            self.tree.tag_configure("shipped", background="#D3D3D3")  # Gris claro
            self.tree.tag_configure("stock_zero", background="#FFB6C1")  # Rojo claro
            self.tree.tag_configure("normal", background="#FFFFFF")  # Blanco
    
    def setup_websocket(self):
        """Configura conexión WebSocket."""
        if not WEBSOCKET_AVAILABLE:
            self.status_label.config(text="❌ WebSocket no disponible - Usando polling")
            return
            
        try:
            self.ws = websocket.WebSocketApp(
                "ws://localhost:5000/events/ws",
                on_message=self.on_websocket_message,
                on_error=self.on_websocket_error,
                on_close=self.on_websocket_close,
                on_open=self.on_websocket_open
            )
            
            # Ejecutar WebSocket en thread separado
            ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
            ws_thread.start()
            
        except Exception as e:
            print(f"Error configurando WebSocket: {e}")
            self.status_label.config(text="❌ Error WebSocket - Usando polling")
    
    def on_websocket_open(self, ws):
        """Callback cuando se abre la conexión WebSocket."""
        self.ws_connected = True
        self.root.after(0, lambda: self.status_label.config(text="🟢 WebSocket conectado"))
        print("WebSocket conectado")
    
    def on_websocket_message(self, ws, message):
        """Callback cuando llega un mensaje WebSocket."""
        try:
            data = json.loads(message)
            print(f"WebSocket mensaje: {data}")
            
            # Actualizar UI en thread principal
            self.root.after(0, self.handle_websocket_data, data)
            
        except Exception as e:
            print(f"Error procesando mensaje WebSocket: {e}")
    
    def on_websocket_error(self, ws, error):
        """Callback cuando hay error en WebSocket."""
        print(f"WebSocket error: {error}")
        self.ws_connected = False
        self.root.after(0, lambda: self.status_label.config(text="❌ WebSocket error"))
    
    def on_websocket_close(self, ws, close_status_code, close_msg):
        """Callback cuando se cierra WebSocket."""
        print("WebSocket cerrado")
        self.ws_connected = False
        self.root.after(0, lambda: self.status_label.config(text="🔴 WebSocket desconectado"))
    
    def handle_websocket_data(self, data):
        """Maneja datos recibidos por WebSocket."""
        event_type = data.get('type', '')
        
        if event_type == 'orders.printed':
            # Una orden fue marcada como printed
            order_id = data.get('order_id', '')
            print(f"Orden marcada como printed: {order_id}")
            
            # Actualizar datos
            self.refresh_data()
            
        elif event_type == 'connection.established':
            print("Conexión WebSocket establecida")
    
    def reconnect_websocket(self):
        """Reconecta WebSocket."""
        if self.ws:
            self.ws.close()
        
        threading.Timer(1.0, self.setup_websocket).start()
    
    def refresh_data(self):
        """Actualiza los datos de la tabla."""
        try:
            # Limpiar tabla
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Obtener datos de BD
            with pyodbc.connect(self.conn_str) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT order_id, sku, deposito_asignado, subestado, 
                           shipping_subestado, qty, resultante, fecha_asignacion
                    FROM orders_meli 
                    WHERE asignado_flag = 1
                    ORDER BY fecha_asignacion DESC
                """)
                
                rows = cursor.fetchall()
                
                for row in rows:
                    order_id, sku, deposito, subestado, shipping, qty, resultante, fecha = row
                    
                    # Formatear fecha
                    fecha_str = fecha.strftime('%Y-%m-%d %H:%M') if fecha else ''
                    
                    # Insertar en tabla
                    values = (order_id, sku, deposito or '', subestado or '', 
                             shipping or '', qty or 0, resultante or 0, fecha_str)
                    
                    item_id = self.tree.insert("", "end", values=values)
                    
                    # Aplicar color según estado
                    tag = self.get_color_tag(subestado, resultante)
                    self.tree.item(item_id, tags=(tag,))
                
                # Actualizar estadísticas
                self.update_stats(len(rows))
                
                # Actualizar timestamp
                self.last_update_label.config(text=f"Última actualización: {datetime.now().strftime('%H:%M:%S')}")
                
        except Exception as e:
            print(f"Error actualizando datos: {e}")
            self.status_label.config(text=f"❌ Error BD: {str(e)[:50]}...")
    
    def get_color_tag(self, subestado: str, resultante: int) -> str:
        """Determina el color según el estado."""
        if resultante == 0:
            return "stock_zero"
        elif subestado == "ready_to_print":
            return "ready"
        elif subestado == "printed":
            return "printed"
        elif subestado in ["shipped", "delivered"]:
            return "shipped"
        else:
            return "normal"
    
    def update_stats(self, total_orders: int):
        """Actualiza las estadísticas."""
        try:
            with pyodbc.connect(self.conn_str) as conn:
                cursor = conn.cursor()
                
                # Contar por subestado
                cursor.execute("""
                    SELECT subestado, COUNT(*) as count
                    FROM orders_meli 
                    WHERE asignado_flag = 1
                    GROUP BY subestado
                """)
                
                status_counts = {}
                for row in cursor.fetchall():
                    status_counts[row[0] or 'sin_estado'] = row[1]
                
                # Contar stock agotado
                cursor.execute("""
                    SELECT COUNT(*) FROM orders_meli 
                    WHERE asignado_flag = 1 AND resultante = 0
                """)
                
                stock_zero = cursor.fetchone()[0]
                
                # Formatear estadísticas
                stats_text = f"Total: {total_orders} | "
                stats_text += f"Ready: {status_counts.get('ready_to_print', 0)} | "
                stats_text += f"Printed: {status_counts.get('printed', 0)} | "
                stats_text += f"Shipped: {status_counts.get('shipped', 0)} | "
                stats_text += f"Stock 0: {stock_zero}"
                
                if self.ws_connected:
                    stats_text += " | 🟢 WS"
                else:
                    stats_text += " | 🔴 WS"
                
                self.stats_text.config(text=stats_text)
                
        except Exception as e:
            self.stats_text.config(text=f"Error estadísticas: {e}")
    
    def show_stats(self):
        """Muestra ventana de estadísticas detalladas."""
        stats_window = tk.Toplevel(self.root)
        stats_window.title("Estadísticas Detalladas")
        stats_window.geometry("600x400")
        
        text_widget = tk.Text(stats_window, wrap=tk.WORD, padx=10, pady=10)
        scrollbar_stats = ttk.Scrollbar(stats_window, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar_stats.set)
        
        try:
            with pyodbc.connect(self.conn_str) as conn:
                cursor = conn.cursor()
                
                # Estadísticas por depósito
                cursor.execute("""
                    SELECT deposito_asignado, COUNT(*) as count, 
                           AVG(CAST(resultante as FLOAT)) as avg_stock
                    FROM orders_meli 
                    WHERE asignado_flag = 1
                    GROUP BY deposito_asignado
                    ORDER BY count DESC
                """)
                
                stats_text = "📊 ESTADÍSTICAS DETALLADAS\n"
                stats_text += "=" * 50 + "\n\n"
                stats_text += "ÓRDENES POR DEPÓSITO:\n"
                stats_text += "-" * 30 + "\n"
                
                for row in cursor.fetchall():
                    deposito, count, avg_stock = row
                    stats_text += f"{deposito or 'Sin asignar'}: {count} órdenes (stock prom: {avg_stock:.1f})\n"
                
                # Estadísticas por estado
                cursor.execute("""
                    SELECT subestado, COUNT(*) as count
                    FROM orders_meli 
                    WHERE asignado_flag = 1
                    GROUP BY subestado
                    ORDER BY count DESC
                """)
                
                stats_text += "\nÓRDENES POR ESTADO:\n"
                stats_text += "-" * 30 + "\n"
                
                for row in cursor.fetchall():
                    estado, count = row
                    stats_text += f"{estado or 'Sin estado'}: {count} órdenes\n"
                
                text_widget.insert(tk.END, stats_text)
                
        except Exception as e:
            text_widget.insert(tk.END, f"Error obteniendo estadísticas: {e}")
        
        text_widget.pack(side='left', fill='both', expand=True)
        scrollbar_stats.pack(side='right', fill='y')
        text_widget.config(state='disabled')
    
    def auto_refresh(self):
        """Auto-refresh cada 5 segundos."""
        if not self.ws_connected:
            self.refresh_data()
        
        # Programar próximo refresh
        self.root.after(5000, self.auto_refresh)
    
    def run(self):
        """Ejecuta la aplicación."""
        print("🔥 Iniciando GUI Monitor - PIPELINE 4")
        print("Conectando a base de datos...")
        print("Configurando WebSocket...")
        
        self.root.mainloop()

if __name__ == "__main__":
    gui = PipelineGUI()
    gui.run()
