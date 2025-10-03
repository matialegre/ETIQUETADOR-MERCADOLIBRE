"""
Módulo 03: Conexión a base de datos local
=========================================

Configuración de SQLAlchemy para SQL Server Express.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import urllib.parse

from modules.models import Base
from modules.config import SQLSERVER_CONN_STR, SQLSERVER_APP_CONN_STR

# Configurar connection string para SQLAlchemy
def get_sqlalchemy_url():
    """
    Convierte el connection string de pyodbc a formato SQLAlchemy.
    """
    # Connection string base (preferir base de la app)
    conn_str = SQLSERVER_APP_CONN_STR or SQLSERVER_CONN_STR
    
    # Para SQLAlchemy necesitamos URL encode
    params = urllib.parse.quote_plus(conn_str)
    return f"mssql+pyodbc:///?odbc_connect={params}"

# Crear engine
engine = create_engine(
    get_sqlalchemy_url(),
    echo=False,  # Cambiar a True para debug SQL
    pool_pre_ping=True,
    pool_recycle=3600
)

# Crear sessionmaker
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def init_db():
    """
    Inicializa las tablas en la base de datos.
    """
    Base.metadata.create_all(bind=engine)

def get_db():
    """
    Dependency para obtener sesión de base de datos.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    # Test de conexión
    import sys
    
    try:
        print("🔌 Probando conexión a SQL Server Express...")
        
        # Test básico de conexión
        with SessionLocal() as session:
            result = session.execute("SELECT 1 as test").fetchone()
            print(f"✅ Conexión exitosa: {result}")
        
        print("✅ Base de datos conectada correctamente")
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        sys.exit(1)
