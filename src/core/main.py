from fastapi import FastAPI

app = FastAPI(title="memward API")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}