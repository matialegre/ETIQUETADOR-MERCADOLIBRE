#!/usr/bin/env python3
"""
🚀 LAUNCHER SIMPLE - MercadoLibre Stock Picking
Launcher minimalista con imagen de fondo y botón para abrir la GUI
"""

import tkinter as tk
from tkinter import messagebox
import subprocess
import sys
import os
from pathlib import Path

class SimpleLauncher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🏔️ MUNDO OUTDOOR - Stock Picking")
        self.root.geometry("800x600")
        self.root.resizable(False, False)
        
        # Centrar ventana
        self.center_window()
        
        # Configurar colores
        self.root.configure(bg='#2C3E50')  # Azul oscuro elegante
        
        # Crear interfaz
        self.create_interface()
    
    def center_window(self):
        """Centrar la ventana en la pantalla."""
        self.root.update_idletasks()
        width = 800
        height = 600
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
    
    def create_interface(self):
        """Crear la interfaz del launcher."""
        
        # Frame principal con imagen de fondo
        main_frame = tk.Frame(self.root, bg='#2C3E50')
        main_frame.pack(fill='both', expand=True)
        
        # Intentar cargar imagen de fondo
        self.load_background_image(main_frame)
        
        # Título principal
        title_label = tk.Label(
            main_frame,
            text="🏔️ MUNDO OUTDOOR",
            font=('Arial', 28, 'bold'),
            fg='white',
            bg='#2C3E50'
        )
        title_label.pack(pady=(50, 10))
        
        # Subtítulo
        subtitle_label = tk.Label(
            main_frame,
            text="Sistema de Picking MercadoLibre",
            font=('Arial', 16),
            fg='#BDC3C7',
            bg='#2C3E50'
        )
        subtitle_label.pack(pady=(0, 50))
        
        # Botón principal (tamaño moderado para apreciar el fondo)
        launch_button = tk.Button(
            main_frame,
            text="🚀 ABRIR SISTEMA",
            font=('Arial', 14, 'bold'),
            bg='#27AE60',  # Verde
            fg='white',
            activebackground='#2ECC71',
            activeforeground='white',
            relief='raised',
            bd=2,
            padx=25,
            pady=12,
            cursor='hand2',
            command=self.launch_gui
        )
        launch_button.pack(pady=30)
        
        # Información adicional
        info_label = tk.Label(
            main_frame,
            text="Versión 3.0 - Optimizado para máximo rendimiento",
            font=('Arial', 10),
            fg='#95A5A6',
            bg='#2C3E50'
        )
        info_label.pack(side='bottom', pady=20)
        
        # Botón de salir pequeño
        exit_button = tk.Button(
            main_frame,
            text="❌ Salir",
            font=('Arial', 10),
            bg='#E74C3C',
            fg='white',
            activebackground='#C0392B',
            activeforeground='white',
            relief='flat',
            padx=20,
            pady=5,
            cursor='hand2',
            command=self.root.quit
        )
        exit_button.pack(side='bottom', pady=(0, 10))
    
    def load_background_image(self, parent):
        """Intentar cargar imagen de fondo."""
        try:
            # Buscar imagen de fondo en el directorio
            image_extensions = ['.png', '.jpg', '.jpeg', '.bmp', '.gif']
            
            # Detectar si estamos en un .exe empaquetado
            if getattr(sys, 'frozen', False):
                # Estamos en un .exe empaquetado
                base_path = Path(sys.executable).parent
                # También buscar en el directorio temporal de PyInstaller
                temp_path = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else base_path
            else:
                # Estamos ejecutando el script Python directamente
                base_path = Path(__file__).parent
                temp_path = base_path
            
            background_image = None
            
            # Buscar en ambas ubicaciones
            search_paths = [base_path, temp_path]
            
            for search_path in search_paths:
                for ext in image_extensions:
                    image_path = search_path / f"background{ext}"
                    if image_path.exists():
                        background_image = image_path
                        break
                if background_image:
                    break
            
            if background_image:
                # Cargar y mostrar imagen
                from PIL import Image, ImageTk
                
                # Abrir y redimensionar imagen
                pil_image = Image.open(background_image)
                pil_image = pil_image.resize((800, 600), Image.Resampling.LANCZOS)
                
                # Convertir para Tkinter
                self.bg_image = ImageTk.PhotoImage(pil_image)
                
                # Crear label con imagen de fondo
                bg_label = tk.Label(parent, image=self.bg_image)
                bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                
                print("✅ Imagen de fondo cargada exitosamente")
            else:
                print("ℹ️ No se encontró imagen de fondo (buscar: background.png/jpg/jpeg)")
                
        except ImportError:
            print("⚠️ PIL no disponible - usando fondo sólido")
        except Exception as e:
            print(f"⚠️ Error cargando imagen de fondo: {e}")
    
    def launch_gui(self):
        """Lanzar la GUI principal."""
        try:
            # Buscar el archivo .exe de la GUI
            base_path = Path(__file__).parent
            
            # Buscar el .exe en varias ubicaciones posibles
            possible_paths = [
                base_path / "Cliente_Matias_GUI_v3.exe",  # Mismo directorio
                base_path / "dist" / "Cliente_Matias_GUI_v3.exe",  # En carpeta dist
                base_path / "gui" / "app_gui_v3.py"  # Fallback a Python
            ]
            
            gui_path = None
            for path in possible_paths:
                if path.exists():
                    gui_path = path
                    break
            
            if not gui_path:
                messagebox.showerror(
                    "Error", 
                    "No se encontró la GUI.\n\nArchivos buscados:\n" +
                    "\n".join([str(p) for p in possible_paths])
                )
                return
            
            # Lanzar la GUI
            print(f"🚀 Lanzando GUI desde: {gui_path}")
            
            if gui_path.suffix == '.exe':
                # Es un .exe, ejecutar directamente
                subprocess.Popen([str(gui_path)], cwd=str(base_path))
            else:
                # Es un .py, ejecutar con Python
                subprocess.Popen([sys.executable, str(gui_path)], cwd=str(base_path))
            
            # Minimizar el launcher
            self.root.iconify()
            
        except Exception as e:
            messagebox.showerror(
                "Error al lanzar GUI", 
                f"Error: {str(e)}\n\nVerifica que el archivo existe y es ejecutable."
            )
    
    def run(self):
        """Ejecutar el launcher."""
        self.root.mainloop()

def main():
    """Función principal."""
    try:
        launcher = SimpleLauncher()
        launcher.run()
    except Exception as e:
        print(f"❌ Error en launcher: {e}")
        input("Presiona Enter para salir...")

if __name__ == "__main__":
    main()
