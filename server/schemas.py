from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, RootModel


class OrderItem(RootModel[Dict[str, Any]]):
    # dynamic dict for flexible fields (Pydantic v2 RootModel)
    pass


class OrdersResponse(BaseModel):
    orders: List[Dict[str, Any]]
    page: int
    total: int


class UpdateOrderRequest(BaseModel):
    deposito_asignado: Optional[str] = Field(default=None)
    COMENTARIO: Optional[str] = Field(default=None)
    mov_depo_hecho: Optional[int] = Field(default=None, ge=0, le=1)
    mov_depo_obs: Optional[str] = Field(default=None)
    mov_depo_numero: Optional[str] = Field(default=None)
    tracking_number: Optional[str] = Field(default=None)
    # Movimiento LOCAL (nuevo)
    MOV_LOCAL_HECHO: Optional[int] = Field(default=None, ge=0, le=1)
    MOV_LOCAL_NUMERO: Optional[str] = Field(default=None)
    MOV_LOCAL_OBS: Optional[str] = Field(default=None)
    printed: Optional[int] = Field(default=None, ge=0, le=1)
    ready_to_print: Optional[int] = Field(default=None, ge=0, le=1)
    asignacion_detalle: Optional[str] = Field(default=None)
    shipping_estado: Optional[str] = Field(default=None)
    shipping_subestado: Optional[str] = Field(default=None)
    CAMBIO_ESTADO: Optional[int] = Field(default=None, ge=0, le=1)


class UpdateOrderResponse(BaseModel):
    ok: bool
    affected: int


def get_allowed_update_fields() -> List[str]:
    return [
        "deposito_asignado",
        "COMENTARIO",
        "mov_depo_hecho",
        "mov_depo_obs",
        "mov_depo_numero",
        "tracking_number",
        # Movimiento LOCAL (nuevo)
        "MOV_LOCAL_HECHO",
        "MOV_LOCAL_NUMERO",
        "MOV_LOCAL_OBS",
        "printed",
        "ready_to_print",
        "asignacion_detalle",
        "shipping_estado",
        "shipping_subestado",
        "CAMBIO_ESTADO",
    ]


def get_default_fields() -> List[str]:
    # Campos más usados; el cliente puede pedir más vía ?fields=
    return [
        "order_id",
        "pack_id",
        "sku",
        "seller_sku",
        "barcode",
        "ARTICULO",
        "COLOR",
        "TALLE",
        "display_color",
        "qty",
        "date_created",
        "date_closed",
        "_estado",
        "shipping_estado",
        "shipping_subestado",
        "venta_tipo",
        "meli_ad",
        "agotamiento_flag",
        "COMENTARIO",
        "deposito_asignado",
        "ready_to_print",
        "printed",
    ]
