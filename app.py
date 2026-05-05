import time
import random
import requests
from flask import Flask, jsonify, render_template
from tradingview_ta import TA_Handler, Interval
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# ==========================================================
# 15X RADAR CONFIGURATION (V3.0 - RSI/ATR/ARROWS)
# ==========================================================
API_KEY = "b439f591-322b-41b6-839b-e9ef1a2631ec"
FNG_API = "https://api.alternative.me/fng/"

session = requests.Session()
session.headers.update({"X-CoinAPI-Key": API_KEY})

ASSETS = {
    "BTC": {"id": "BINANCE_SPOT_BTC_USDT", "tv": "BTCUSDT", "target": 81500.0},
    "ETH": {"id": "BINANCE_SPOT_ETH_USDT", "tv": "ETHUSDT", "target": 2500.0},
    "SOL": {"id": "BINANCE_SPOT_SOL_USDT", "tv": "SOLUSDT", "target": 100.0},
    "ORCA": {"id": "BINANCE_SPOT_ORCA_USDT", "tv": "ORCAUSDT", "target": 2.50},
    "LDO": {"id": "BINANCE_SPOT_LDO_USDT", "tv": "LDOUSDT", "target": 4.50}
}


def fetch_precision_intel(asset_tuple):
    asset, cfg, sentiment, index = asset_tuple
    time.sleep(index * 0.15)

    try:
        # 1. TradingView 1H Analysis (RSI, ATR, ADX)
        try:
            handler = TA_Handler(symbol=cfg['tv'], exchange="BINANCE", screener="crypto",
                                 interval=Interval.INTERVAL_1_HOUR)
            analysis = handler.get_analysis()

            adx = round(analysis.indicators.get('ADX', 20))
            rsi = round(analysis.indicators.get('RSI', 50))
            # ATR often requires manual calculation or specific library access;
            # here we pull the volatility indicator or fallback to a standard range
            atr = analysis.indicators.get('ATR', 0.0)
            rec = analysis.summary.get('RECOMMENDATION', 'STABILIZING')
        except:
            adx, rsi, atr, rec = 20, 50, 0, "SYNCING"

        # 2. CoinAPI High-Precision Pulse
        url = f"https://rest.coinapi.io/v1/ohlcv/{cfg['id']}/latest?period_id=5SEC&limit=1"
        r = session.get(url, timeout=10)

        if r.status_code == 200 and r.json():
            price = r.json()[0]['price_close']

            # Probability Math
            proximity = 100 - (abs(cfg['target'] - price) / price * 450)

            # Force Recommendation Logic based on current Green Candle Momentum
            final_rec = rec
            if rsi > 55 and price > (cfg['target'] * 0.95):
                final_rec = "STRONG BUY"
            elif rsi < 45:
                final_rec = "BEARISH BIAS"

            return {
                "asset": asset, "price": f"{price:,.2f}", "adx": adx,
                "rsi": rsi, "atr": f"{atr:.4f}", "prob": f"{proximity:.1f}%",
                "rec": final_rec,
                "scalp": "SELL SCALP" if rsi > 65 else "BUY SCALP" if rsi < 35 else "RANGE"
            }
        return {"asset": asset, "price": "BUSY", "adx": "-", "rsi": "-", "atr": "-", "prob": "-", "rec": "RETRY",
                "scalp": "-"}
    except:
        return {"asset": asset, "price": "TIMEOUT", "adx": "-", "rsi": "-", "atr": "-", "prob": "-", "rec": "RETRY",
                "scalp": "-"}


@app.route('/')
def home(): return render_template('index.html')


@app.route('/api/data')
def data():
    try:
        r = session.get(FNG_API, timeout=5)
        sent = r.json()['data'][0]
        sentiment = {"val": int(sent['value']), "class": sent['value_classification']}
    except:
        sentiment = {"val": 50, "class": "Neutral"}

    params = [(k, v, sentiment, i) for i, (k, v) in enumerate(ASSETS.items())]
    with ThreadPoolExecutor(max_workers=len(ASSETS)) as executor:
        results = list(executor.map(fetch_precision_intel, params))
    return jsonify({"sentiment": sentiment, "assets": results})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)