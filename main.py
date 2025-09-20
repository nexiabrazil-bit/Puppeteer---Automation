from fastapi import FastAPI
import asyncio
from myscript import run_bot

app = FastAPI(title="WhatsApp Bot API")

@app.get("/")
def health_check():
    return {"status": "ok"}

@app.get("/run")
async def run_script():
    try:
        results = await run_bot()
        return {
            "status": "done",
            "found_numbers": results,
            "message": f"{len(results)} números processados com sucesso"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
