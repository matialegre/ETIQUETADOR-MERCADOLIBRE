#!/usr/bin/env python3
"""
🧪 TEST SIMPLE - Imagen de fondo en Treeview
Prueba básica para verificar que la imagen de fondo funciona
"""

import tkinter as tk
from tkinter import ttk
import os
import sys

def test_background():
    """Crear ventana de prueba con imagen de fondo en Treeview."""
    
    root = tk.Tk()
    root.title("🧪 Test - Imagen de fondo")
    root.geometry("800x600")
    root.configure(bg='#2c3e50')
    
    # Frame para la tabla
    frame = tk.Frame(root, bg='#2c3e50')
    frame.pack(fill='both', expand=True, padx=20, pady=20)
    
    # Configurar grid
    frame.grid_rowconfigure(0, weight=1)
    frame.grid_columnconfigure(0, weight=1)
    
    print("🔍 Buscando imagen de fondo...")
    
    # Buscar imagen
    possible_paths = [
        "background.png",
        "background.jpg", 
        "fondo.png",
        os.path.join(os.path.dirname(__file__), "background.png"),
        os.path.join(os.path.dirname(__file__), "fondo.png")
    ]
    
    bg_path = None
    for path in possible_paths:
        if os.path.exists(path):
            bg_path = path
            print(f"✅ Imagen encontrada: {path}")
            break
        else:
            print(f"❌ No existe: {path}")
    
    if bg_path:
        try:
            print("📎 Cargando imagen con PIL...")
            from PIL import Image, ImageTk
            
            # Cargar imagen
            pil_image = Image.open(bg_path)
            print(f"📎 Tamaño original: {pil_image.size}")
            
            # Redimensionar
            pil_image = pil_image.resize((800, 600), Image.Resampling.LANCZOS)
            
            # Hacer semi-transparente
            pil_image = pil_image.convert("RGBA")
            alpha = pil_image.split()[-1]
            alpha = alpha.point(lambda p: int(p * 0.3))  # 30% opacidad
            pil_image.putalpha(alpha)
            
            # Crear PhotoImage
            bg_image = ImageTk.PhotoImage(pil_image)
            
            # Crear label de fondo
            bg_label = tk.Label(frame, image=bg_image, bg='#2c3e50')
            bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            bg_label.lower()
            
            print("🎉 ¡Imagen de fondo aplicada!")
            
            # Mantener referencia para evitar garbage collection
            root.bg_image = bg_image
            
        except Exception as e:
            print(f"❌ Error cargando imagen: {e}")
            bg_label = tk.Label(frame, text="❌ Error cargando imagen", bg='#e74c3c', fg='white')
            bg_label.place(x=0, y=0, relwidth=1, relheight=1)
    else:
        print("❌ No se encontró imagen de fondo")
        bg_label = tk.Label(frame, text="❌ No se encontró imagen", bg='#e74c3c', fg='white')
        bg_label.place(x=0, y=0, relwidth=1, relheight=1)
    
    # Crear Treeview de prueba
    columns = ("nombre", "cant", "talle", "color")
    tree = ttk.Treeview(frame, columns=columns, show="headings", height=10)
    
    # Configurar columnas
    tree.heading("nombre", text="Nombre del Artículo")
    tree.heading("cant", text="Cant")
    tree.heading("talle", text="Talle") 
    tree.heading("color", text="Color")
    
    tree.column("nombre", width=400)
    tree.column("cant", width=80)
    tree.column("talle", width=100)
    tree.column("color", width=100)
    
    # Estilo semi-transparente
    style = ttk.Style()
    style.configure("Treeview",
                   background="#34495e",  # Fondo semi-transparente
                   fieldbackground="#34495e",
                   foreground="white")
    
    style.configure("Treeview.Heading",
                   background="#2c3e50",
                   foreground="white")
    
    # Agregar datos de prueba
    tree.insert("", "end", values=("Zapatilla Nike Air Max", "1", "42", "Negro"))
    tree.insert("", "end", values=("Remera Adidas", "2", "L", "Blanco"))
    tree.insert("", "end", values=("Pantalón Deportivo", "1", "M", "Azul"))
    
    # Posicionar Treeview
    tree.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
    
    # Scrollbar
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.grid(row=0, column=1, sticky='ns')
    
    # Botón de prueba
    btn_test = tk.Button(root, text="🎨 ¡Imagen de fondo funcionando!", 
                        bg='#27ae60', fg='white', font=('Arial', 12, 'bold'))
    btn_test.pack(pady=10)
    
    print("🚀 Ventana de prueba creada. ¡Deberías ver la imagen de fondo!")
    root.mainloop()

if __name__ == "__main__":
    test_background()
