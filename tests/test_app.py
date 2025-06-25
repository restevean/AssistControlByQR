import os
import sqlite3
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from main import Base
import main as app_main


@pytest.fixture()
def client(tmp_path, monkeypatch):
    tmp_csv = tmp_path / "invitados.csv"
    df = pd.DataFrame(
        [
            {"nombre": "Alice", "email": "alice@example.com"},
            {"nombre": "Bob", "email": "bob@example.com"},
        ]
    )
    df.to_csv(tmp_csv, index=False)
    monkeypatch.setattr(app_main, "CSV_PATH", str(tmp_csv))

    tmp_qr = tmp_path / "qrs"
    tmp_qr.mkdir()
    monkeypatch.setattr(app_main, "QR_DIR", str(tmp_qr))

    tmp_db = tmp_path / "test.db"
    monkeypatch.setattr(app_main, "DB_PATH", f"sqlite:///{tmp_db}")

    app_main.engine = create_engine(
        app_main.DB_PATH, connect_args={"check_same_thread": False}
    )
    app_main.SessionLocal.configure(bind=app_main.engine)
    Base.metadata.drop_all(bind=app_main.engine)
    Base.metadata.create_all(bind=app_main.engine)

    return TestClient(app_main.app)


def test_regenerate_and_csv_load(client):
    resp = client.post("/regenerar", follow_redirects=False)
    assert resp.status_code == 303
    qr_files = os.listdir(app_main.QR_DIR)
    assert any("Alice" in fn for fn in qr_files)
    assert any("Bob" in fn for fn in qr_files)


def test_confirm_entry_exit(client):
    client.post("/regenerar", follow_redirects=False)
    conn = sqlite3.connect(app_main.engine.url.database)
    alice_id = conn.execute("SELECT id FROM invitados WHERE nombre='Alice'").fetchone()[
        0
    ]
    conn.close()

    r1 = client.get(f"/confirmar?id={alice_id}", follow_redirects=False)
    assert r1.status_code == 303
    assert (
        "Bienvenido+Alice" in r1.headers["location"]
        or "Entrada+registrada+para+Alice" in r1.headers["location"]
    )

    r2 = client.get(f"/confirmar?id={alice_id}", follow_redirects=False)
    assert "Salida+registrada+para+Alice" in r2.headers["location"]

    conn = sqlite3.connect(app_main.engine.url.database)
    asistencia = conn.execute(
        "SELECT fecha_entrada, fecha_salida FROM asistencias WHERE invitado_id=? ORDER BY fecha_entrada DESC",
        (alice_id,),
    ).fetchone()
    assert asistencia[0] is not None and asistencia[1] is not None
    conn.close()


def test_multiple_entry_exit_cycles(client):
    client.post("/regenerar", follow_redirects=False)
    conn = sqlite3.connect(app_main.engine.url.database)
    alice_id = conn.execute("SELECT id FROM invitados WHERE nombre='Alice'").fetchone()[
        0
    ]
    conn.close()

    for i in range(2):
        r1 = client.get(f"/confirmar?id={alice_id}", follow_redirects=False)
        assert r1.status_code == 303
        assert (
            "Entrada+registrada+para+Alice" in r1.headers["location"]
            or "Bienvenido+Alice" in r1.headers["location"]
        )

        r2 = client.get(f"/confirmar?id={alice_id}", follow_redirects=False)
        assert r2.status_code == 303
        assert "Salida+registrada+para+Alice" in r2.headers["location"]

    conn = sqlite3.connect(app_main.engine.url.database)
    rows = conn.execute(
        "SELECT fecha_entrada, fecha_salida FROM asistencias WHERE invitado_id=?",
        (alice_id,),
    ).fetchall()
    assert len(rows) == 2
    for entrada, salida in rows:
        assert entrada is not None and salida is not None
    conn.close()


def test_reset_and_clear(client):
    client.post("/regenerar", follow_redirects=False)
    r = client.post("/reset-asistencias", follow_redirects=False)
    assert r.status_code == 303 and "Asistencias+reiniciadas" in r.headers["location"]

    conn = sqlite3.connect(app_main.engine.url.database)
    count = conn.execute("SELECT COUNT(*) FROM asistencias").fetchone()[0]
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
