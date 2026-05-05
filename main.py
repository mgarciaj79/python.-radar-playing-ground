import asyncio, httpx, uvicorn, os, time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from tradingview_ta import TA_Handler, Interval

app = FastAPI(title="PSYCHO-MASTER V12.8 // HYPER-SYNC")
os.makedirs("templates", exist_ok=True)
templates = Jinja2Templates(directory="templates")

API_KEY = "b439f591-322b-41b6-839b-e9ef1a2631ec"

SYMBOLS = {
    "BTC": "BINANCE_SPOT_BTC_USDT",
    "TON": "BINANCE_SPOT_TON_USDT",
    "SUI": "BINANCE_SPOT_SUI_USDT",
    "ETH": "BINANCE_SPOT_ETH_USDT",
    "SOL": "BINANCE_SPOT_SOL_USDT",
    "LINK": "BINANCE_SPOT_LINK_USDT",
    "HBAR": "BINANCE_SPOT_HBAR_USDT",
    "AKT": "BINANCE_SPOT_AKT_USDT"
}


async def fetch_signals(name, symbol_id, client):
    loop = asyncio.get_event_loop()

    def get_pro_math():
        try:
            # Shifted to 1-minute interval for hyper-responsive scalping
            handler = TA_Handler(symbol=name + "USDT", exchange="BINANCE", screener="crypto",
                                 interval=Interval.INTERVAL_1_MINUTE)
            inds = handler.get_analysis().indicators

            rsi, adx = inds.get('RSI', 50), inds.get('ADX', 20)
            atr, close = inds.get('ATR', 0), inds.get('close', 1)

            # Volatility Fallback (Optimized for $81k range)
            effective_atr = atr if atr > 0 else (close * 0.0005)

            bb_w = (inds.get('BB.upper', 0) - inds.get('BB.lower', 0))
            kc_w = (inds.get('KC.upper', 0) - inds.get('KC.lower', 0))

            # Squeeze Intensity for Needle Sweep
            pressure_raw = (kc_w / bb_w) * 10 if bb_w > 0 else 5
            boost_pct = min(max(pressure_raw * 10, 0), 100)
            rotation = (boost_pct * 1.8) - 90

            is_snipe = boost_pct > 85 and adx > 25
            alert_msg = f"FIRE SIGNAL: {name} Sniped" if is_snipe else (f"COILING: {name}" if boost_pct > 70 else None)

            vol = (effective_atr / close) * 100 if close > 0 else 0
            lev_final = min(max(round(2.0 / vol), 1), 50) if vol > 0 else 10

            return (rsi, adx, effective_atr, rotation, boost_pct, is_snipe, alert_msg, close, lev_final)
        except:
            return (50, 20, 0.0001, -90, 0, False, None, 0, 5)

    price = 0.0
    try:
        # Prioritize ExchangeRate for the most current 'breathing' price
        url = f"https://rest.coinapi.io/v1/exchangerate/{name}/USDT"
        r = await client.get(url, headers={"X-CoinAPI-Key": API_KEY}, timeout=5.0)
        price = r.json().get('rate', 0.0)
    except:
        pass

    rsi, adx, atr, rot, pct, snipe, alert, ta_p, lev = await loop.run_in_executor(None, get_pro_math)
    final_p = price if price > 0 else ta_p

    return {
        "asset": name, "price": final_p, "rsi": rsi, "adx": adx, "atr": round(atr, 4),
        "rotation": rot, "boost": pct, "is_snipe": snipe, "alert_msg": alert,
        "target": final_p + (atr * 1.5), "stop": final_p - (atr * 0.5), "max_lev": f"{lev}x",
        "color": "#00FF7F" if snipe else "#FF8C00" if pct > 70 else "#8A2BE2"
    }


@app.get("/api/data")
async def api_endpoint():
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[fetch_signals(n, sid, client) for n, sid in SYMBOLS.items()],
                                       return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=5000)