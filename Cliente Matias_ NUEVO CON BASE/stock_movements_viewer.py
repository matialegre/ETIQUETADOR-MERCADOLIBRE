#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Visor de Movimientos de Stock
Aplicación standalone para consultar movimientos de stock via API
"""

import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
from datetime import datetime, timedelta
import threading
from typing import List, Dict

class StockMovementsViewer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Visor de Movimientos de Stock")
        self.root.geometry("1200x800")
        self.root.state('zoomed')  # Maximizar ventana en Windows
        self.root.configure(bg='#f0f0f0')
        
        # Configuración de la API
        self.api_base = "http://190.211.201.217:8888/api.Dragonfish"
        self.headers = {
            "accept": "application/json",
            "Authorization": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE4MTc5ODg0ODQsInVzdWFyaW8iOiJhZG1pbiIsInBhc3N3b3JkIjoiMDE5NGRkMGEyYjA2Yzc4Yzc5YmUxZThjMDQ3ZmFkNTgyZTM2NzJlMzQ0NWFlYzRlODMwMDFiNDdlNGE4MWQwMyJ9.zAWCBxY5smFLyDrNAPqeaaoOJbmG-R-SM7mFFg7MQeE",
            "IdCliente": "MATIAPP",
            "BaseDeDatos": "MELI"
        }

        self.setup_main_window()
        
    def setup_main_window(self):
        """Configura la ventana principal"""
        # Título principal
        title_frame = tk.Frame(self.root, bg='#f0f0f0')
        title_frame.pack(pady=20)
        
        title_label = tk.Label(
            title_frame,
            text="📦 VISOR DE MOVIMIENTOS DE STOCK",
            font=("Arial", 20, "bold"),
            bg='#f0f0f0',
            fg='#2c3e50'
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            title_frame,
            text="Consulta movimientos de stock con filtros personalizables",
            font=("Arial", 12),
            bg='#f0f0f0',
            fg='#7f8c8d'
        )
        subtitle_label.pack(pady=(5, 0))
        
        # Frame principal para el botón
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(expand=True, fill='both', padx=50, pady=50)
        
        # Botón principal
        self.main_button = tk.Button(
            main_frame,
            text="🔍 VER MOVIMIENTOS",
            font=("Arial", 16, "bold"),
            bg='#3498db',
            fg='white',
            relief='raised',
            bd=3,
            padx=30,
            pady=15,
            command=self.open_filters_window,
            cursor='hand2'
        )
        self.main_button.pack(expand=True)
        
        # Información de estado
        self.status_frame = tk.Frame(self.root, bg='#f0f0f0')
        self.status_frame.pack(side='bottom', fill='x', padx=10, pady=10)
        
        self.status_label = tk.Label(
            self.status_frame,
            text="✅ Listo para consultar movimientos",
            font=("Arial", 10),
            bg='#f0f0f0',
            fg='#27ae60'
        )
        self.status_label.pack()
        
    def open_filters_window(self):
        """Abre la ventana de filtros"""
        self.filters_window = tk.Toplevel(self.root)
        self.filters_window.title("Filtros de Búsqueda")
        self.filters_window.geometry("700x600")  # Agrandado de 500x400 a 700x600
        self.filters_window.configure(bg='#f8f9fa')
        self.filters_window.transient(self.root)
        self.filters_window.grab_set()
        
        # Centrar ventana
        self.filters_window.geometry("+{}+{}".format(
            self.root.winfo_rootx() + 50,  # Ajustado para centrar mejor
            self.root.winfo_rooty() + 50
        ))
        
        self.setup_filters_window()
        
    def setup_filters_window(self):
        """Configura la ventana de filtros"""
        # Título
        title_label = tk.Label(
            self.filters_window,
            text="🔧 Configurar Filtros",
            font=("Arial", 16, "bold"),
            bg='#f8f9fa',
            fg='#2c3e50'
        )
        title_label.pack(pady=20)
        
        # Frame principal
        main_frame = tk.Frame(self.filters_window, bg='#f8f9fa')
        main_frame.pack(padx=40, pady=20, fill='both', expand=True)
        
        # Fechas
        dates_frame = tk.LabelFrame(main_frame, text="📅 Rango de Fechas", 
                                   font=("Arial", 14, "bold"), bg='#f8f9fa', fg='#34495e')
        dates_frame.pack(fill='x', pady=15)
        
        # Fecha desde
        from_frame = tk.Frame(dates_frame, bg='#f8f9fa')
        from_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(from_frame, text="Desde:", font=("Arial", 12), 
                bg='#f8f9fa', fg='#2c3e50').pack(side='left')
        
        self.date_from = tk.Entry(from_frame, font=("Arial", 12), width=15)
        self.date_from.pack(side='right')
        # Fecha por defecto: hoy
        today = datetime.now().strftime("%Y-%m-%d")
        self.date_from.insert(0, today)
        
        # Fecha hasta
        to_frame = tk.Frame(dates_frame, bg='#f8f9fa')
        to_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(to_frame, text="Hasta:", font=("Arial", 12), 
                bg='#f8f9fa', fg='#2c3e50').pack(side='left')
        
        self.date_to = tk.Entry(to_frame, font=("Arial", 12), width=15)
        self.date_to.pack(side='right')
        self.date_to.insert(0, today)
        
        # Vendedor
        vendor_frame = tk.LabelFrame(main_frame, text="👤 Vendedor", 
                                    font=("Arial", 14, "bold"), bg='#f8f9fa', fg='#34495e')
        vendor_frame.pack(fill='x', pady=15)
        
        vendor_inner = tk.Frame(vendor_frame, bg='#f8f9fa')
        vendor_inner.pack(fill='x', padx=20, pady=10)
        
        tk.Label(vendor_inner, text="Vendedor:", font=("Arial", 12), 
                bg='#f8f9fa', fg='#2c3e50').pack(side='left')
        
        self.vendor_entry = tk.Entry(vendor_inner, font=("Arial", 12), width=20)
        self.vendor_entry.pack(side='right')
        self.vendor_entry.insert(0, "API")  # Valor por defecto
        
        # Filtros de Ubicación
        location_frame = tk.LabelFrame(main_frame, text="🏢 Filtros de Ubicación", 
                                      font=("Arial", 14, "bold"), bg='#f8f9fa', fg='#34495e')
        location_frame.pack(fill='x', pady=15)
        
        # BaseDeDatos (origen)
        base_frame = tk.Frame(location_frame, bg='#f8f9fa')
        base_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(base_frame, text="📤 BaseDeDatos (origen):", font=("Arial", 12), 
                bg='#f8f9fa', fg='#2c3e50').pack(side='left')
        
        self.base_datos_entry = tk.Entry(base_frame, font=("Arial", 12), width=20)
        self.base_datos_entry.pack(side='right')
        # Dejar vacío por defecto
        
        # OrigenDestino (destino)
        destino_frame = tk.Frame(location_frame, bg='#f8f9fa')
        destino_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Label(destino_frame, text="📥 OrigenDestino (destino):", font=("Arial", 12), 
                bg='#f8f9fa', fg='#2c3e50').pack(side='left')
        
        self.origin_entry = tk.Entry(destino_frame, font=("Arial", 12), width=20)
        self.origin_entry.pack(side='right')
        self.origin_entry.insert(0, "MUNDOCAB")  # Valor por defecto
        
        # Separador
        separator = tk.Frame(location_frame, height=2, bg='#bdc3c7')
        separator.pack(fill='x', padx=20, pady=10)
        
        # Información sobre filtros
        info_frame = tk.Frame(location_frame, bg='#f8f9fa')
        info_frame.pack(fill='x', padx=20, pady=10)
        
        info_text = "💡 Puedes usar uno, ambos o ninguno. Ejemplos: DEPOSITO, MUNDOCAB, CABA, MUNDOAL, etc."
        tk.Label(info_frame, text=info_text, font=("Arial", 11), 
                bg='#f8f9fa', fg='#7f8c8d', wraplength=600).pack(anchor='w')
        
        # Botones
        buttons_frame = tk.Frame(self.filters_window, bg='#f8f9fa')
        buttons_frame.pack(side='bottom', fill='x', padx=40, pady=30)
        
        # Botón cancelar
        cancel_btn = tk.Button(
            buttons_frame,
            text="❌ Cancelar",
            font=("Arial", 14),
            bg='#e74c3c',
            fg='white',
            padx=30,
            pady=12,
            command=self.filters_window.destroy
        )
        cancel_btn.pack(side='right', padx=(15, 0))
        
        # Botón buscar
        search_btn = tk.Button(
            buttons_frame,
            text="🔍 Buscar Movimientos",
            font=("Arial", 14, "bold"),
            bg='#27ae60',
            fg='white',
            padx=30,
            pady=12,
            command=self.search_movements
        )
        search_btn.pack(side='right')
        
        # Ayuda
        help_frame = tk.Frame(main_frame, bg='#f8f9fa')
        help_frame.pack(fill='x', pady=(10, 0))
        
        help_text = """💡 Ayuda:
• Fechas en formato YYYY-MM-DD (ej: 2025-07-29)
• Vendedor: API, MEL, o cualquier otro
• BaseDeDatos: Filtro por origen (opcional)
• OrigenDestino: Filtro por destino (opcional)
• Puedes usar ambos filtros, solo uno, o ninguno"""
        
        help_label = tk.Label(
            help_frame,
            text=help_text,
            font=("Arial", 9),
            bg='#f8f9fa',
            fg='#7f8c8d',
            justify='left'
        )
        help_label.pack(anchor='w')
        
    def search_movements(self):
        """Busca movimientos con los filtros especificados"""
        # Validar fechas
        try:
            date_from = self.date_from.get().strip()
            date_to = self.date_to.get().strip()
            
            if not date_from or not date_to:
                messagebox.showerror("Error", "Por favor ingresa ambas fechas")
                return
                
            # Validar formato de fecha
            datetime.strptime(date_from, "%Y-%m-%d")
            datetime.strptime(date_to, "%Y-%m-%d")
            
        except ValueError:
            messagebox.showerror("Error", "Formato de fecha inválido. Use YYYY-MM-DD")
            return
        
        # Obtener otros filtros
        vendor = self.vendor_entry.get().strip()
        base_datos = self.base_datos_entry.get().strip()
        origin = self.origin_entry.get().strip()
        
        if not vendor:
            messagebox.showerror("Error", "Por favor ingresa un vendedor")
            return
            
        # Cerrar ventana de filtros
        self.filters_window.destroy()
        
        # Actualizar status
        self.status_label.config(
            text="🔄 Buscando movimientos...",
            fg='#f39c12'
        )
        self.root.update()
        
        # Buscar en hilo separado para no bloquear UI
        search_thread = threading.Thread(
            target=self.fetch_movements,
            args=(date_from, date_to, vendor, base_datos, origin)
        )
        search_thread.daemon = True
        search_thread.start()
        
    def fetch_movements(self, date_from: str, date_to: str, vendor: str, base_datos: str, origin: str):
        """Obtiene movimientos de la API"""
        try:
            # Construir URL con parámetros
            url = f"{self.api_base}/Movimientodestock/"
            
            params = {
                "vendedor": vendor,
                "Fecha": date_from,  # API parece usar una sola fecha
                "limit": 1000  # Límite alto para obtener todos
            }
            
            # Agregar BaseDeDatos si se especificó
            if base_datos:
                params["BaseDeDatos"] = base_datos
            
            # Agregar OrigenDestino si se especificó
            if origin:
                params["OrigenDestino"] = origin
            
            # Si hay rango de fechas, hacer múltiples consultas
            movements = []
            current_date = datetime.strptime(date_from, "%Y-%m-%d")
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                params["Fecha"] = date_str
                
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                
                if response.status_code == 200:
                    data = response.json()
                    if "Resultados" in data and data["Resultados"]:
                        movements.extend(data["Resultados"])
                elif response.status_code != 404:  # 404 es normal si no hay datos
                    print(f"Error en fecha {date_str}: {response.status_code}")
                
                current_date += timedelta(days=1)
            
            # Actualizar UI en hilo principal
            self.root.after(0, self.show_results, movements, date_from, date_to, vendor, base_datos, origin)
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Error de conexión: {str(e)}"
            self.root.after(0, self.show_error, error_msg)
        except Exception as e:
            error_msg = f"Error inesperado: {str(e)}"
            self.root.after(0, self.show_error, error_msg)
            
    def show_error(self, error_msg: str):
        """Muestra error en UI principal"""
        self.status_label.config(
            text=f"❌ {error_msg}",
            fg='#e74c3c'
        )
        messagebox.showerror("Error", error_msg)
        
    def show_results(self, movements: List[Dict], date_from: str, date_to: str, vendor: str, base_datos: str, origin: str):
        """Muestra los resultados en una nueva ventana"""
        self.status_label.config(
            text=f"✅ Encontrados {len(movements)} movimientos",
            fg='#27ae60'
        )
        
        if not movements:
            filters_text = f"Fechas: {date_from} - {date_to}\nVendedor: {vendor}"
            if base_datos:
                filters_text += f"\nBaseDeDatos: {base_datos}"
            if origin:
                filters_text += f"\nOrigenDestino: {origin}"
            
            messagebox.showinfo("Sin resultados", 
                              f"No se encontraron movimientos para:\n{filters_text}")
            return
            
        # Crear ventana de resultados
        results_window = tk.Toplevel(self.root)
        results_window.title(f"Movimientos de Stock - {len(movements)} resultados")
        results_window.geometry("1600x900")
        results_window.state('zoomed')  # Maximizar ventana de resultados
        results_window.configure(bg='#ffffff')
        
        self.setup_results_window(results_window, movements, date_from, date_to, vendor, base_datos, origin)
        
    def setup_results_window(self, window: tk.Toplevel, movements: List[Dict], 
                           date_from: str, date_to: str, vendor: str, base_datos: str, origin: str):
        """Configura la ventana de resultados"""
        # Título con filtros aplicados
        title_frame = tk.Frame(window, bg='#ffffff')
        title_frame.pack(fill='x', padx=10, pady=10)
        
        title_label = tk.Label(
            title_frame,
            text=f"📊 Movimientos de Stock ({len(movements)} resultados)",
            font=("Arial", 16, "bold"),
            bg='#ffffff',
            fg='#2c3e50'
        )
        title_label.pack()
        
        # Construir texto de filtros
        filters_text = f"Filtros: {date_from} - {date_to} | Vendedor: {vendor}"
        if base_datos:
            filters_text += f" | BaseDeDatos: {base_datos}"
        if origin:
            filters_text += f" | OrigenDestino: {origin}"
        
        filters_label = tk.Label(
            title_frame,
            text=filters_text,
            font=("Arial", 10),
            bg='#ffffff',
            fg='#7f8c8d'
        )
        filters_label.pack()
        
        # Frame para la tabla con scrollbars
        table_frame = tk.Frame(window, bg='#ffffff')
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Crear Treeview con scrollbars (ordenable)
        columns = ('Fecha/Hora', 'Código', 'De Dónde', 'A Dónde', 'Tipo', 'Motivo', 'Vendedor', 'Remito', 'Número', 'Artículos', 'Cantidad', 'Observación')
        
        tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=28)
        
        # Función para ordenar por columna
        def sort_treeview(col, reverse):
            # Obtener todos los elementos
            items = [(tree.set(child, col), child) for child in tree.get_children('')]
            
            # Ordenar especialmente para fechas
            if col == 'Fecha/Hora':
                def parse_date(date_str):
                    try:
                        # Intentar parsear fecha DD/MM/YYYY HH:MM
                        if ' ' in date_str:
                            fecha_parte, hora_parte = date_str.split(' ', 1)
                        else:
                            fecha_parte = date_str
                            hora_parte = '00:00'
                        
                        if '/' in fecha_parte:
                            dia, mes, año = fecha_parte.split('/')
                            return f"{año}-{mes.zfill(2)}-{dia.zfill(2)} {hora_parte}"
                        else:
                            return date_str
                    except:
                        return date_str
                
                items.sort(key=lambda x: parse_date(x[0]), reverse=reverse)
            else:
                # Ordenar normalmente para otras columnas
                items.sort(key=lambda x: x[0], reverse=reverse)
            
            # Reorganizar elementos en el treeview
            for index, (val, child) in enumerate(items):
                tree.move(child, '', index)
            
            # Cambiar el comando del header para la próxima vez
            tree.heading(col, command=lambda: sort_treeview(col, not reverse))
        
        # Configurar columnas con ordenamiento
        tree.heading('Fecha/Hora', text='📅 Fecha/Hora ↕️', command=lambda: sort_treeview('Fecha/Hora', False))
        tree.heading('Código', text='🔢 Código ↕️', command=lambda: sort_treeview('Código', False))
        tree.heading('De Dónde', text='📤 De Dónde ↕️', command=lambda: sort_treeview('De Dónde', False))
        tree.heading('A Dónde', text='📥 A Dónde ↕️', command=lambda: sort_treeview('A Dónde', False))
        tree.heading('Tipo', text='📋 Tipo ↕️', command=lambda: sort_treeview('Tipo', False))
        tree.heading('Motivo', text='💭 Motivo ↕️', command=lambda: sort_treeview('Motivo', False))
        tree.heading('Vendedor', text='👤 Vendedor ↕️', command=lambda: sort_treeview('Vendedor', False))
        tree.heading('Remito', text='📄 Remito ↕️', command=lambda: sort_treeview('Remito', False))
        tree.heading('Número', text='🔢 Número ↕️', command=lambda: sort_treeview('Número', False))
        tree.heading('Artículos', text='📦 Artículos ↕️', command=lambda: sort_treeview('Artículos', False))
        tree.heading('Cantidad', text='🔢 Cantidad ↕️', command=lambda: sort_treeview('Cantidad', False))

        tree.heading('Observación', text='📝 Observación ↕️', command=lambda: sort_treeview('Observación', False))
        
        # Ajustar anchos de columna
        tree.column('Fecha/Hora', width=140)
        tree.column('Código', width=100)
        tree.column('De Dónde', width=120)
        tree.column('A Dónde', width=120)
        tree.column('Tipo', width=60)
        tree.column('Motivo', width=120)
        tree.column('Vendedor', width=80)
        tree.column('Remito', width=100)
        tree.column('Número', width=80)
        tree.column('Artículos', width=300)
        tree.column('Cantidad', width=80)

        tree.column('Observación', width=150)
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Posicionar elementos
        tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # Llenar datos
        for movement in movements:
            # Procesar artículos y cantidades
            articles_text = ""
            total_quantity = 0
            
            if "MovimientoDetalle" in movement and movement["MovimientoDetalle"]:
                articles = []
                for detail in movement["MovimientoDetalle"]:
                    # Nombre del artículo con detalles
                    article_name = detail.get('Articulo', '')
                    if detail.get('ArticuloDetalle'):
                        article_name = detail.get('ArticuloDetalle')
                    
                    article_info = article_name
                    if detail.get('Color'):
                        article_info += f" ({detail.get('Color')})"
                    if detail.get('Talle'):
                        article_info += f" T:{detail.get('Talle')}"
                    
                    articles.append(article_info.strip())
                    
                    # Sumar cantidad total
                    if detail.get('Cantidad'):
                        total_quantity += detail.get('Cantidad', 0)
                
                articles_text = " | ".join(articles)
            
            # Procesar fecha y hora en formato legible
            fecha_completa = ""
            if movement.get('Fecha'):
                try:
                    # Usar fecha tal como viene de la API
                    fecha_completa = movement.get('Fecha')
                    
                    # Agregar hora si está disponible y formatearla
                    if (movement.get('InformacionAdicional') and 
                        movement['InformacionAdicional'].get('HoraAltaFW')):
                        hora_raw = movement['InformacionAdicional']['HoraAltaFW']
                        
                        if ':' in hora_raw:
                            # Ya está formateada
                            fecha_completa += f" {hora_raw}"
                        elif len(hora_raw) >= 4:
                            # Formatear hora desde formato HHMMSS o HHMM
                            hh = hora_raw[:2]
                            mm = hora_raw[2:4] if len(hora_raw) >= 4 else '00'
                            ss = hora_raw[4:6] if len(hora_raw) >= 6 else '00'
                            fecha_completa += f" {hh}:{mm}:{ss}"
                        else:
                            fecha_completa += f" {hora_raw}"
                except Exception as e:
                    # Si hay error en el formato, usar el original
                    fecha_completa = movement.get('Fecha', '')
            
            # Lógica SIMPLE: De Dónde = BaseDeDatos, A Dónde = OrigenDestino
            
            # Obtener BaseDeDatos de InformacionAdicional si está disponible
            base_datos_origen = ""
            if movement.get('InformacionAdicional'):
                base_datos_origen = movement['InformacionAdicional'].get('BaseDeDatosAltaFW', '')
            
            # Si no hay BaseDeDatos en InformacionAdicional, usar el filtro aplicado
            if not base_datos_origen:
                # Usar el valor del filtro BaseDeDatos si se aplicó
                base_datos_origen = base_datos if base_datos else "Sistema"
            
            # DE DÓNDE = BaseDeDatos (origen)
            de_donde = f"📤 {base_datos_origen}" if base_datos_origen else "📤 Sistema"
            
            # A DÓNDE = OrigenDestino (destino)
            origen_destino = movement.get('OrigenDestino', '')
            a_donde = f"📥 {origen_destino}" if origen_destino else "📥 No especificado"
            
            # Insertar fila
            tree.insert('', 'end', values=(
                fecha_completa,
                movement.get('Codigo', ''),
                de_donde,
                a_donde,
                movement.get('Tipo', ''),
                movement.get('Motivo', ''),
                movement.get('vendedor', ''),
                movement.get('Remito', ''),
                movement.get('Numero', ''),
                articles_text,
                total_quantity if total_quantity > 0 else '',
                movement.get('Observacion', '')
            ))
        
        # Botón para cerrar
        close_btn = tk.Button(
            window,
            text="✅ Cerrar",
            font=("Arial", 12),
            bg='#95a5a6',
            fg='white',
            padx=20,
            pady=10,
            command=window.destroy
        )
        close_btn.pack(pady=10)
        
        # Doble click para ver detalles
        def show_detail(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                index = tree.index(selection[0])
                movement = movements[index]
                self.show_movement_detail(movement)
        
        tree.bind('<Double-1>', show_detail)
        
    def show_movement_detail(self, movement: Dict):
        """Muestra detalles completos de un movimiento"""
        detail_window = tk.Toplevel(self.root)
        detail_window.title("Detalle del Movimiento")
        detail_window.geometry("600x500")
        detail_window.configure(bg='#f8f9fa')
        
        # Crear área de texto con scroll
        text_frame = tk.Frame(detail_window, bg='#f8f9fa')
        text_frame.pack(fill='both', expand=True, padx=20, pady=20)
        
        text_widget = tk.Text(text_frame, wrap='word', font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        
        text_widget.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Formatear y mostrar datos
        detail_text = json.dumps(movement, indent=2, ensure_ascii=False)
        text_widget.insert('1.0', detail_text)
        text_widget.config(state='disabled')
        
        # Botón cerrar
        close_btn = tk.Button(
            detail_window,
            text="Cerrar",
            command=detail_window.destroy,
            bg='#95a5a6',
            fg='white',
            padx=20,
            pady=5
        )
        close_btn.pack(pady=10)
        
    def run(self):
        """Ejecuta la aplicación"""
        self.root.mainloop()

if __name__ == "__main__":
    app = StockMovementsViewer()
    app.run()
