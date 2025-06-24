from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from uuid import uuid4, UUID
from sqlalchemy import create_engine, Column, String, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
import pandas as pd
import qrcode
import os
from datetime import datetime
from sqlalchemy import DateTime

import socket

# --- Configuracion ---
DB_PATH = "sqlite:///./invitados.db"
CSV_PATH = "invitados.csv"
QR_DIR = "static/qrs"
TEMPLATES_DIR = "templates"
LOCAL_IP = "192.168.28.186"  # IP local corregida para acceso desde otros dispositivos en la red

# --- Crear carpetas necesarias ---
for path in ["static", QR_DIR, TEMPLATES_DIR]:
    os.makedirs(path, exist_ok=True)

# --- Inicializacion ---
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Modelo ---
class Invitado(Base):
    __tablename__ = "invitados"

    id = Column(String, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    email = Column(String, nullable=True, unique=True)
    ha_asistido = Column(Boolean, default=False)
    fecha_hora = Column(DateTime, nullable=True)  # agregar esta línea

Base.metadata.create_all(bind=engine)

# --- Carga inicial desde CSV y generación de QR ---
def cargar_invitados(regenerar_qrs: bool = False):
    df = pd.read_csv(CSV_PATH)
    db = SessionLocal()
    for _, row in df.iterrows():
        nombre = row['nombre']
        email = row.get('email', None)

        existente = db.query(Invitado).filter(Invitado.email == email).first()
        if existente:
            invitado_uuid = existente.id
        else:
            invitado_uuid = str(uuid4())
            invitado = Invitado(id=invitado_uuid, nombre=nombre, email=email)
            db.add(invitado)

        qr_filename = f"{QR_DIR}/{nombre}_{invitado_uuid}.png"
        if regenerar_qrs or not os.path.exists(qr_filename):
            url = f"http://{LOCAL_IP}:8000/confirmar?id={invitado_uuid}"
            img = qrcode.make(url)
            img.save(qr_filename)

    db.commit()
    db.close()

# --- Endpoint de confirmacion ---
@app.get("/confirmar")
def confirmar_asistencia(id: UUID):
    db = SessionLocal()
    invitado = db.query(Invitado).filter(Invitado.id == str(id)).first()
    if not invitado:
        db.close()
        return RedirectResponse(url="/?msg=Invitaci%C3%B3n+inv%C3%A1lida", status_code=303)

    if invitado.ha_asistido:
        mensaje = f"{invitado.nombre}+ya+fue+registrado"
    else:
        invitado.ha_asistido = True
        invitado.fecha_hora = datetime.now()
        db.commit()
        mensaje = f"Bienvenido+{invitado.nombre}"

    db.close()
    return RedirectResponse(url=f"/?msg={mensaje}", status_code=303)

# --- Endpoint de inicio con listado de invitados ---
@app.get("/", response_class=HTMLResponse)
def home(request: Request, msg: str = None):
    db = SessionLocal()
    invitados = db.query(Invitado).order_by(Invitado.nombre).all()
    db.close()
    return templates.TemplateResponse("inicio.html", {"request": request, "invitados": invitados, "msg": msg})

# --- Acciones administrativas ---
@app.post("/regenerar")
def regenerar_qrs():
    cargar_invitados(regenerar_qrs=True)
    return RedirectResponse(url="/?msg=QRs+regenerados", status_code=303)

@app.post("/limpiar")
def limpiar_qrs():
    for f in os.listdir(QR_DIR):
        f_path = os.path.join(QR_DIR, f)
        if os.path.isfile(f_path):
            os.remove(f_path)
    return RedirectResponse(url="/?msg=QRs+eliminados", status_code=303)

@app.post("/enviar-emails")
def enviar_emails():
    print("Simulación de envío de emails a todos los invitados...")
    return RedirectResponse(url="/?msg=Invitaciones+enviadas+(simulado)", status_code=303)

@app.post("/reset-asistencias")
def reset_asistencias():
    db = SessionLocal()
    db.query(Invitado).update({Invitado.ha_asistido: False})
    db.commit()
    db.close()
    return RedirectResponse(url="/?msg=Asistencias+reiniciadas", status_code=303)

# --- Punto de entrada ---
if __name__ == "__main__":
    import sys
    regenerar = "--regenerar" in sys.argv
    limpiar = "--limpiar" in sys.argv

    if limpiar:
        for f in os.listdir(QR_DIR):
            f_path = os.path.join(QR_DIR, f)
            if os.path.isfile(f_path):
                os.remove(f_path)
        print("QRs eliminados.")

    print(f"IP local usada: {LOCAL_IP}")
    print("Generando base de datos e invitaciones...")
    cargar_invitados(regenerar_qrs=regenerar)
    print("Listo. Ahora ejecuta 'poetry run uvicorn main:app --host 0.0.0.0 --port 8000'")
