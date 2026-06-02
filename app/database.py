from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from .config import settings

_cliente: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def conectar_db() -> None:
    global _cliente, _db
    _cliente = AsyncIOMotorClient(settings.mongodb_uri)
    _db = _cliente[settings.database_name]
    await _crear_indices()
    print(f"Conectado a MongoDB: {settings.database_name}")


async def desconectar_db() -> None:
    if _cliente:
        _cliente.close()


async def _crear_indices() -> None:
    # Unicidad en email y teléfono — evita duplicados a nivel de BD
    await _db.usuarios.create_index("email", unique=True)
    await _db.usuarios.create_index("telefono", unique=True)
    # TTL index: MongoDB borra automáticamente los códigos expirados
    await _db.verificaciones.create_index("expira_at", expireAfterSeconds=0)
    # Índices de búsqueda frecuente
    await _db.areas.create_index("miembros")
    await _db.proyectos.create_index([("area_id", 1), ("miembros", 1)])
    await _db.tareas.create_index([("proyecto_id", 1), ("columna", 1)])
    await _db.mensajes.create_index([("sala_id", 1), ("created_at", -1)])


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Base de datos no inicializada — llamar conectar_db() primero")
    return _db
