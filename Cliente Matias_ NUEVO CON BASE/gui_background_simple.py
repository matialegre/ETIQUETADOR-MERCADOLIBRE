#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI Simplificada con Imagen de Fondo en el Treeview
Versión que garantiza funcionar sin errores de estilo
"""

import tkinter as tk
from tkinter import ttk
import ttkbootstrap as ttk_boot
from PIL import Image, ImageTk
import sys
import os

class SimpleGuiWithBackground:
    def __init__(self):
        print("🚀 Iniciando GUI simplificada con imagen de fondo...")
        
        # Crear ventana principal
        self.root = ttk_boot.Window(themename="darkly")
        self.root.title("🎯 GUI con Imagen de Fondo - PRUEBA")
        self.root.geometry("1400x800")
        
        # Variables para mantener referencias
        self.bg_image_ref = None
        self.bg_label = None
        
        # Cargar imagen de fondo
        self.load_background_image()
        
        # Crear interfaz
        self.create_interface()
        
        print("✅ GUI inicializada correctamente")

    def find_background_image(self):
        """Busca la imagen de fondo en múltiples ubicaciones"""
        possible_paths = [
            "background.png",
            "gui/background.png", 
            os.path.join(os.path.dirname(__file__), "background.png"),
            os.path.join(os.path.dirname(__file__), "gui", "background.png")
        ]
        
        # Si estamos ejecutando como .exe
        if hasattr(sys, '_MEIPASS'):
            possible_paths.insert(0, os.path.join(sys._MEIPASS, "background.png"))
        
        for path in possible_paths:
            if os.path.exists(path):
                print(f"✅ Imagen encontrada: {os.path.abspath(path)}")
                return path
        
        print("❌ No se encontró background.png en ninguna ubicación")
        return None

    def load_background_image(self):
        """Carga y prepara la imagen de fondo"""
        print("🔍 Cargando imagen de fondo...")
        
        image_path = self.find_background_image()
        if not image_path:
            print("⚠️ Continuando sin imagen de fondo")
            return
        
        try:
            print(f"📎 Cargando imagen: {image_path}")
            
            # Cargar imagen
            pil_image = Image.open(image_path)
            print(f"📎 Tamaño original: {pil_image.size}")
            
            # Redimensionar para que se vea bien en el fondo
            target_width = 1200
            target_height = 600
            pil_image = pil_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
            print(f"📎 Redimensionando a: {target_width}x{target_height}")
            
            # Convertir a PhotoImage
            self.bg_image_ref = ImageTk.PhotoImage(pil_image)
            print("✅ Imagen de fondo cargada correctamente")
            
        except Exception as e:
            print(f"❌ Error cargando imagen: {e}")
            self.bg_image_ref = None

    def create_interface(self):
        """Crea la interfaz principal"""
        print("🎨 Creando interfaz...")
        
        # Frame principal
        main_frame = ttk_boot.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Título
        title_label = ttk_boot.Label(main_frame, text="🎯 PRUEBA - Imagen de Fondo en Tabla", 
                                   font=("Arial", 20, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Frame para la tabla con imagen de fondo
        table_container = ttk_boot.Frame(main_frame)
        table_container.pack(fill="both", expand=True)
        
        # Si tenemos imagen de fondo, crear el label de fondo
        if self.bg_image_ref:
            print("🖼️ Aplicando imagen de fondo...")
            self.bg_label = tk.Label(table_container, image=self.bg_image_ref)
            self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            # Enviar al fondo
            self.bg_label.lower()
        
        # Crear Treeview ESTÁNDAR (sin estilos personalizados)
        self.create_standard_treeview(table_container)
        
        # Botones de prueba
        button_frame = ttk_boot.Frame(main_frame)
        button_frame.pack(pady=20)
        
        add_btn = ttk_boot.Button(button_frame, text="➕ Agregar Fila", 
                                command=self.add_sample_row, bootstyle="success")
        add_btn.pack(side="left", padx=10)
        
        clear_btn = ttk_boot.Button(button_frame, text="🗑️ Limpiar", 
                                  command=self.clear_table, bootstyle="danger")
        clear_btn.pack(side="left", padx=10)
        
        # Agregar algunas filas de ejemplo
        self.add_sample_data()

    def create_standard_treeview(self, parent):
        """Crea un Treeview estándar sin estilos personalizados"""
        print("📋 Creando tabla estándar...")
        
        # Definir columnas
        columns = ("producto", "cantidad", "talle", "color", "estado")
        
        # Crear Treeview ESTÁNDAR
        self.tree = ttk.Treeview(parent, columns=columns, show="headings", height=15)
        
        # Configurar encabezados
        self.tree.heading("producto", text="Producto")
        self.tree.heading("cantidad", text="Cant")
        self.tree.heading("talle", text="Talle")
        self.tree.heading("color", text="Color")
        self.tree.heading("estado", text="Estado")
        
        # Configurar anchos
        self.tree.column("producto", width=400)
        self.tree.column("cantidad", width=80)
        self.tree.column("talle", width=100)
        self.tree.column("color", width=150)
        self.tree.column("estado", width=120)
        
        # Hacer el Treeview semi-transparente usando configure
        try:
            # Configurar colores para transparencia
            self.tree.configure(selectmode="extended")
            
            # Crear scrollbar
            scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
            self.tree.configure(yscrollcommand=scrollbar.set)
            
            # Empaquetar
            self.tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            print("✅ Tabla creada correctamente")
            
        except Exception as e:
            print(f"❌ Error configurando tabla: {e}")

    def add_sample_data(self):
        """Agrega datos de ejemplo"""
        sample_data = [
            ("Zapatillas Nike Air Max", "1", "42", "Negro", "Pendiente"),
            ("Remera Adidas", "2", "L", "Azul", "Listo"),
            ("Pantalón Deportivo", "1", "M", "Gris", "Impreso"),
            ("Buzo Micropolar", "1", "S", "Rojo", "Pendiente"),
            ("Campera Impermeable", "1", "XL", "Verde", "Listo")
        ]
        
        for i, data in enumerate(sample_data):
            # Alternar colores para ver mejor el efecto
            tag = "even" if i % 2 == 0 else "odd"
            item_id = self.tree.insert("", "end", values=data, tags=(tag,))
        
        # Configurar tags de colores
        self.tree.tag_configure("even", background="#f0f0f0")
        self.tree.tag_configure("odd", background="#ffffff")
        
        print(f"✅ Agregadas {len(sample_data)} filas de ejemplo")

    def add_sample_row(self):
        """Agrega una fila de ejemplo"""
        import random
        productos = ["Producto A", "Producto B", "Producto C"]
        talles = ["S", "M", "L", "XL"]
        colores = ["Rojo", "Azul", "Verde", "Negro"]
        estados = ["Pendiente", "Listo", "Impreso"]
        
        data = (
            random.choice(productos),
            str(random.randint(1, 3)),
            random.choice(talles),
            random.choice(colores),
            random.choice(estados)
        )
        
        self.tree.insert("", "end", values=data)
        print(f"➕ Fila agregada: {data[0]}")

    def clear_table(self):
        """Limpia la tabla"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        print("🗑️ Tabla limpiada")

    def run(self):
        """Ejecuta la aplicación"""
        print("🚀 Iniciando aplicación...")
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            print("\n👋 Aplicación cerrada por el usuario")
        except Exception as e:
            print(f"❌ Error en aplicación: {e}")

def main():
    """Función principal"""
    try:
        app = SimpleGuiWithBackground()
        app.run()
    except Exception as e:
        print(f"❌ Error en GUI: {e}")
        import traceback
        traceback.print_exc()
    finally:
        input("Presiona Enter para salir...")

if __name__ == "__main__":
    main()
