from fastapi import FastAPI

from audio import router as audio_router

app = FastAPI(title="SenseiAPI", version="0.1.0")

app.include_router(audio_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Welcome to SenseiAPI"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
