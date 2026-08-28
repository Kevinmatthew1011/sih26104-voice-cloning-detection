# Local Development Setup Guide: SIH26104

## 1. Prerequisites

- **Operating System**: Linux (Ubuntu 22.04+ / Debian), macOS, or Windows (WSL2).
- **Python**: Version 3.11, 3.12, 3.13, or 3.14.
- **Node.js**: Version 18.x, 20.x, or 22.x (with `npm`).
- **FFmpeg**: Version 6.x or 7.x development libraries (for PyAV audio decoding).

---

## 2. Backend Setup & Startup

```bash
# 1. Navigate to backend directory
cd backend

# 2. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configure environment
cp ../.env.example .env

# 5. Run backend tests
pytest

# 6. Start FastAPI development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Backend API will be available at `http://localhost:8000`.  
Swagger documentation at `http://localhost:8000/docs`.

---

## 3. Frontend Setup & Startup

```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install Node dependencies
npm install

# 3. Build and test frontend
npm run build

# 4. Start Next.js development server
npm run dev
```

Frontend UI will be available at `http://localhost:3000`.

---

## 4. Verifying Local Installation

1. Open `http://localhost:3000` in your web browser.
2. Navigate to `http://localhost:3000/detect`.
3. Submit a test audio file or record via microphone to verify that the deep learning model and decision engine execute successfully.
