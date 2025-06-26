# AccessControlByQR

A lightweight FastAPI + SQLite app for managing event invitations using unique QR codes.

## 🚀 Features

- **Import contacts** from a CSV file (`invitados.csv`).
- Generate unique QR codes for each invitee, linking to a confirmation URL.
- Track attendance with timestamp logging.
- Web dashboard (`/`) shows:
  - Invitee list (name, email)
  - Attendance status ✔/✘
  - Scan timestamp (formatted DD/MM/YYYY HH:MM:SS)
  - Admin actions: Re‑generate QRs, clear QRs, reset attendance, send emails (mock)
- Flash messages and smooth UI messages banner.

## 🛠️ Requirements

- Python 3.12+
- Poetry-managed virtual environment

## 🔧 Setup & Usage

1. **Install dependencies**

   ```
   bash


   CopiarEditar
   poetry install
   ```

2. **Prepare your invitees CSV**
    Create `invitados.csv` with columns:

   ```
   csv


   CopiarEditar
   nombre,email
   Alice,alice@example.com
   Bob,bob@example.com
   ```

3. **Generate QR codes & init DB**

   ```
   bash


   CopiarEditar
   python main.py --regenerar
   ```

4. **Start the server**

   ```
   bash


   CopiarEditar
   poetry run uvicorn main:app --host 0.0.0.0 --port 8000
   ```

5. **Access the dashboard**
    Open http://localhost:8000/ (or replace with your local IP).

6. **Scan QRs to register attendance**
    Use any mobile QR reader to scan the image (PNG) in `static/qrs`, which will hit `/confirmar?id=…`, record attendance & timestamp, then redirect to the dashboard.

## ⏱️ Admin actions

- **Regenerate QRs** — recreate missing/new QRs.
- **Delete all QRs** — remove from disk.
- **Reset attendance** — clear all check-in flags and timestamps (back to default).
- **Send invitations** — placeholder/end‑point only (prints to console).

## 💡 Database setup

Uses SQLite (`invitados.db`) and SQLAlchemy ORM.
 When updating the model (e.g., adding `fecha_hora` column), either:

- Delete `invitados.db` and rerun `--regenerar`, **or**

- Apply a `ALTER TABLE` manually:

  ```
  python


  CopiarEditar
  from sqlalchemy import create_engine
  engine = create_engine('sqlite:///./invitados.db')
  engine.execute('ALTER TABLE invitados ADD COLUMN fecha_hora DATETIME')
  ```

## 📁 Project structure

```
bash


CopiarEditar
.
├── main.py           # FastAPI application
├── invitados.csv     # Contacts input
├── invitados.db      # SQLite database (auto-generated)
├── static/qrs/       # Generated QR code images
└── templates/
    └── inicio.html   # Dashboard template
```

## ✅ Next improvements

- Add live updates to the dashboard via WebSockets or Server-Sent Events.
- Implement real email sending using SMTP/AWS SES/SendGrid.
- Add authentication to restrict dashboard access.
- Export attendance report (CSV, PDF).
