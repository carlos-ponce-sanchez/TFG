from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.ml.predict import load_model, analyze_email_text


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"


class TextRequest(BaseModel):
    text: str


app = FastAPI(title="Detector de Phishing (EN/ES)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


model_pipeline = load_model()


@app.post("/api/predict-text")
async def predict_text(payload: TextRequest):
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="El texto del correo no puede estar vacío.")

    result = analyze_email_text(model_pipeline, text)
    return result


@app.post("/api/predict-file")
async def predict_file(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="Debes subir al menos un fichero.")

    analyses = []
    for f in files:
        raw = await f.read()
        try:
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            raise HTTPException(status_code=400, detail=f"No se ha podido leer el fichero: {f.filename}")

        analysis = analyze_email_text(model_pipeline, text)
        analyses.append({"filename": f.filename, **analysis})

    return {"results": analyses}


if FRONTEND_DIR.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(FRONTEND_DIR), html=True),
        name="frontend",
    )

