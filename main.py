import asyncio
import httpx
import uvicorn
import os
import time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from tradingview_ta import TA_Handler, Interval

# INITIALIZATION
app = FastAPI(title="NANO-CORE // PSYCHO-COMPACT-V8.7")

# Ensure directories exist
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

API_KEY = "b439f591-322b-41b6-839b-e9ef1a2631ec"

# HIGH DENSITY ASSET LIST
ASSETS = {
    "BTC": {"id": "BINANCE_SPOT_BTC_USDT", "tv": "BTCUSDT"},
    "ETH": {"id": "BINANCE_SPOT_ETH_USDT", "tv": "ETHUSDT"},
    "SOL": {"id": "BINANCE_SPOT_SOL_USDT", "tv": "SOLUSDT"},
    "BIO": {"id": "BINANCE_SPOT_BIO_USDT", "tv": "BIOUSDT"},
    "KNC": {"id": "BINANCE_SPOT_KNC_USDT", "tv": "KNCUSDT"},
    "BABY": {"id": "BINANCE_SPOT_BABY_USDT", "tv": "BABYUSDT"}
}


async def fetch_data(name, cfg, client):
    loop = asyncio.get_event_loop()

    def get_ta():
        try:
            h5 = TA_Handler(symbol=cfg['tv'], exchange="BINANCE", screener="crypto",
                            interval=Interval.INTERVAL_5_MINUTES)
            a5 = h5.get_analysis();
            inds = a5.indicators
            bb_u, bb_l = inds.get("BB.upper", 0), inds.get("BB.lower", 0)
            kc_u, kc_l = inds.get("KC.upper", 0), inds.get("KC.lower", 0)
            is_sqz = bb_u < kc_u and bb_l > kc_l
            close = inds.get('close', 1)
            bw = ((bb_u - bb_l) / close) * 100
            atr = inds.get('ATR', 0)
            # Leverage Calculation (Educated Business)
            lev = min(max(round(0.02 / (((atr if atr > 0 else 0.01) * 1.5) / close)), 1), 50)
            return (round(inds.get('RSI', 50)), round(inds.get('ADX', 20)), 95 if is_sqz else 30, atr, lev, bw)
        except:
            return (50, 20, 10, 0, 1, 0)

    url = f"https://rest.coinapi.io/v1/ohlcv/{cfg['id']}/latest?period_id=1MIN&limit=1"
    try:
        r = await client.get(url, headers={"X-CoinAPI-Key": API_KEY}, timeout=3.0)
        price = r.json()[0]['price_close']
    except:
        price = 0.0

    rsi, adx, sqz, atr, lev, bw = await loop.run_in_executor(None, get_ta)

    if sqz > 80:
        state, instr, color = "COILING", "SNIPE", "#00d4ff"
    elif bw > 8:
        state, instr, color = "BREATHING", "RELOAD", "#ff8c00"
    else:
        state, instr, color = "IDLE", "SCAN", "#8a2be2"

    return {
        "asset": name, "price": f"{price:,.2f}", "rsi": rsi, "adx": adx,
        "sqz": f"{sqz}%", "state": state, "instr": instr, "color": color,
        "atr": f"{atr:,.4f}", "lev": f"{lev}x", "bw": f"{bw:,.2f}%"
    }


@app.get("/api/data")
async def api_data():
    async with httpx.AsyncClient() as client:
        return await asyncio.gather(*[fetch_data(n, c, client) for n, c in ASSETS.items()])


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # CRITICAL FIX: Pass 'request' as the FIRST positional argument
    # This satisfies older Starlette versions while keeping context for Jinja2
    return templates.TemplateResponse(
        request,
        "index.html",
        {"request": request}
    )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)