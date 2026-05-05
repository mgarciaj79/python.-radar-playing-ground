import asyncio
import httpx
import uvicorn
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import List, Dict
from tradingview_ta import TA_Handler, Interval

app = FastAPI(title="v7.5 High-Freq Nano")

os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

API_KEY = "b439f591-322b-41b6-839b-e9ef1a2631ec"
PRICE_HISTORY: Dict[str, float] = {}

ASSETS = {
    "BTC": {"id": "BINANCE_SPOT_BTC_USDT", "tv": "BTCUSDT"},
    "ETH": {"id": "BINANCE_SPOT_ETH_USDT", "tv": "ETHUSDT"},
    "SOL": {"id": "BINANCE_SPOT_SOL_USDT", "tv": "SOLUSDT"},
    "ORDI": {"id": "BINANCE_SPOT_ORDI_USDT", "tv": "ORDIUSDT"},
    "FLOW": {"id": "BINANCE_SPOT_FLOW_USDT", "tv": "FLOWUSDT"},
    "BIO": {"id": "BINANCE_SPOT_BIO_USDT", "tv": "BIOUSDT"},
    "KNC": {"id": "BINANCE_SPOT_KNC_USDT", "tv": "KNCUSDT"},
    "ORCA": {"id": "BINANCE_SPOT_ORCA_USDT", "tv": "ORCAUSDT"}
}


class AssetIntel(BaseModel):
    asset: str
    price: str
    rsi: int
    adx: int
    delta: str
    hit_prob: str
    squeeze_pct: str
    action: str
    alert_lvl: int
    trend: str
    signal_flag: str
    logic_lock: str
    direction: str
    macd_status: str


async def fetch_intel(symbol, current_price):
    loop = asyncio.get_event_loop()

    def sync_ta():
        try:
            # Note: INTERVAL_1_MINUTE is the fastest reliable TV-TA interval
            h = TA_Handler(symbol=symbol, exchange="BINANCE", screener="crypto", interval=Interval.INTERVAL_1_MINUTE)
            a = h.get_analysis()
            inds = a.indicators

            macd = inds.get("MACD.macd", 0)
            signal = inds.get("MACD.signal", 0)
            m_status = "BULL_CROSS" if macd > signal else "DEATH_CROSS" if macd < signal else "NEUTRAL"

            ema20, ema50 = inds.get("EMA20", 0), inds.get("EMA50", 0)
            trend = "BULL" if ema20 > ema50 else "BEAR"
            atr = max(inds.get('ATR', current_price * 0.0005), 0.00000001)
            h_val, l_val = inds.get('high', current_price + atr), inds.get('low', current_price - atr)
            pivot = (h_val + l_val + current_price) / 3
            r1, s1 = (2 * pivot) - l_val, (2 * pivot) - h_val
            sqz_val = max(5, min(99, (1 - ((r1 - s1) / (atr * 2.5))) * 100 + 40))

            return (round(inds.get('ADX', 10)), round(inds.get('RSI', 50)), trend, sqz_val, m_status, atr)
        except:
            return (10, 50, "NEUTRAL", 10, "NEUTRAL", 0.001)

    return await loop.run_in_executor(None, sync_ta)


async def fetch_price(client, asset_id):
    url = f"https://rest.coinapi.io/v1/ohlcv/{asset_id}/latest?period_id=1MIN&limit=1"
    try:
        r = await client.get(url, headers={"X-CoinAPI-Key": API_KEY}, timeout=3.0)
        return r.json()[0]['price_close']
    except:
        return 0.0


@app.get("/api/data", response_model=List[AssetIntel])
async def get_data():
    async with httpx.AsyncClient() as client:
        items = list(ASSETS.items())
        prices = await asyncio.gather(*[fetch_price(client, cfg['id']) for _, cfg in items])
        intels = await asyncio.gather(*[fetch_intel(cfg['tv'], prices[i]) for i, (_, cfg) in enumerate(items)])
        results = []
        for i, (name, _) in enumerate(items):
            price = prices[i]
            adx, rsi, trend, sqz, m_status, atr = intels[i]

            action, lvl, flag, lock, direction = "SCAN", 0, "STDBY", "IDLE", "NONE"
            if rsi > 51 and m_status == "BULL_CROSS":
                action, lvl, flag, direction = "SNIPE", 2, "FIRE", "UP"
            elif rsi < 49 and m_status == "DEATH_CROSS":
                action, lvl, flag, direction = "SNIPE", 2, "FIRE", "DOWN"

            diff = price - PRICE_HISTORY.get(name, price)
            PRICE_HISTORY[name] = price
            results.append(AssetIntel(
                asset=name, price=f"{price:,.4f}", rsi=rsi, adx=adx,
                delta=f"{'+' if diff > 0 else ''}{diff:,.4f}",
                hit_prob="HIGH", squeeze_pct=f"{sqz:.1f}%",
                action=action, alert_lvl=lvl, trend=trend,
                signal_flag=flag, logic_lock=lock, direction=direction,
                macd_status=m_status
            ))
        return results


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html", context={"request": request})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)