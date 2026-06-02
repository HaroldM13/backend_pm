from datetime import datetime


def fecha_a_str(dt: datetime) -> str:
    # Serializa datetime UTC de MongoDB a ISO 8601 con sufijo Z
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "Z"


def doc_to_dict(doc: dict) -> dict:
    # Convierte _id de ObjectId a string "id" — evita repetir esta lógica en cada servicio
    if doc and "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    return doc
