import random
from datetime import datetime, timedelta, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from ..config import settings


async def generar_y_guardar_codigo(db: AsyncIOMotorDatabase, email: str) -> str:
    codigo = str(random.randint(100000, 999999))
    expira_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    # Reemplaza código anterior si existe (upsert evita duplicados)
    await db.verificaciones.replace_one(
        {"email": email},
        {"email": email, "codigo": codigo, "expira_at": expira_at},
        upsert=True,
    )
    return codigo


async def verificar_codigo(db: AsyncIOMotorDatabase, email: str, codigo: str) -> bool:
    ahora = datetime.now(timezone.utc)
    doc = await db.verificaciones.find_one({
        "email": email,
        "codigo": codigo,
        "expira_at": {"$gt": ahora},
    })
    return doc is not None


async def eliminar_codigo(db: AsyncIOMotorDatabase, email: str) -> None:
    await db.verificaciones.delete_one({"email": email})


async def enviar_codigo_verificacion(email: str, codigo: str) -> None:
    if settings.dev_mode:
        # En desarrollo el código aparece en consola para no necesitar SMTP real
        print(f"\n{'='*50}")
        print(f"  CÓDIGO DE VERIFICACIÓN para {email}")
        print(f"  Código: {codigo}")
        print(f"  Expira en 15 minutos")
        print(f"{'='*50}\n")
        return

    import aiosmtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart("alternative")
    msg["From"] = settings.email_from
    msg["To"] = email
    msg["Subject"] = "JHT PM — Código de verificación"

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 420px; margin: 0 auto; padding: 24px;">
        <h2 style="color: #4F46E5; margin-bottom: 8px;">JHT Project Manager</h2>
        <p style="color: #374151;">Tu código de verificación es:</p>
        <div style="font-size: 36px; font-weight: bold; letter-spacing: 10px; color: #4F46E5;
                    padding: 20px; background: #EEF2FF; border-radius: 10px; text-align: center;
                    margin: 20px 0;">
            {codigo}
        </div>
        <p style="color: #9CA3AF; font-size: 13px;">Expira en 15 minutos. Si no solicitaste este código, ignora este mensaje.</p>
    </div>
    """

    msg.attach(MIMEText(html, "html"))

    await aiosmtplib.send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_user,
        password=settings.smtp_password,
        start_tls=True,
    )
