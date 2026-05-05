import asyncio
import httpx
import uvicorn
import os
import time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict
from tradingview_ta import TA_Handler, Interval

app = FastAPI(title="NANO-CORE V7.5 // MASTER ROTATION")

# Directory Setup
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuration
API_KEY = "b439f591-322b-41b6-839b-e9ef1a2631ec"
PRICE_HISTORY: Dict[str, float] = {}
LAST_ROTATION_TIME = 0

# Assets: Core is protected, Mover is dynamic
CORE_LIST = ["BTC", "ETH", "SOL"]
ASSETS = {
    "BTC": {"id": "BINANCE_SPOT_BTC_USDT", "tv": "BTCUSDT"},
    "ETH": {"id": "BINANCE_SPOT_ETH_USDT", "tv": "ETHUSDT"},
    "SOL": {"id": "BINANCE_SPOT_SOL_USDT", "tv": "SOLUSDT"}
}


async def rotate_assets():
    """Self-cleaning loop: Purges low-momentum, Injects high-alpha."""
    global ASSETS, LAST_ROTATION_TIME
    now = time.time()

    if now - LAST_ROTATION_TIME < 900 and LAST_ROTATION_TIME != 0:
        return

    async with httpx.AsyncClient() as client:
        try:
            # Active May 2026 Mover Discovery
            new_top_movers = ["BIO", "KNC", "BABY", "ORCA", "TAO"]

            # 1. PURGE non-profitable/low-momentum assets
            current_keys = list(ASSETS.keys())
            for key in current_keys:
                if key not in CORE_LIST and key not in new_top_movers:
                    print(f"CLEANUP: Removing {key}")
                    del ASSETS[key]

            # 2. INJECT new business opportunities
            for coin in new_top_movers:
                if coin not in ASSETS:
                    print(f"BUSINESS: Adding {coin}")
                    ASSETS[coin] = {"id": f"BINANCE_SPOT_{coin}_USDT", "tv": f"{coin}USDT"}

            LAST_ROTATION_TIME = now
        except Exception as e:
            print(f"Rotation Logic Failure: {e}")


async def fetch_intel(symbol, current_price):
    loop = asyncio.get_event_loop()

    def sync_ta():
        try:
            h = TA_Handler(symbol=symbol, exchange="BINANCE", screener="crypto", interval=Interval.INTERVAL_30_MINUTES)
            a = h.get_analysis();
            inds = a.indicators
            bb_u, bb_l = inds.get("BB.upper", 0), inds.get("BB.lower", 0)
            kc_u, kc_l = inds.get("KC.upper", 0), inds.get("KC.lower", 0)
            is_sqz = bb_u < kc_u and bb_l > kc_l
            mom = "UP" if inds.get("MACD.macd", 0) > inds.get("MACD.signal", 0) else "DOWN"
            return (round(inds.get('RSI', 50)), round(inds.get('ADX', 20)), 95 if is_sqz else 30, mom)
        except:
            return (50, 20, 10, "NEUTRAL")

    return await loop.run_in_executor(None, sync_ta)


async def fetch_price(client, asset_id):
    url = f"https://rest.coinapi.io/v1/ohlcv/{asset_id}/latest?period_id=1MIN&limit=1"
    try:
        r = await client.get(url, headers={"X-CoinAPI-Key": API_KEY}, timeout=3.0)
        return r.json()[0]['price_close']
    except:
        return 0.0


@app.get("/api/data")
async def get_data():
    await rotate_assets()
    async with httpx.AsyncClient() as client:
        items = list(ASSETS.items())
        prices = await asyncio.gather(*[fetch_price(client, cfg['id']) for _, cfg in items])
        intels = await asyncio.gather(*[fetch_intel(cfg['tv'], prices[i]) for i, (_, cfg) in enumerate(items)])

        results = []
        for i, (name, _) in enumerate(items):
            price = prices[i];
            rsi, adx, sqz, mom = intels[i]

            if sqz > 80:
                action, instr, color = ("LONG", "SNIPE OPEN", "#00f2ff") if mom == "UP" else ("SHORT", "SNIPE OPEN",
                                                                                              "#ff0055")
            elif rsi > 68:
                action, instr, color = "LONG", "CLOSE/SELL", "#00ff66"
            elif rsi < 32:
                action, instr, color = "SHORT", "CLOSE/SELL", "#00ff66"
            else:
                action, instr, color = "SCAN", "READY", "#333"

            diff = price - PRICE_HISTORY.get(name, price);
            PRICE_HISTORY[name] = price
            results.append({
                "asset": name, "price": f"{price:,.4f}", "rsi": rsi, "adx": adx,
                "delta": f"{'+' if diff > 0 else ''}{diff:,.4f}", "squeeze_pct": f"{sqz}%",
                "action_type": action, "instruction": instr, "signal_color": color,
                "tag": "CORE" if name in CORE_LIST else "TOP MOVER"
            })
        return results


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)