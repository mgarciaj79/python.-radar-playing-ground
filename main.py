import asyncio, httpx, uvicorn, os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from tradingview_ta import TA_Handler, Interval

app = FastAPI(title="SHARKY V12.8 // PROBABILITY-ENGINE")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

base_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

API_KEY = "b439f591-322b-41b6-839b-e9ef1a2631ec"

SYMBOLS = {
    "BTC": "BINANCE", "TON": "BINANCE", "SUI": "BINANCE",
    "ETH": "BINANCE", "SOL": "BINANCE", "LINK": "BINANCE",
    "HBAR": "BINANCE", "AKT": "KRAKEN"
}


async def fetch_signals(name, exchange, client):
    loop = asyncio.get_event_loop()

    price, volume = 0.0, 0.0
    try:
        p_url = f"https://rest.coinapi.io/v1/exchangerate/{name}/USDT"
        r = await client.get(p_url, headers={"X-CoinAPI-Key": API_KEY}, timeout=3.0)
        if r.status_code == 200:
            price = float(r.json().get('rate', 0.0))

        v_url = f"https://rest.coinapi.io/v1/symbols?filter_symbol_id={exchange}_SPOT_{name}_USDT"
        v_r = await client.get(v_url, headers={"X-CoinAPI-Key": API_KEY}, timeout=3.0)
        if v_r.status_code == 200 and v_r.json():
            volume = float(v_r.json()[0].get('volume_1day_usd', 0.0))
    except:
        pass

    def get_ta():
        try:
            h = TA_Handler(symbol=f"{name}USDT", exchange=exchange, screener="crypto",
                           interval=Interval.INTERVAL_30_MINUTES)
            return h.get_analysis().indicators
        except:
            return None

    inds = await loop.run_in_executor(None, get_ta)
    close = price if price > 0 else (inds.get('close', 1.0) if inds else 1.0)

    # DEFAULT VALUES
    atr, boost, adx, rsi, macd, snipe_prob = close * 0.001, 15.0, 20.0, 50.0, 0.0, 5.0

    if inds:
        atr = float(inds.get('ATR') or inds.get('Average.True.Range') or (close * 0.0014))
        bb_w = float(inds.get('BB.upper', 0) - inds.get('BB.lower', 0))
        kc_w = float(inds.get('KC.upper', 0) - inds.get('KC.lower', 0))

        # SQUEEZE PROBABILITY MATH
        # Ratio < 1.0 means BB is inside KC (The Squeeze)
        sqz_ratio = bb_w / kc_w if kc_w > 0 else 1.0
        pressure = (kc_w / bb_w) if bb_w > 0 else 1.1
        boost = float(min(max((pressure - 0.4) * 180, 10), 100))

        # Probability scales as BB gets tighter inside KC + ADX trend build
        raw_prob = (1.1 - sqz_ratio) * 150
        snipe_prob = min(max(raw_prob + (float(inds.get('ADX', 20)) * 0.4), 5), 98.5)

        adx, rsi = float(inds.get('ADX', 20)), float(inds.get('RSI', 50))
        macd = float(inds.get('MACD.hist', 0.0))

    # Biometric States
    if boost > 85 and adx > 25:
        status, color = "SNIPING", ("#39FF14" if macd >= 0 else "#FF00FF")
    elif boost > 70:
        status, color = "SQUEEZING", "#FF4D00"
    else:
        status, color = "BREATHING", "#9D00FF"

    return {
        "asset": name, "price": close, "volume": volume, "rsi": rsi, "adx": adx,
        "atr": atr, "boost": boost, "status": status, "color": color,
        "snipe_prob": round(snipe_prob, 1),
        "rotation": (boost * 1.8) - 90, "target": close + (atr * 1.6), "stop": close - (atr * 0.8)
    }


@app.get("/api/data")
async def api_endpoint():
    async with httpx.AsyncClient() as client:
        res = await asyncio.gather(*[fetch_signals(n, ex, client) for n, ex in SYMBOLS.items()])
        valid_results = [r for r in res if r is not None]
        # Sort by Probability first, then Volume
        return sorted(valid_results, key=lambda x: (x['snipe_prob'], x['volume']), reverse=True)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)