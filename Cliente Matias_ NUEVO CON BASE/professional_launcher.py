#!/usr/bin/env python3
"""
🚀 PROFESSIONAL LAUNCHER - Mundo Outdoor
Launcher profesional con menús desplegables y diseño moderno
"""

import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import sys
import os
import json
from pathlib import Path
from PIL import Image, ImageTk

class ProfessionalLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🏔️ MUNDO OUTDOOR - Launcher Profesional")
        
        # Pantalla completa
        self.root.state('zoomed')  # Windows fullscreen
        self.root.resizable(True, True)
        
        # Configurar estilo
        self.setup_style()
        
        # Centrar ventana
        self.center_window()
        
        # Cargar configuración
        self.load_config()
        
        # Crear interfaz
        self.create_interface()
    
    def setup_style(self):
        """Configurar el estilo de la aplicación."""
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configurar colores personalizados
        self.style.configure('Title.TLabel', 
                           font=('Arial', 24, 'bold'),
                           foreground='#1e3a8a',
                           background='white')
        
        self.style.configure('Menu.TButton',
                           font=('Arial', 12, 'bold'),
                           padding=(20, 10))
        
        self.style.configure('App.TButton',
                           font=('Arial', 10),
                           padding=(10, 5))
    
    def center_window(self):
        """Configurar ventana para pantalla completa."""
        # Ya está en pantalla completa, no necesita centrar
        pass
    
    def load_config(self):
        """Cargar configuración desde archivo JSON."""
        config_file = Path(__file__).parent / "launcher_config.json"
        
        # Configuración por defecto
        default_config = {
            "deposito": [
                {"name": "Cliente CABA", "exe": "Cliente_Matias_GUI_v3_CABA.exe"},
                {"name": "Cliente DEPÓSITO", "exe": "Cliente_Matias_GUI_v3_DEPOSITO.exe"},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""}
            ],
            "seguimientos": [
                {"name": "Visor Movimientos CABA", "exe": "VisorMovimientoCABA.exe"},
                {"name": "Visor Movimientos DEPÓSITO", "exe": "VisorMovimientosDEPOSITO.exe"},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""}
            ],
            "monitoreo": [
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""}
            ],
            "comunicacion": [
                {"name": "Chat Cliente Simple", "exe": "ChatClienteSimple_MundoOutdoor.exe"},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""}
            ],
            "test": [
                {"name": "Test Stock Movement CABA", "exe": "Test_Stock_Movement_CABA.exe"},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""}
            ],
            "ayuda": [
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""},
                {"name": "", "exe": ""}
            ]
        }
        
        try:
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = default_config
                self.save_config()
        except Exception as e:
            print(f"Error cargando configuración: {e}")
            self.config = default_config
    
    def save_config(self):
        """Guardar configuración en archivo JSON."""
        config_file = Path(__file__).parent / "launcher_config.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error guardando configuración: {e}")
    
    def create_interface(self):
        """Crear la interfaz principal."""
        # Frame principal con imagen de fondo
        self.main_frame = tk.Frame(self.root, bg='white')
        self.main_frame.pack(fill='both', expand=True)
        
        # Cargar imagen de fondo
        self.load_background()
        
        # Crear barra de menú superior
        self.create_menu_bar()
        
        # Crear área de contenido
        self.create_content_area()
        
        # Mostrar depósito por defecto
        self.show_category('deposito')
    
    def load_background(self):
        """Cargar imagen de fondo."""
        try:
            # Intentar cargar background.png
            bg_path = Path(__file__).parent / "background.png"
            if bg_path.exists():
                # Obtener tamaño de pantalla
                self.root.update_idletasks()
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                
                # Cargar y redimensionar imagen a pantalla completa
                image = Image.open(bg_path)
                image = image.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
                self.bg_image = ImageTk.PhotoImage(image)
                
                # Crear label con imagen de fondo
                bg_label = tk.Label(self.main_frame, image=self.bg_image)
                bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            else:
                # Si no hay imagen, usar color sólido
                self.main_frame.configure(bg='#f0f8ff')
        except Exception as e:
            print(f"Error cargando imagen de fondo: {e}")
            self.main_frame.configure(bg='#f0f8ff')
    
    def create_menu_bar(self):
        """Crear barra de menú superior."""
        menu_frame = tk.Frame(self.main_frame, bg='white', height=80)
        menu_frame.pack(fill='x', padx=20, pady=20)
        menu_frame.pack_propagate(False)
        
        # Título
        title_label = tk.Label(menu_frame, 
                              text="🏔️ MUNDO OUTDOOR - LAUNCHER",
                              font=('Arial', 20, 'bold'),
                              fg='#1e3a8a',
                              bg='white')
        title_label.pack(pady=10)
        
        # Frame para botones de menú
        buttons_frame = tk.Frame(menu_frame, bg='white')
        buttons_frame.pack(fill='x', pady=5)
        
        # Botones de menú
        menu_items = [
            ('Depósito', 'deposito'),
            ('Seguimientos', 'seguimientos'),
            ('Monitoreo', 'monitoreo'),
            ('Comunicación', 'comunicacion'),
            ('Test', 'test'),
            ('Ayuda', 'ayuda')
        ]
        
        for text, category in menu_items:
            btn = tk.Button(buttons_frame,
                           text=text,
                           font=('Arial', 12, 'bold'),
                           bg='#3b82f6',
                           fg='white',
                           relief='flat',
                           padx=20,
                           pady=8,
                           cursor='hand2',
                           command=lambda c=category: self.show_category(c))
            btn.pack(side='left', padx=5)
            
            # Efecto hover
            def on_enter(e, button=btn):
                button.configure(bg='#2563eb')
            def on_leave(e, button=btn):
                button.configure(bg='#3b82f6')
            
            btn.bind("<Enter>", on_enter)
            btn.bind("<Leave>", on_leave)
    
    def create_content_area(self):
        """Crear área de contenido."""
        # Frame para contenido con fondo semi-transparente
        self.content_frame = tk.Frame(self.main_frame, bg='white', relief='raised', bd=2)
        self.content_frame.pack(fill='both', expand=True, padx=40, pady=20)
        
        # Título de categoría
        self.category_title = tk.Label(self.content_frame,
                                      text="",
                                      font=('Arial', 18, 'bold'),
                                      fg='#1e3a8a',
                                      bg='white')
        self.category_title.pack(pady=20)
        
        # Frame para botones de aplicaciones
        self.apps_frame = tk.Frame(self.content_frame, bg='white')
        self.apps_frame.pack(fill='both', expand=True, padx=20, pady=10)
    
    def show_category(self, category):
        """Mostrar aplicaciones de una categoría."""
        # Limpiar frame de aplicaciones
        for widget in self.apps_frame.winfo_children():
            widget.destroy()
        
        # Actualizar título
        category_names = {
            'deposito': 'DEPÓSITO',
            'seguimientos': 'SEGUIMIENTOS',
            'monitoreo': 'MONITOREO',
            'comunicacion': 'COMUNICACIÓN',
            'test': 'TEST',
            'ayuda': 'AYUDA'
        }
        self.category_title.configure(text=category_names.get(category, category.upper()))
        
        # Crear grid de botones (2 columnas, 5 filas)
        apps = self.config.get(category, [])
        
        for i, app in enumerate(apps[:10]):  # Máximo 10 aplicaciones
            row = i // 2
            col = i % 2
            
            if app['name'] and app['exe']:
                # Botón para aplicación existente
                btn = tk.Button(self.apps_frame,
                               text=app['name'],
                               font=('Arial', 11, 'bold'),
                               bg='#10b981',
                               fg='white',
                               relief='flat',
                               padx=20,
                               pady=15,
                               cursor='hand2',
                               width=30,
                               command=lambda exe=app['exe']: self.launch_app(exe))
                
                # Efecto hover
                def on_enter(e, button=btn):
                    button.configure(bg='#059669')
                def on_leave(e, button=btn):
                    button.configure(bg='#10b981')
                
                btn.bind("<Enter>", on_enter)
                btn.bind("<Leave>", on_leave)
            else:
                # Botón vacío para futuras aplicaciones
                btn = tk.Button(self.apps_frame,
                               text="[Espacio disponible]",
                               font=('Arial', 10, 'italic'),
                               bg='#e5e7eb',
                               fg='#6b7280',
                               relief='flat',
                               padx=20,
                               pady=15,
                               width=30,
                               state='disabled')
            
            btn.grid(row=row, column=col, padx=10, pady=8, sticky='ew')
        
        # Configurar columnas para que se expandan
        self.apps_frame.grid_columnconfigure(0, weight=1)
        self.apps_frame.grid_columnconfigure(1, weight=1)
        
        # Botón para editar configuración
        edit_btn = tk.Button(self.apps_frame,
                            text="⚙️ Editar configuración",
                            font=('Arial', 10),
                            bg='#f59e0b',
                            fg='white',
                            relief='flat',
                            padx=15,
                            pady=8,
                            cursor='hand2',
                            command=lambda: self.edit_category(category))
        edit_btn.grid(row=5, column=0, columnspan=2, pady=20)
    
    def launch_app(self, exe_name):
        """Lanzar una aplicación."""
        try:
            exe_path = Path(__file__).parent / exe_name
            if exe_path.exists():
                subprocess.Popen([str(exe_path)], cwd=exe_path.parent)
                messagebox.showinfo("Éxito", f"Aplicación {exe_name} iniciada correctamente.")
            else:
                messagebox.showerror("Error", f"No se encontró el archivo: {exe_name}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al iniciar {exe_name}:\n{str(e)}")
    
    def edit_category(self, category):
        """Abrir ventana de edición para una categoría."""
        edit_window = tk.Toplevel(self.root)
        edit_window.title(f"Editar {category.upper()}")
        edit_window.geometry("600x500")
        edit_window.resizable(False, False)
        
        # Centrar ventana
        edit_window.transient(self.root)
        edit_window.grab_set()
        
        # Título
        title_label = tk.Label(edit_window,
                              text=f"Editar configuración - {category.upper()}",
                              font=('Arial', 14, 'bold'),
                              fg='#1e3a8a')
        title_label.pack(pady=10)
        
        # Frame para entradas
        entries_frame = tk.Frame(edit_window)
        entries_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Crear entradas para cada aplicación
        entries = []
        apps = self.config.get(category, [])
        
        for i in range(10):
            frame = tk.Frame(entries_frame)
            frame.pack(fill='x', pady=5)
            
            tk.Label(frame, text=f"App {i+1}:", width=8).pack(side='left')
            
            name_entry = tk.Entry(frame, width=25, font=('Arial', 10))
            name_entry.pack(side='left', padx=5)
            
            tk.Label(frame, text="EXE:", width=5).pack(side='left')
            
            exe_entry = tk.Entry(frame, width=30, font=('Arial', 10))
            exe_entry.pack(side='left', padx=5)
            
            # Cargar valores existentes
            if i < len(apps):
                name_entry.insert(0, apps[i].get('name', ''))
                exe_entry.insert(0, apps[i].get('exe', ''))
            
            entries.append((name_entry, exe_entry))
        
        # Botones
        buttons_frame = tk.Frame(edit_window)
        buttons_frame.pack(pady=20)
        
        def save_changes():
            # Guardar cambios
            new_apps = []
            for name_entry, exe_entry in entries:
                new_apps.append({
                    'name': name_entry.get().strip(),
                    'exe': exe_entry.get().strip()
                })
            
            self.config[category] = new_apps
            self.save_config()
            self.show_category(category)  # Refrescar vista
            edit_window.destroy()
            messagebox.showinfo("Éxito", "Configuración guardada correctamente.")
        
        save_btn = tk.Button(buttons_frame,
                            text="💾 Guardar",
                            font=('Arial', 11, 'bold'),
                            bg='#10b981',
                            fg='white',
                            padx=20,
                            pady=8,
                            command=save_changes)
        save_btn.pack(side='left', padx=10)
        
        cancel_btn = tk.Button(buttons_frame,
                              text="❌ Cancelar",
                              font=('Arial', 11, 'bold'),
                              bg='#ef4444',
                              fg='white',
                              padx=20,
                              pady=8,
                              command=edit_window.destroy)
        cancel_btn.pack(side='left', padx=10)
    
    def run(self):
        """Ejecutar la aplicación."""
        self.root.mainloop()

def main():
    """Función principal."""
    try:
        app = ProfessionalLauncher()
        app.run()
    except Exception as e:
        messagebox.showerror("Error", f"Error al iniciar el launcher:\n{str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
