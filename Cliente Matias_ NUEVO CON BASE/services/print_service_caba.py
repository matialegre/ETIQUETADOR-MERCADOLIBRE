# services/print_service_caba.py
"""
Servicio de impresión específico para CABA.
Genera PDFs filtrados por keywords de CABA.
"""

import os
import subprocess
from typing import List, Dict, Any
from datetime import datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

import config_caba
from utils.logger import get_logger

log = get_logger(__name__)

class PrintServiceCaba:
    """Servicio de impresión específico para CABA."""
    
    def __init__(self):
        self.keywords = config_caba.KEYWORDS_NOTE_CABA
        self.deposito_name = config_caba.DEPOSITO_DISPLAY_NAME
        log.info(f"🖨️ PrintService CABA inicializado para: {self.deposito_name}")
    
    def generate_and_open_pdf(self, rows: List[Dict[str, Any]], filename: str = None) -> str:
        """
        Genera un PDF con los artículos filtrados para CABA y lo abre.
        
        Args:
            rows: Lista de diccionarios con datos de artículos
            filename: Nombre del archivo (opcional)
            
        Returns:
            str: Ruta del archivo PDF generado
        """
        try:
            # Generar nombre de archivo si no se proporciona
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"lista_picking_caba_{timestamp}.pdf"
            
            # Crear directorio de salida si no existe
            output_dir = "pdfs_caba"
            os.makedirs(output_dir, exist_ok=True)
            
            filepath = os.path.join(output_dir, filename)
            
            # Crear documento PDF
            doc = SimpleDocTemplate(filepath, pagesize=A4)
            story = []
            
            # Estilos
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=1,  # Centrado
                textColor=colors.darkblue
            )
            
            header_style = ParagraphStyle(
                'CustomHeader',
                parent=styles['Normal'],
                fontSize=12,
                spaceAfter=20,
                alignment=1,  # Centrado
                textColor=colors.black
            )
            
            # Título del documento
            title = Paragraph(f"LISTA DE PICKING - {self.deposito_name}", title_style)
            story.append(title)
            
            # Información del documento
            info_text = f"""
            <b>Fecha de generación:</b> {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}<br/>
            <b>Depósito:</b> {self.deposito_name}<br/>
            <b>Filtros aplicados:</b> {', '.join(self.keywords)}<br/>
            <b>Total de artículos:</b> {len(rows)}
            """
            info = Paragraph(info_text, header_style)
            story.append(info)
            story.append(Spacer(1, 20))
            
            if not rows:
                # Si no hay datos
                no_data = Paragraph(
                    f"<b>No se encontraron artículos para imprimir con los filtros de {self.deposito_name}</b>",
                    styles['Normal']
                )
                story.append(no_data)
            else:
                # Preparar datos para la tabla
                table_data = [
                    ['Pedido', 'Artículo', 'SKU', 'Cant.', 'Talle', 'Color', 'Depósito']
                ]
                
                for row in rows:
                    table_data.append([
                        str(row.get('pedido', '')),
                        str(row.get('articulo', ''))[:40] + ('...' if len(str(row.get('articulo', ''))) > 40 else ''),
                        str(row.get('sku', '')),
                        str(row.get('cantidad', '')),
                        str(row.get('talle', '')),
                        str(row.get('color', '')),
                        str(row.get('deposito', self.deposito_name))
                    ])
                
                # Crear tabla
                table = Table(table_data, colWidths=[
                    1.2*inch,  # Pedido
                    2.5*inch,  # Artículo
                    1.2*inch,  # SKU
                    0.6*inch,  # Cantidad
                    0.8*inch,  # Talle
                    1.0*inch,  # Color
                    1.0*inch   # Depósito
                ])
                
                # Estilo de la tabla
                table.setStyle(TableStyle([
                    # Encabezado
                    ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    
                    # Contenido
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    
                    # Bordes
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    
                    # Alternar colores de filas
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]))
                
                story.append(table)
                
                # Resumen al final
                story.append(Spacer(1, 30))
                summary_text = f"""
                <b>RESUMEN:</b><br/>
                • Total de artículos: {len(rows)}<br/>
                • Depósito: {self.deposito_name}<br/>
                • Generado: {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
                """
                summary = Paragraph(summary_text, styles['Normal'])
                story.append(summary)
            
            # Construir PDF
            doc.build(story)
            
            log.info(f"✅ PDF CABA generado: {filepath}")
            
            # Abrir PDF automáticamente
            self._open_pdf(filepath)
            
            return filepath
            
        except Exception as e:
            log.error(f"❌ Error generando PDF CABA: {e}")
            raise
    
    def _open_pdf(self, filepath: str):
        """Abre el PDF generado con el visor predeterminado."""
        try:
            if os.name == 'nt':  # Windows
                os.startfile(filepath)
            elif os.name == 'posix':  # macOS/Linux
                subprocess.call(['open', filepath])
            else:
                log.warning("⚠️ No se pudo abrir PDF automáticamente en este sistema")
            
            log.info(f"📖 PDF abierto: {filepath}")
            
        except Exception as e:
            log.error(f"❌ Error abriendo PDF: {e}")
    
    def filter_rows_for_caba(self, all_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filtra filas para incluir solo las que corresponden a CABA.
        
        Args:
            all_rows: Todas las filas disponibles
            
        Returns:
            List[Dict]: Filas filtradas para CABA
        """
        filtered_rows = []
        
        for row in all_rows:
            # Buscar keywords en diferentes campos
            pedido = str(row.get('pedido', '')).upper()
            deposito = str(row.get('deposito', '')).upper()
            notas = str(row.get('notas', '')).upper()
            
            # Verificar si contiene algún keyword de CABA
            text_to_check = f"{pedido} {deposito} {notas}"
            
            if any(keyword in text_to_check for keyword in self.keywords):
                # Asegurar que el depósito esté marcado correctamente
                row['deposito'] = self.deposito_name
                filtered_rows.append(row)
                log.debug(f"✅ Fila incluida para CABA: {row.get('pedido', '')}")
            else:
                log.debug(f"❌ Fila excluida (no CABA): {row.get('pedido', '')}")
        
        log.info(f"🎯 Filtrado CABA: {len(filtered_rows)}/{len(all_rows)} filas")
        return filtered_rows
    
    def generate_caba_summary_pdf(self, orders_summary: Dict[str, int]) -> str:
        """
        Genera un PDF con resumen de pedidos CABA.
        
        Args:
            orders_summary: Diccionario con estadísticas de pedidos
            
        Returns:
            str: Ruta del archivo PDF generado
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"resumen_caba_{timestamp}.pdf"
            
            output_dir = "pdfs_caba"
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, filename)
            
            doc = SimpleDocTemplate(filepath, pagesize=A4)
            story = []
            styles = getSampleStyleSheet()
            
            # Título
            title = Paragraph(f"RESUMEN DE PEDIDOS - {self.deposito_name}", styles['Title'])
            story.append(title)
            story.append(Spacer(1, 30))
            
            # Estadísticas
            stats_text = f"""
            <b>ESTADÍSTICAS DE PEDIDOS {self.deposito_name}</b><br/><br/>
            • Total de pedidos cargados: {orders_summary.get('total', 0)}<br/>
            • Pedidos de CABA: {orders_summary.get('caba', 0)}<br/>
            • Listos para imprimir: {orders_summary.get('ready_to_print', 0)}<br/>
            • Ya impresos: {orders_summary.get('printed', 0)}<br/><br/>
            
            <b>Filtros aplicados:</b> {', '.join(self.keywords)}<br/>
            <b>Fecha de generación:</b> {datetime.now().strftime("%d/%m/%Y %H:%M:%S")}
            """
            
            stats = Paragraph(stats_text, styles['Normal'])
            story.append(stats)
            
            doc.build(story)
            
            log.info(f"✅ PDF resumen CABA generado: {filepath}")
            self._open_pdf(filepath)
            
            return filepath
            
        except Exception as e:
            log.error(f"❌ Error generando PDF resumen CABA: {e}")
            raise
    
    def validate_pdf_data(self, rows: List[Dict[str, Any]]) -> bool:
        """
        Valida que los datos para PDF sean correctos.
        
        Args:
            rows: Filas a validar
            
        Returns:
            bool: True si los datos son válidos
        """
        if not rows:
            log.warning("⚠️ No hay datos para generar PDF")
            return False
        
        required_fields = ['pedido', 'articulo', 'sku', 'cantidad']
        
        for i, row in enumerate(rows):
            for field in required_fields:
                if field not in row or not row[field]:
                    log.warning(f"⚠️ Fila {i} falta campo requerido: {field}")
                    return False
        
        log.debug(f"✅ Datos PDF validados: {len(rows)} filas")
        return True
