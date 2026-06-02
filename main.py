import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import conectar_db, desconectar_db
from app.routers import auth, usuarios, areas, proyectos, tareas, sprints, epicas, chat, estados, evidencias, checklists


@asynccontextmanager
async def lifespan(app: FastAPI):
    await conectar_db()
    os.makedirs("uploads/images", exist_ok=True)
    os.makedirs("uploads/archivos", exist_ok=True)
    os.makedirs("uploads/estados", exist_ok=True)
    os.makedirs("uploads/evidencias", exist_ok=True)
    yield
    await desconectar_db()


app = FastAPI(title="JHT Project Manager API", version="1.0.0", lifespan=lifespan)

origenes = [o.strip() for o in settings.allowed_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origenes,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(usuarios.router, prefix="/usuarios", tags=["Usuarios"])
app.include_router(areas.router, prefix="/areas", tags=["Áreas"])
app.include_router(proyectos.router, prefix="/proyectos", tags=["Proyectos"])
app.include_router(tareas.router, prefix="/tareas", tags=["Tareas"])
app.include_router(sprints.router, prefix="/sprints", tags=["Sprints"])
app.include_router(epicas.router, prefix="/epicas", tags=["Épicas"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(estados.router, prefix="/estados", tags=["Estados"])
app.include_router(evidencias.router, prefix="/evidencias", tags=["Evidencias"])
app.include_router(checklists.router, prefix="/checklists", tags=["Checklists"])


@app.get("/")
async def raiz():
    return {"mensaje": "JHT Project Manager API", "version": "1.0.0", "docs": "/docs"}
