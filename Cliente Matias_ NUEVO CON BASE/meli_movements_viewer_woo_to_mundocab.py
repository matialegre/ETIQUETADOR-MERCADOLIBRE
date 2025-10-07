#!/usr/bin/env python3
# ────────────────────────────────────────────────────────────────
#  meli_movements_viewer_woo_to_mundocab.py
#  Visor especializado para movimientos BASE=WOO → DESTINO=MUNDOCAB
#  Filtros predeterminados: BaseDeDatosAltaFW=WOO, OrigenDestino=MUNDOCAB, Fecha seleccionada
# ────────────────────────────────────────────────────────────────

import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
from datetime import datetime, timedelta
import threading
from typing import List, Dict

class WooToMundocabViewer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Visor de Movimientos WOO → MUNDOCAB")
        self.root.geometry("1400x900")
        try:
            self.root.state('zoomed')  # Maximizar ventana en Windows
        except Exception:
            pass
        self.root.configure(bg='#f0f0f0')
        
        # Configuración de la API
        self.api_base = "http://190.211.201.217:8888/api.Dragonfish"
        self.headers = {
            "accept": "application/json",
            "Authorization": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE4MTc5ODg0ODQsInVzdWFyaW8iOiJhZG1pbiIsInBhc3N3b3JkIjoiMDE5NGRkMGEyYjA2Yzc4Yzc5YmUxZThjMDQ3ZmFkNTgyZTM2NzJlMzQ0NWFlYzRlODMwMDFiNDdlNGE4MWQwMyJ9.zAWCBxY5smFLyDrNAPqeaaoOJbmG-R-SM7mFFg7MQeE",
            "IdCliente": "MATIAPP",
            "BaseDeDatos": "WOO"
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
            text="🛒 VISOR MOVIMIENTOS WOO → MUNDOCAB",
            font=("Arial", 22, "bold"),
            bg='#f0f0f0',
            fg='#e74c3c'
        )
        title_label.pack()
        
        subtitle_label = tk.Label(
            title_frame,
            text="Filtros automáticos: BASE=WOO → DESTINO=MUNDOCAB | FECHA SELECCIONADA",
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
            text="🔒 FILTROS FIJOS: BaseDeDatosAltaFW=WOO | OrigenDestino=MUNDOCAB",
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
            text=f"Listo para buscar movimientos WOO → MUNDOCAB del {self.current_date.strftime('%d/%m/%Y')}",
            font=("Arial", 11),
            bg='#f0f0f0',
            fg='#7f8c8d'
        )
        self.status_label.pack(pady=10)
        
    def previous_day(self):
        self.current_date -= timedelta(days=1)
        self.update_date_display()
        
    def next_day(self):
        self.current_date += timedelta(days=1)
        self.update_date_display()
        
    def update_date_display(self):
        self.date_label.config(text=self.current_date.strftime("%d/%m/%Y"))
        date_str = self.current_date.strftime("%d/%m/%Y")
        self.status_label.config(text=f"Listo para buscar movimientos WOO → MUNDOCAB del {date_str}")
        
    def search_current_date_movements(self):
        date_str = self.current_date.strftime("%Y-%m-%d")
        self.status_label.config(text=f"🔍 Buscando movimientos WOO → MUNDOCAB del {self.current_date.strftime('%d/%m/%Y')}...")
        self.root.update()
        threading.Thread(target=self.fetch_movements, args=(date_str, date_str), daemon=True).start()
    
    def fetch_movements(self, date_from, date_to):
        try:
            all_movements = []
            current_date = datetime.strptime(date_from, "%Y-%m-%d")
            end_date = datetime.strptime(date_to, "%Y-%m-%d")
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                params = {
                    "Fecha": date_str,
                    "limit": 1000
                }
                response = requests.get(
                    f"{self.api_base}/Movimientodestock/",
                    params=params,
                    headers=self.headers,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                movements = data.get("Resultados", [])
                filtered_movements = []
                
                for movement in movements:
                    origen_destino = str(movement.get('OrigenDestino', '')).upper()
                    base_datos_mov = ''
                    if movement.get('InformacionAdicional'):
                        base_datos_mov = str(movement['InformacionAdicional'].get('BaseDeDatosAltaFW', '')).upper()
                    
                    destino_ok = origen_destino == 'MUNDOCAB'
                    base_ok = base_datos_mov == 'WOO'
                    
                    if destino_ok and base_ok:
                        filtered_movements.append(movement)
                
                all_movements.extend(filtered_movements)
                current_date += timedelta(days=1)
            
            self.root.after(0, self.show_results, all_movements, date_from, date_to)
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error al obtener movimientos: {e}"))
            self.root.after(0, lambda: self.status_label.config(text="Error en la búsqueda"))
    
    def show_results(self, movements, date_from, date_to):
        if not movements:
            messagebox.showinfo("Sin resultados", "No se encontraron movimientos WOO → MUNDOCAB para la fecha especificada.")
            self.status_label.config(text="Sin resultados encontrados")
            return
        
        results_window = tk.Toplevel(self.root)
        results_window.title(f"Movimientos WOO → MUNDOCAB - {len(movements)} resultados")
        results_window.geometry("1600x900")
        try:
            results_window.state('zoomed')
        except Exception:
            pass
        results_window.configure(bg='#ffffff')
        
        title_frame = tk.Frame(results_window, bg='#ffffff')
        title_frame.pack(fill='x', padx=10, pady=10)
        
        title_label = tk.Label(
            title_frame,
            text=f"🛒 Movimientos WOO → MUNDOCAB ({len(movements)} resultados)",
            font=("Arial", 18, "bold"),
            bg='#ffffff',
            fg='#e74c3c'
        )
        title_label.pack()
        
        filters_text = f"📅 Fecha: {date_from} | 🏢 WOO → MUNDOCAB"
        filters_label = tk.Label(
            title_frame,
            text=filters_text,
            font=("Arial", 12),
            bg='#ffffff',
            fg='#7f8c8d'
        )
        filters_label.pack()
        
        table_frame = tk.Frame(results_window, bg='#ffffff')
        table_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        columns = ('Fecha/Hora', 'Número', 'Código', 'Artículo', 'Motivo', 'Vendedor', 'Observación')
        tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=20)
        
        tree.heading('Fecha/Hora', text='📅 Fecha/Hora')
        tree.heading('Número', text='🔢 Número')
        tree.heading('Código', text='🔢 Código')
        tree.heading('Artículo', text='📦 Artículo')
        tree.heading('Motivo', text='💭 Motivo')
        tree.heading('Vendedor', text='👤 Vendedor')
        tree.heading('Observación', text='📝 Observación')
        
        tree.column('Fecha/Hora', width=140)
        tree.column('Número', width=100)
        tree.column('Código', width=100)
        tree.column('Artículo', width=300)
        tree.column('Motivo', width=80)
        tree.column('Vendedor', width=80)
        tree.column('Observación', width=400)
        
        v_scrollbar = ttk.Scrollbar(table_frame, orient='vertical', command=tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        for movement in movements:
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
            
            article_name = ""
            if movement.get("MovimientoDetalle"):
                first_detail = movement["MovimientoDetalle"][0]
                article_name = first_detail.get('ArticuloDetalle', '')
                if len(movement["MovimientoDetalle"]) > 1:
                    article_name += f" (+{len(movement['MovimientoDetalle'])-1} más)"
            
            tree.insert('', 'end', values=(
                fecha_completa,
                movement.get('Numero', ''),
                movement.get('Codigo', ''),
                article_name,
                movement.get('Motivo', ''),
                movement.get('vendedor', ''),
                movement.get('Observacion', '')
            ))
        
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
        
        self.status_label.config(text=f"✅ {len(movements)} movimientos WOO → MUNDOCAB encontrados")
    
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = WooToMundocabViewer()
    app.run()
