"""
Módulo 03: Modelos SQLAlchemy
============================

Modelos ORM para la base de datos meli_stock.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, BigInteger, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class OrderItem(Base):
    """
    Modelo para la tabla orders_meli.
    """
    __tablename__ = 'orders_meli'
    
    # Campos principales
    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(50), nullable=False)
    pack_id = Column(String(50))
    item_id = Column(String(50))
    sku = Column(String(100))
    barcode = Column(String(100))
    
    # Estados y tipos
    venta_tipo = Column(String(50))
    estado = Column(String(50))
    subestado = Column(String(50))
    shipping_estado = Column(String(50))
    shipping_subestado = Column(String(50))
    
    # Información adicional
    nota = Column(String(512))
    deposito_asignado = Column(String(50))
    
    # Stock y cantidades
    qty = Column(Integer)
    stock_real = Column(Integer)
    stock_reservado = Column(Integer)
    resultante = Column(Integer)
    
    # Flags de control
    asignado_flag = Column(Boolean, default=False)
    agotamiento_flag = Column(Boolean, default=False)
    
    # Fechas
    fecha_orden = Column(DateTime)
    last_update = Column(DateTime, default=func.sysutcdatetime())
    
    # Campos adicionales de la base actual
    multiventa_grupo = Column(Integer)
    pack_original = Column(String(50))
    pack_actual = Column(String(50))
    multiventa_subgrupo = Column(String(10))
    es_particion = Column(Boolean)
    fecha_particion = Column(DateTime)
    motivo_particion = Column(String(200))
    
    # Shipping detallado
    shipment_id = Column(String(50))
    shipment_original = Column(String(50))
    sibling_shipment_id = Column(String(50))
    split_status = Column(String(20))
    ml_split_response = Column(Text)
    display_color = Column(String(20))
    
    # Stock por depósito
    stock_mundoal = Column(Integer, default=0)
    stock_dep = Column(Integer, default=0)
    stock_monbahia = Column(Integer, default=0)
    stock_mtgbbps = Column(Integer, default=0)
    stock_mundocab = Column(Integer, default=0)
    stock_nqnshop = Column(Integer, default=0)
    stock_mtgcom = Column(Integer, default=0)
    stock_mtgroca = Column(Integer, default=0)
    stock_mundoroc = Column(Integer, default=0)
    
    # Estados de shipping
    shipping_status = Column(String(50))
    shipping_substatus = Column(String(50))
    date_created = Column(DateTime)
    
    # Información de MercadoLibre
    meli_id = Column(String(50))
    fulfillment = Column(String(50))
    substatus = Column(String(50))
    notes = Column(Text)
    tags = Column(String(500))
    
    # Precios
    unit_price = Column(Numeric(18, 2))
    total_amount = Column(Numeric(18, 2))
    currency_id = Column(String(10))
    
    # IDs de referencia
    buyer_id = Column(BigInteger)
    seller_id = Column(BigInteger)
    shipping_id = Column(BigInteger)
    
    # Tracking
    tracking_number = Column(String(100))
    tracking_method = Column(String(100))
    estimated_delivery = Column(DateTime)
    
    # Estados críticos
    ready_to_print = Column(Boolean, default=False)
    printed = Column(Boolean, default=False)
    fecha_asignacion = Column(DateTime)

    # Campos adicionales solicitados
    articulo = Column('ARTICULO', String(100), nullable=True)
    color = Column('COLOR', String(50), nullable=True)
    talle = Column('TALLE', String(50), nullable=True)
    comentario = Column('COMENTARIO', String(500), nullable=True)
    
    def __repr__(self):
        return f"<OrderItem(order_id='{self.order_id}', sku='{self.sku}', deposito='{self.deposito_asignado}')>"
