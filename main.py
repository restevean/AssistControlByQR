from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from uuid import uuid4, UUID
from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey, desc
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import pandas as pd
import qrcode
import os
from datetime import datetime

# Configuration
DB_PATH = "sqlite:///./invitados.db"
CSV_PATH = "invitados.csv"
QR_DIR = "static/qrs"
TEMPLATES_DIR = "templates"
LOCAL_IP = "192.168.28.186"

# Create needed directories
for path in ["static", QR_DIR, TEMPLATES_DIR]:
    os.makedirs(path, exist_ok=True)


# Inicialization
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Models
class Invitado(Base):
    __tablename__ = "invitados"
    id = Column(String, primary_key=True, index=True)
    nombre = Column(String, nullable=False)
    email = Column(String, nullable=True, unique=True)
    asistencias = relationship("Asistencia", back_populates="invitado")


class Asistencia(Base):
    __tablename__ = "asistencias"
    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid4()))
    invitado_id = Column(String, ForeignKey("invitados.id"))
    fecha_entrada = Column(DateTime, nullable=True)
    fecha_salida = Column(DateTime, nullable=True)

    invitado = relationship("Invitado", back_populates="asistencias")


Base.metadata.create_all(bind=engine)


# CSV load and QR generation
def cargar_invitados(regenerar_qrs: bool = False):
    df = pd.read_csv(CSV_PATH)
    db = SessionLocal()
    for _, row in df.iterrows():
        nombre = row["nombre"]
        email = row.get("email", None)

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


@app.get("/confirmar")
def confirmar_asistencia(id: UUID):
    db = SessionLocal()
    invitado = db.query(Invitado).filter(Invitado.id == str(id)).first()
    if not invitado:
        db.close()
        return RedirectResponse(url="/?msg=Invitaci%C3%B3n+inv%C3%A1lida", status_code=303)

    ultima = (
        db.query(Asistencia).filter(Asistencia.invitado_id == str(id)).order_by(desc(Asistencia.fecha_entrada)).first()
    )
    ahora = datetime.now()

    if not ultima or (ultima and ultima.fecha_salida is not None):
        nueva = Asistencia(invitado_id=str(id), fecha_entrada=ahora)
        db.add(nueva)
        mensaje = f"Bienvenido+{invitado.nombre}" if not ultima else f"Entrada+registrada+para+{invitado.nombre}"
    else:
        ultima.fecha_salida = ahora
        mensaje = f"Salida+registrada+para+{invitado.nombre}"

    db.commit()
    db.close()
    return RedirectResponse(url=f"/?msg={mensaje}", status_code=303)


@app.get("/", response_class=HTMLResponse)
def home(request: Request, msg: str = None):
    db = SessionLocal()
    asistencias = db.query(Asistencia).join(Invitado).order_by(Asistencia.fecha_entrada).all()
    datos = [
        {
            "nombre": a.invitado.nombre,
            "email": a.invitado.email,
            "fecha_entrada": a.fecha_entrada,
            "fecha_salida": a.fecha_salida,
        }
        for a in asistencias
    ]
    db.close()
    return templates.TemplateResponse("inicio.html", {"request": request, "invitados": datos, "msg": msg})


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
    db.query(Asistencia).delete()
    db.commit()
    db.close()
    return RedirectResponse(url="/?msg=Asistencias+reiniciadas", status_code=303)


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
