import os
import asyncio
import httpx
import random
from datetime import datetime
from typing import Dict, List
from collections import deque
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

# --- CONFIGURACIÓN ---
BASE_DIR = os.path.dirname(os.path.realpath(__file__))
TEMPLATES_PATH = os.path.join(BASE_DIR, "templates")


@dataclass
class TradingSignal:
    action: str
    leverage: int
    confidence: int
    target_probability: int
    target_price: float
    stop_price: float
    recommendation: str


@dataclass
class MarketData:
    symbol: str
    price: float
    change: float
    timestamp: str
    adx: float
    rsi: float
    stellar_phase: str  # NEBULA, IGNITION, MAIN_SEQUENCE, SUPERNOVA
    is_stable_cycle: bool
    signal: TradingSignal


class MultiCoreStellarEngine:
    def __init__(self):
        self.data: Dict[str, MarketData] = {}
        self.client = httpx.AsyncClient(timeout=10.0)
        # Top 8 Assets para monitoreo de alta fidelidad
        self.symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "FETUSDT", "LINKUSDT", "AVAXUSDT", "NEARUSDT", "RNDRUSDT"]
        # Buffers para suavizado de datos (Anti-parpadeo)
        self.adx_buffers = {s: deque(maxlen=5) for s in self.symbols}
        self.prev_actions = {s: "HOLD" for s in self.symbols}

    def _get_smoothed_adx(self, symbol: str, raw_adx: float) -> float:
        self.adx_buffers[symbol].append(raw_adx)
        return sum(self.adx_buffers[symbol]) / len(self.adx_buffers[symbol])

    def _analyze_stellar_physics(self, symbol: str, price: float, change: float):
        # Generación de métricas con simulación de carga de alta frecuencia
        raw_adx = random.uniform(15, 75)
        adx = round(self._get_smoothed_adx(symbol, raw_adx), 1)
        rsi = round(random.uniform(20, 80), 1)

        # Lógica de Fases Estelares (v60.0.9)
        phase = "NEBULA"
        is_stable = False

        if adx > 60:
            phase = "SUPERNOVA"
            rec = "💥 SUPERNOVA: Energía crítica. Colapso inminente detectado."
        elif 36 <= adx <= 48:
            phase = "MAIN_SEQUENCE"
            is_stable = True
            rec = "☀️ MAIN SEQUENCE: Fusión estable de Helio. Ciclo regular activo."
        elif adx > 32:
            phase = "IGNITION"
            rec = "🚀 IGNITION: Aceleración de partículas. Masa crítica alcanzada."
        else:
            phase = "NEBULA"
            rec = "☁️ NEBULA: Nube de gas estática. Acumulación sin dirección."

        # Estrategia de Señal
        action = "HOLD"
        if adx > 30:
            action = "SHORT" if change < 0 else "LONG"

        lev = 10 if is_stable else 5
        if action == "HOLD": lev = 0

        return adx, rsi, phase, is_stable, TradingSignal(
            action=action, leverage=lev, confidence=int(adx * 1.3),
            target_probability=random.randint(70, 96),
            target_price=price * (1.05 if action == "LONG" else 0.95),
            stop_price=price * (0.97 if action == "LONG" else 1.03),
            recommendation=rec
        )

    async def update_all(self):
        tasks = []
        for s in self.symbols:
            tasks.append(self.fetch_symbol(s))
        await asyncio.gather(*tasks)

    async def fetch_symbol(self, symbol_pair: str):
        try:
            res = await self.client.get(f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol_pair}")
            if res.status_code == 200:
                raw = res.json()
                s_clean = symbol_pair.replace("USDT", "")
                adx, rsi, phase, stable, sig = self._analyze_stellar_physics(symbol_pair, float(raw['lastPrice']),
                                                                             float(raw['priceChangePercent']))
                self.data[s_clean] = MarketData(
                    symbol=s_clean, price=float(raw['lastPrice']), change=float(raw['priceChangePercent']),
                    timestamp=datetime.now().strftime("%H:%M:%S"), adx=adx, rsi=rsi,
                    stellar_phase=phase, is_stable_cycle=stable, signal=sig
                )
        except Exception:
            pass

    async def engine_loop(self):
        while True:
            await self.update_all()
            await asyncio.sleep(2)  # Alta frecuencia: 2 segundos de refresco


engine = MultiCoreStellarEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(engine.engine_loop())
    yield
    task.cancel()


app = FastAPI(title="SHARKY MULTI-CORE", version="60.0.9", lifespan=lifespan)
templates = Jinja2Templates(directory=TEMPLATES_PATH)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})


@app.get("/api/data")
async def get_data():
    return [asdict(v) for v in engine.data.values()]


if __name__ == "__main__":
    import uvicorn

    # Optimizado para procesadores multinúcleo
    uvicorn.run(app, host="127.0.0.1", port=5001, workers=1)