# inicio.html

import os
import sqlite3
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from main import Base, engine
import main as app_main

TEMPLATE_CONTENT = """
<html>
<head><title>Test</title></head>
<body>
  {% for invitado in invitados %}
    {{ invitado.nombre }}
  {% endfor %}
</body>
</html>
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Create temp CSV
    tmp_csv = tmp_path / "invitados.csv"
    df = pd.DataFrame(
        [
            {"nombre": "Alice", "email": "alice@example.com"},
            {"nombre": "Bob", "email": "bob@example.com"},
        ]
    )
    df.to_csv(tmp_csv, index=False)
    monkeypatch.setattr(app_main, "CSV_PATH", str(tmp_csv))

    # Create temp QR dir
    tmp_qr = tmp_path / "qrs"
    tmp_qr.mkdir()
    monkeypatch.setattr(app_main, "QR_DIR", str(tmp_qr))

    # Create temp DB
    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(app_main, "DB_PATH", f"sqlite:///{tmp_db}")
    # Recreate engine
    app_main.engine = create_engine(
        app_main.DB_PATH, connect_args={"check_same_thread": False}
    )
    Base.metadata.drop_all(bind=app_main.engine)
    Base.metadata.create_all(bind=app_main.engine)

    # Create dummy templates dir
    tmp_templates = tmp_path / "templates"
    tmp_templates.mkdir()
    (tmp_templates / "inicio.html").write_text(TEMPLATE_CONTENT)
    monkeypatch.setattr(app_main, "TEMPLATES_DIR", str(tmp_templates))
    app_main.templates = app_main.Jinja2Templates(directory=str(tmp_templates))

    return TestClient(app_main.app)


def test_regenerate_and_csv_load(client):
    resp = client.post("/regenerar", follow_redirects=False)
    assert resp.status_code == 303
    qr_files = os.listdir(app_main.QR_DIR)
    assert any("Alice" in fn for fn in qr_files)
    assert any("Bob" in fn for fn in qr_files)

    resp_home = client.get("/")
    assert "Alice" in resp_home.text
    assert "Bob" in resp_home.text


def test_confirm_attendance(client):
    client.post("/regenerar", follow_redirects=False)
    conn = sqlite3.connect(engine.url.database)
    alice_id = conn.execute("SELECT id FROM invitados WHERE nombre='Alice'").fetchone()[
        0
    ]
    conn.close()

    r1 = client.get(f"/confirmar?id={alice_id}", follow_redirects=False)
    assert r1.status_code == 303 and "Bienvenido+Alice" in r1.headers["location"]

    r2 = client.get(f"/confirmar?id={alice_id}", follow_redirects=False)
    assert "Alice+ya+fue+registrado" in r2.headers["location"]

    conn = sqlite3.connect(engine.url.database)
    row = conn.execute(
        "SELECT ha_asistido, fecha_hora FROM invitados WHERE id=?", (alice_id,)
    ).fetchone()
    assert row[0] == 1 and row[1] is not None
    conn.close()


def test_reset_and_clear(client):
    client.post("/regenerar", follow_redirects=False)
    r = client.post("/reset-asistencias", follow_redirects=False)
    assert r.status_code == 303 and "Asistencias+reiniciadas" in r.headers["location"]

    conn = sqlite3.connect(engine.url.database)
    count = conn.execute(
        "SELECT COUNT(*) FROM invitados WHERE ha_asistido=1"
    ).fetchone()[0]
    assert count == 0
    conn.close()

    client.post("/regenerar", follow_redirects=False)
    assert os.listdir(app_main.QR_DIR)
    r2 = client.post("/limpiar", follow_redirects=False)
    assert "QRs+eliminados" in r2.headers["location"]
    assert os.listdir(app_main.QR_DIR) == []


def test_send_emails(client, capsys):
    r = client.post("/enviar-emails", follow_redirects=False)
    assert r.status_code == 303 and "Invitaciones+enviadas" in r.headers["location"]
    captured = capsys.readouterr()
    assert "Simulación de envío de emails" in captured.out
