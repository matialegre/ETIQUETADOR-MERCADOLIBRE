#!/usr/bin/env python3
# ────────────────────────────────────────────────────────────────
#  meli_movements_viewer.py
#  Visor especializado para movimientos DEPOSITO → MELI
#  Filtros predeterminados: BaseDeDatos=DEPOSITO, OrigenDestino=MELI
#  Motivo=API, Vendedor=API, Tipo=SALIDA, Fecha=HOY
# ────────────────────────────────────────────────────────────────

import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
from datetime import datetime, timedelta
import threading
from typing import List, Dict

class MeliMovementsViewer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Visor de Movimientos DEPOSITO → MELI")
        self.root.geometry("1400x900")
        self.root.state('zoomed')  # Maximizar ventana en Windows
        self.root.configure(bg='#f0f0f0')
        
        # Configuración de la API
        self.api_base = "http://190.211.201.217:8888/api.Dragonfish"
        self.headers = {
            "accept": "application/json",
            "Authorization": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE4MTc5ODg0ODQsInVzdWFyaW8iOiJhZG1pbiIsInBhc3N3b3JkIjoiMDE5NGRkMGEyYjA2Yzc4Yzc5YmUxZThjMDQ3ZmFkNTgyZTM2NzJlMzQ0NWFlYzRlODMwMDFiNDdlNGE4MWQwMyJ9.zAWCBxY5smFLyDrNAPqeaaoOJbmG-R-SM7mFFg7MQeE",
            "IdCliente": "PRUEBA-WEB",
            "BaseDeDatos": "DEPOSITO"  # Cambiar a DEPOSITO para buscar movimientos que salen del depósito
        }
        
        # Fecha actual para navegación
        self.current_date = datetime.now()

        self.setup_main_window()
        
    def setup_main_window(self):
        """Configura la ventana principal"""
        # Título principal
        title_frame = tk.Frame(self.root, bg='#f0f0f0')
        title_frame.pack(pady=20)
        
        title_label = tk.Label(
            title_frame,
            text="🛒 VISOR MOVIMIENTOS DEPOSITO → MELI",
            font=("Arial", 22, "bold"),
            bg='#f0f0f0',
            fg='#e74c3c'
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            title_frame,
            text="Filtros automáticos: DEPOSITO → MELI | API | SALIDA | HOY",
            font=("Arial", 14),
            bg='#f0f0f0',
            fg='#7f8c8d'
        )
        subtitle_label.pack(pady=(5, 0))
        
        # Frame para información de filtros fijos
        info_frame = tk.Frame(self.root, bg='#ecf0f1', relief='raised', bd=2)
        info_frame.pack(fill='x', padx=50, pady=10)
        
        info_label = tk.Label(
            info_frame,
            text="🔒 FILTROS FIJOS: BaseDeDatos=DEPOSITO | OrigenDestino=MELI | Vendedor=API | Motivo=API | Tipo=SALIDA",
            font=("Arial", 12, "bold"),
            bg='#ecf0f1',
            fg='#2c3e50',
            pady=10
        )
        info_label.pack()
        
        # Frame principal para los controles
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(expand=True, fill='both', padx=50, pady=30)
        
        # Frame para navegación de fechas
        date_nav_frame = tk.Frame(main_frame, bg='#f0f0f0')
        date_nav_frame.pack(pady=20)
        
        # Botón día anterior
        prev_btn = tk.Button(
            date_nav_frame,
            text="◀ Día Anterior",
            font=("Arial", 14, "bold"),
            bg='#3498db',
            fg='white',
            padx=20,
            pady=10,
            command=self.previous_day,
            cursor='hand2'
        )
        prev_btn.pack(side='left', padx=10)
        
        # Label de fecha actual
        self.date_label = tk.Label(
            date_nav_frame,
            text=self.current_date.strftime("%d/%m/%Y"),
            font=("Arial", 16, "bold"),
            bg='#f0f0f0',
            fg='#2c3e50',
            padx=30
        )
        self.date_label.pack(side='left', padx=20)
        
        # Botón día siguiente
        next_btn = tk.Button(
            date_nav_frame,
            text="Día Siguiente ▶",
            font=("Arial", 14, "bold"),
            bg='#3498db',
            fg='white',
            padx=20,
            pady=10,
            command=self.next_day,
            cursor='hand2'
        )
        next_btn.pack(side='left', padx=10)
        
        # Botón principal
        self.main_button = tk.Button(
            main_frame,
            text="🔍 VER MOVIMIENTOS",
            font=("Arial", 18, "bold"),
            bg='#e74c3c',
            fg='white',
            relief='raised',
            bd=4,
            padx=40,
            pady=20,
            command=self.search_current_date_movements,
            cursor='hand2'
        )
        self.main_button.pack(pady=30)
        
        # Status
        self.status_label = tk.Label(
            self.root,
            text=f"Listo para buscar movimientos DEPOSITO → MELI del {self.current_date.strftime('%d/%m/%Y')}",
            font=("Arial", 11),
            bg='#f0f0f0',
            fg='#7f8c8d'
        )
        self.status_label.pack(pady=10)
        
    def previous_day(self):
        """Navega al día anterior"""
        self.current_date -= timedelta(days=1)
        self.update_date_display()
        
    def next_day(self):
        """Navega al día siguiente"""
        self.current_date += timedelta(days=1)
        self.update_date_display()
        
    def update_date_display(self):
        """Actualiza la visualización de la fecha"""
        self.date_label.config(text=self.current_date.strftime("%d/%m/%Y"))
        # Actualizar el texto del status
        date_str = self.current_date.strftime("%d/%m/%Y")
        self.status_label.config(text=f"Listo para buscar movimientos DEPOSITO → MELI del {date_str}")
        
    def search_current_date_movements(self):
        """Busca movimientos para la fecha actual seleccionada"""
        date_str = self.current_date.strftime("%Y-%m-%d")
        
        self.status_label.config(text=f"🔍 Buscando movimientos DEPOSITO → MELI del {self.current_date.strftime('%d/%m/%Y')}...")
        self.root.update()
        
        # Ejecutar búsqueda en hilo separado
        threading.Thread(
            target=self.fetch_movements,
            args=(date_str, date_str, "API", "MELI"),
            daemon=True
        ).start()
    
    def search_today_movements(self):
        """Busca movimientos con filtros fijos para hoy"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        self.status_label.config(text="🔍 Buscando movimientos DEPOSITO → MELI...")
        self.root.update()
        
        # Ejecutar búsqueda en hilo separado
        threading.Thread(
            target=self.fetch_movements,
            args=(today, today, "API", "MELI"),
            daemon=True
        ).start()
        
    def fetch_movements(self, date_from, date_to, vendor, origen_destino):
        """Obtiene movimientos de la API con filtros específicos"""
        try:
            all_movements = []
            current_date = datetime.strptime(date_from, "%Y-%m-%d")
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                
                # Parámetros para buscar movimientos DEPOSITO → MELI
                # Según el código: OrigenDestino="MELI", Tipo=2, BaseDeDatosAltaFW="MELI"
                params = {
                    "Fecha": date_str,
                    "vendedor": vendor,
                    "OrigenDestino": origen_destino,  # "MELI"
                    "limit": 1000
                    # No filtrar por BaseDeDatos en la API, sino internamente
                }
                
                try:
                    response = requests.get(
                        f"{self.api_base}/Movimientodestock/",
                        params=params,
                        headers=self.headers,
                        timeout=30
                    )
                    response.raise_for_status()
                    data = response.json()
                    
                    # Procesar todos los movimientos del día
                    movements = data.get("Resultados", [])
                    filtered_movements = []
                    
                    print(f"\n=== DEBUG FECHA {date_str} ===")
                    print(f"Total movimientos recibidos: {len(movements)}")
                    
                    for i, movement in enumerate(movements):
                        motivo = str(movement.get('Motivo', '')).upper()
                        tipo = movement.get('Tipo', 0)  # Tipo es numérico: 2=Salida, 1=Entrada
                        vendedor_mov = str(movement.get('vendedor', '')).upper()
                        origen_destino = str(movement.get('OrigenDestino', '')).upper()
                        
                        # Obtener BaseDeDatos del movimiento
                        base_datos_movimiento = ""
                        if movement.get('InformacionAdicional'):
                            base_datos_movimiento = str(movement['InformacionAdicional'].get('BaseDeDatosAltaFW', '')).upper()
                        
                        # Debug: mostrar los primeros 5 movimientos
                        if i < 5:
                            print(f"\nMovimiento {i+1}:")
                            print(f"  Motivo: '{motivo}'")
                            print(f"  Tipo: {tipo} (2=Salida, 1=Entrada)")
                            print(f"  Vendedor: '{vendedor_mov}'")
                            print(f"  OrigenDestino: '{origen_destino}'")
                            print(f"  BaseDeDatosAltaFW: '{base_datos_movimiento}'")
                        
                        # Filtros correctos para DEPOSITO → MELI:
                        # - Motivo: "API"
                        # - Tipo: 2 (Salida)
                        # - Vendedor: "API" 
                        # - OrigenDestino: "MELI"
                        # - BaseDeDatosAltaFW: "DEPOSITO" (indica que sale del DEPOSITO)
                        motivo_ok = motivo == 'API'
                        tipo_ok = tipo == 2  # 2 = Salida (DEPOSITO → MELI)
                        vendedor_ok = vendedor_mov == 'API'
                        destino_ok = origen_destino == 'MELI'
                        base_ok = base_datos_movimiento == 'DEPOSITO'  # Sale del DEPOSITO
                        
                        if motivo_ok and tipo_ok and vendedor_ok and destino_ok and base_ok:
                            filtered_movements.append(movement)
                            if i < 5:
                                print(f"  ✓ INCLUIDO")
                        elif i < 5:
                            print(f"  ✗ EXCLUIDO - motivo:{motivo_ok}, tipo:{tipo_ok}, vendedor:{vendedor_ok}, destino:{destino_ok}, base:{base_ok}")
                    
                    print(f"Movimientos filtrados: {len(filtered_movements)}")
                    
                    all_movements.extend(filtered_movements)
                    
                except requests.RequestException as e:
                    print(f"Error en fecha {date_str}: {e}")
                    continue
                
                current_date += timedelta(days=1)
            
            # Actualizar UI en el hilo principal
            self.root.after(0, self.show_results, all_movements, date_from, date_to)
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error al obtener movimientos: {e}"))
            self.root.after(0, lambda: self.status_label.config(text="Error en la búsqueda"))
    
    def show_results(self, movements, date_from, date_to):
        """Muestra los resultados en una nueva ventana"""
        if not movements:
            messagebox.showinfo("Sin resultados", "No se encontraron movimientos DEPOSITO → MELI para la fecha especificada.")
            self.status_label.config(text="Sin resultados encontrados")
            return
        
        # Crear ventana de resultados
        results_window = tk.Toplevel(self.root)
        results_window.title(f"Movimientos DEPOSITO → MELI - {len(movements)} resultados")
        results_window.geometry("1600x900")
        results_window.state('zoomed')
        results_window.configure(bg='#ffffff')
        
        # Título
        title_frame = tk.Frame(results_window, bg='#ffffff')
        title_frame.pack(fill='x', padx=10, pady=10)
        
        title_label = tk.Label(
            title_frame,
            text=f"🛒 Movimientos DEPOSITO → MELI ({len(movements)} resultados)",
            font=("Arial", 18, "bold"),
            bg='#ffffff',
            fg='#e74c3c'
        )
        title_label.pack()
        
        # Información de filtros aplicados
        filters_text = f"📅 Fecha: {date_from} | 🏢 DEPOSITO → MELI | 👤 API | 📋 SALIDA"
        filters_label = tk.Label(
            title_frame,
            text=filters_text,
            font=("Arial", 12),
            bg='#ffffff',
            fg='#7f8c8d'
        )
        filters_label.pack()
        
        # Frame para la tabla
        table_frame = tk.Frame(results_window, bg='#ffffff')
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Crear Treeview
        columns = ('Fecha/Hora', 'Número', 'Código', 'Artículo', 'Motivo', 'Vendedor', 'Observación')
        tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
        
        # Configurar headers
        tree.heading('Fecha/Hora', text='📅 Fecha/Hora')
        tree.heading('Número', text='🔢 Número')
        tree.heading('Código', text='🔢 Código')
        tree.heading('Artículo', text='📦 Artículo')
        tree.heading('Motivo', text='💭 Motivo')
        tree.heading('Vendedor', text='👤 Vendedor')
        tree.heading('Observación', text='📝 Observación')
        
        # Configurar anchos
        tree.column('Fecha/Hora', width=140)
        tree.column('Número', width=100)
        tree.column('Código', width=100)
        tree.column('Artículo', width=300)
        tree.column('Motivo', width=80)
        tree.column('Vendedor', width=80)
        tree.column('Observación', width=400)
        
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
            # Procesar fecha y hora
            fecha_completa = ""
            if movement.get('Fecha'):
                fecha_completa = movement.get('Fecha')
                if (movement.get('InformacionAdicional') and 
                    movement['InformacionAdicional'].get('HoraAltaFW')):
                    hora_raw = movement['InformacionAdicional']['HoraAltaFW']
                    if ':' in hora_raw:
                        fecha_completa += f" {hora_raw}"
                    elif len(hora_raw) >= 4:
                        hh = hora_raw[:2]
                        mm = hora_raw[2:4] if len(hora_raw) >= 4 else '00'
                        ss = hora_raw[4:6] if len(hora_raw) >= 6 else '00'
                        fecha_completa += f" {hh}:{mm}:{ss}"
            
            # Procesar artículos - obtener nombre del primer artículo
            article_name = ""
            
            if "MovimientoDetalle" in movement and movement["MovimientoDetalle"]:
                first_detail = movement["MovimientoDetalle"][0]
                article_name = first_detail.get('ArticuloDetalle', '')
                
                # Si hay múltiples artículos, agregar indicador
                if len(movement["MovimientoDetalle"]) > 1:
                    article_name += f" (+{len(movement['MovimientoDetalle'])-1} más)"
            
            # Insertar fila
            tree.insert('', 'end', values=(
                fecha_completa,
                movement.get('Numero', ''),
                movement.get('Codigo', ''),
                article_name,
                movement.get('Motivo', ''),
                movement.get('vendedor', ''),
                movement.get('Observacion', '')
            ))
        
        # Botón para cerrar
        close_btn = tk.Button(
            results_window,
            text="✅ Cerrar",
            font=("Arial", 14),
            bg='#95a5a6',
            fg='white',
            padx=30,
            pady=15,
            command=results_window.destroy
        )
        close_btn.pack(pady=15)
        
        # Funciones para copiar números
        def copy_movement_number():
            selection = tree.selection()
            if selection:
                index = tree.index(selection[0])
                movement = movements[index]
                numero = str(movement.get('Numero', ''))
                if numero:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(numero)
                    self.status_label.config(text=f"📋 Copiado número de movimiento: {numero}")
        
        def copy_meli_number():
            selection = tree.selection()
            if selection:
                index = tree.index(selection[0])
                movement = movements[index]
                observacion = movement.get('Observacion', '')
                # Buscar patrón "MELI API 2000..."
                import re
                match = re.search(r'MELI API (\d+)', observacion)
                if match:
                    meli_number = match.group(1)
                    self.root.clipboard_clear()
                    self.root.clipboard_append(meli_number)
                    self.status_label.config(text=f"📋 Copiado número MELI: {meli_number}")
                else:
                    self.status_label.config(text="❌ No se encontró número MELI en la observación")
        
        # Menú contextual
        context_menu = tk.Menu(self.root, tearoff=0)
        context_menu.add_command(label="📋 Copiar Número de Movimiento", command=copy_movement_number)
        context_menu.add_command(label="📋 Copiar Número MELI", command=copy_meli_number)
        context_menu.add_separator()
        context_menu.add_command(label="📄 Ver Detalles", command=lambda: show_detail(None))
        
        def show_context_menu(event):
            # Seleccionar el item bajo el cursor
            item = tree.identify_row(event.y)
            if item:
                tree.selection_set(item)
                context_menu.post(event.x_root, event.y_root)
        
        # Doble click para ver detalles
        def show_detail(event):
            selection = tree.selection()
            if selection:
                item = tree.item(selection[0])
                index = tree.index(selection[0])
                movement = movements[index]
                self.show_movement_detail(movement)
        
        tree.bind('<Double-1>', show_detail)
        tree.bind('<Button-3>', show_context_menu)  # Clic derecho
        
        # Actualizar status
        self.status_label.config(text=f"✅ {len(movements)} movimientos DEPOSITO → MELI encontrados")
    
    def show_movement_detail(self, movement):
        """Muestra detalles completos del movimiento"""
        detail_window = tk.Toplevel(self.root)
        detail_window.title("Detalle del Movimiento")
        detail_window.geometry("800x600")
        detail_window.configure(bg='#f8f9fa')
        
        # Título
        title_label = tk.Label(
            detail_window,
            text="📋 Detalle Completo del Movimiento",
            font=("Arial", 16, "bold"),
            bg='#f8f9fa',
            fg='#2c3e50'
        )
        title_label.pack(pady=10)
        
        # Área de texto con scroll
        text_frame = tk.Frame(detail_window)
        text_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        text_area = tk.Text(text_frame, wrap='word', font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=text_area.yview)
        text_area.configure(yscrollcommand=scrollbar.set)
        
        # Mostrar JSON formateado
        json_text = json.dumps(movement, indent=2, ensure_ascii=False)
        text_area.insert('1.0', json_text)
        text_area.config(state='disabled')
        
        text_area.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        
        # Botón cerrar
        close_btn = tk.Button(
            detail_window,
            text="Cerrar",
            command=detail_window.destroy,
            font=("Arial", 12),
            bg='#95a5a6',
            fg='white',
            padx=20,
            pady=10
        )
        close_btn.pack(pady=10)

    def run(self):
        """Ejecuta la aplicación"""
        self.root.mainloop()

if __name__ == "__main__":
    app = MeliMovementsViewer()
    app.run()
