from fastapi import FastAPI
import asyncio
from myscript import run_bot

app = FastAPI()

@app.get("/")
def health():
    return {"status": "ok"}

@app.get("/run")
async def run_script():
    try:
        await run_bot()
        return {"status": "done"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
