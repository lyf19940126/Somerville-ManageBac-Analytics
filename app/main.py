from fastapi import FastAPI

app = FastAPI(title="Somerville ManageBac Analytics")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
