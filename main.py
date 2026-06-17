from fastapi import FastAPI

app = FastAPI(title="SenseiAPI", version="0.1.0")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Welcome to SenseiAPI"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
