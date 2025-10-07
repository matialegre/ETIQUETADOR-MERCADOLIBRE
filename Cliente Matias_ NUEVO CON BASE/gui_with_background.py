#!/usr/bin/env python3
"""
🎨 GUI SIMPLIFICADA CON IMAGEN DE FONDO
Versión que garantiza que la imagen de fondo funcione correctamente
"""

import tkinter as tk
from tkinter import ttk
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import os
import sys

class GuiWithBackground(tb.Window):
    """GUI simplificada con imagen de fondo garantizada."""
    
    def __init__(self):
        super().__init__(title="🏔️ MUNDO OUTDOOR - Stock Picking", themename="darkly")
        self.geometry("1200x800")
        
        # Variables para mantener referencias de imagen
        self.bg_image = None
        self.bg_label = None
        self.bg_image_ref = None
        
        self.create_interface()
        
    def create_interface(self):
        """Crear la interfaz con imagen de fondo."""
        
        # Frame principal
        main_frame = tb.Frame(self, padding=10)
        main_frame.pack(fill=BOTH, expand=YES)
        
        # Título
        title_label = tb.Label(main_frame, text="🏔️ MUNDO OUTDOOR - Sistema de Picking", 
                              font=('Arial', 20, 'bold'))
        title_label.pack(pady=10)
        
        # Botones superiores
        btn_frame = tb.Frame(main_frame)
        btn_frame.pack(fill=X, pady=10)
        
        tb.Button(btn_frame, text="📅 Cargar", bootstyle=PRIMARY).pack(side=LEFT, padx=5)
        tb.Button(btn_frame, text="🖨️ Imprimir lista", bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        tb.Button(btn_frame, text="📊 Historial", bootstyle=INFO).pack(side=LEFT, padx=5)
        
        # Frame para tabla con imagen de fondo
        table_frame = tb.Frame(main_frame, padding=10)
        table_frame.pack(fill=BOTH, expand=YES)
        
        # Configurar grid
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)
        
        # CARGAR IMAGEN DE FONDO
        self.load_background_image(table_frame)
        
        # Crear Treeview con estilo semi-transparente
        self.create_treeview(table_frame)
        
        # Botón de pickear
        pick_frame = tb.Frame(main_frame)
        pick_frame.pack(fill=X, pady=10)
        
        pick_btn = tb.Button(pick_frame, text="📦 PICKEAR", bootstyle="success-outline", 
                            font=('Arial', 16, 'bold'))
        pick_btn.pack(pady=10)
        
        # Barra de progreso
        progress_frame = tb.Frame(main_frame)
        progress_frame.pack(fill=X, pady=5)
        
        tb.Label(progress_frame, text="Progreso del día: 0% (0/0)").pack(side=LEFT)
        tb.Progressbar(progress_frame, value=0, length=200).pack(side=RIGHT)
    
    def load_background_image(self, parent_frame):
        """Cargar imagen de fondo de forma robusta."""
        
        print("🔍 Cargando imagen de fondo...")
        
        # Detectar si estamos en .exe o Python
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            temp_dir = getattr(sys, '_MEIPASS', base_dir)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            temp_dir = base_dir
        
        # Buscar imagen
        possible_paths = [
            os.path.join(base_dir, "background.png"),
            os.path.join(base_dir, "background.jpg"),
            os.path.join(temp_dir, "background.png"),
            os.path.join(temp_dir, "background.jpg"),
            "background.png",
            "background.jpg",
            os.path.join("..", "background.png"),
            os.path.join("..", "background.jpg")
        ]
        
        bg_path = None
        for path in possible_paths:
            if os.path.exists(path):
                bg_path = path
                print(f"✅ Imagen encontrada: {path}")
                break
        
        if not bg_path:
            print("❌ No se encontró imagen de fondo")
            # Crear fondo sólido elegante
            self.bg_label = tk.Label(parent_frame, bg='#34495e', 
                                   text="🏔️ MUNDO OUTDOOR\n\nImagen de fondo no encontrada\nColoca 'background.png' en la carpeta del programa",
                                   fg='white', font=('Arial', 14), justify='center')
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            self.bg_label.lower()
            return
        
        try:
            # Cargar con PIL
            from PIL import Image, ImageTk
            print(f"📎 Cargando imagen: {bg_path}")
            
            # Abrir imagen
            pil_image = Image.open(bg_path)
            original_size = pil_image.size
            print(f"📎 Tamaño original: {original_size}")
            
            # Obtener tamaño del frame
            self.update_idletasks()
            frame_width = max(parent_frame.winfo_width(), 1200)
            frame_height = max(parent_frame.winfo_height(), 600)
            print(f"📎 Redimensionando a: {frame_width}x{frame_height}")
            
            # Redimensionar
            pil_image = pil_image.resize((frame_width, frame_height), Image.Resampling.LANCZOS)
            
            # Aplicar transparencia
            pil_image = pil_image.convert("RGBA")
            alpha = pil_image.split()[-1]
            alpha = alpha.point(lambda p: int(p * 0.2))  # 20% opacidad más sutil
            pil_image.putalpha(alpha)
            
            # Crear PhotoImage
            self.bg_image = ImageTk.PhotoImage(pil_image)
            
            # Crear label de fondo
            self.bg_label = tk.Label(parent_frame, image=self.bg_image, bg='#2c3e50')
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            self.bg_label.lower()
            
            # CRÍTICO: Mantener múltiples referencias
            self.bg_image_ref = self.bg_image
            parent_frame.bg_image_ref = self.bg_image
            self.master.bg_image_ref = self.bg_image  # Referencia en ventana principal
            
            print("🎉 ¡IMAGEN DE FONDO CARGADA EXITOSAMENTE!")
            
        except ImportError:
            print("❌ PIL no disponible, usando fondo sólido")
            self.bg_label = tk.Label(parent_frame, bg='#34495e', 
                                   text="🏔️ MUNDO OUTDOOR\n\nInstala Pillow para imagen de fondo:\npip install Pillow",
                                   fg='white', font=('Arial', 12), justify='center')
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            self.bg_label.lower()
            
        except Exception as e:
            print(f"❌ Error cargando imagen: {e}")
            self.bg_label = tk.Label(parent_frame, bg='#e74c3c', 
                                   text=f"❌ Error cargando imagen:\n{str(e)}",
                                   fg='white', font=('Arial', 10), justify='center')
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            self.bg_label.lower()
    
    def create_treeview(self, parent_frame):
        """Crear Treeview con estilo semi-transparente."""
        
        # Configurar estilo
        style = ttk.Style()
        
        # Treeview semi-transparente
        style.configure("Background.Treeview",
                       background="#34495e",  # Fondo semi-transparente
                       fieldbackground="#34495e",
                       foreground="white",
                       font=('Arial', 12))
        
        style.configure("Background.Treeview.Heading",
                       background="#2c3e50",
                       foreground="white",
                       font=('Arial', 14, 'bold'),
                       relief="flat")
        
        style.map("Background.Treeview",
                 background=[("selected", "#3498db")],
                 foreground=[("selected", "white")])
        
        # Crear Treeview
        columns = ("nombre", "cant", "talle", "color")
        self.tree = ttk.Treeview(parent_frame, columns=columns, show="headings", 
                                height=15, style="Background.Treeview")
        
        # Configurar columnas
        self.tree.heading("nombre", text="Nombre del Artículo")
        self.tree.heading("cant", text="Cant")
        self.tree.heading("talle", text="Talle")
        self.tree.heading("color", text="Color")
        
        self.tree.column("nombre", width=600, anchor="w")
        self.tree.column("cant", width=80, anchor="center")
        self.tree.column("talle", width=100, anchor="center")
        self.tree.column("color", width=120, anchor="center")
        
        # Agregar datos de ejemplo
        sample_data = [
            ("Zapatilla Nike Air Max 270", "1", "42", "Negro/Blanco"),
            ("Remera Adidas Originals", "2", "L", "Azul"),
            ("Pantalón Deportivo Puma", "1", "M", "Gris"),
            ("Campera The North Face", "1", "XL", "Verde"),
            ("Zapatilla Converse All Star", "1", "39", "Rojo"),
        ]
        
        for data in sample_data:
            self.tree.insert("", "end", values=data)
        
        # Posicionar Treeview
        self.tree.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(parent_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky='ns')

def main():
    """Función principal."""
    try:
        print("🚀 Iniciando GUI con imagen de fondo...")
        app = GuiWithBackground()
        print("✅ GUI creada, iniciando mainloop...")
        app.mainloop()
        print("👋 GUI cerrada")
    except Exception as e:
        print(f"❌ Error en GUI: {e}")
        import traceback
        traceback.print_exc()
        input("Presiona Enter para salir...")

if __name__ == "__main__":
    main()
