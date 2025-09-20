from fastapi import FastAPI
import asyncio
from myscript import run_bot  # Importa a função do seu bot

app = FastAPI(title="WhatsApp Bot API")

# Rota de saúde simples
@app.get("/")
def health_check():
    return {"status": "ok"}

# Rota para rodar o bot
@app.get("/run")
async def run_script():
    try:
        # Chama a função assíncrona do bot
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
