from flask import Flask, jsonify
import ccxt
import pandas as pd
import time
import os
import requests

app = Flask(__name__)

# =========================
# 🔐 ENV VARIABLES
# =========================
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# =========================
# 🔐 EXCHANGE SETUP
# =========================
exchange = ccxt.delta({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

# =========================
# ⚙️ SETTINGS
# =========================
SYMBOLS = [
    "XRP/USDT",
    "SOL/USDT"
]

TIMEFRAME = '5m'
RISK = 0.2
LEVERAGE = 5

open_positions = {}

# =========================
# 📲 TELEGRAM
# =========================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": TG_CHAT_ID,
            "text": msg
        })
    except:
        pass

# =========================
# 📊 RSI
# =========================
def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta).clip(lower=0).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# =========================
# 📊 DATA
# =========================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
    df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])
    df['rsi'] = rsi(df['c'])
    return df

# =========================
# 🧠 SIGNAL
# =========================
def signal(df):
    last = df.iloc[-1]
    vol_avg = df['v'].rolling(20).mean().iloc[-1]

    if last['v'] > vol_avg * 1.5:
        if last['rsi'] < 35:
            return "buy"
        elif last['rsi'] > 65:
            return "sell"
    return None

# =========================
# 💰 SIZE
# =========================
def position_size(symbol):
    bal = exchange.fetch_balance()
    usdt = bal['USDT']['free']
    price = exchange.fetch_ticker(symbol)['last']
    return round((usdt * RISK) / price, 2)

# =========================
# 🚀 TRADE
# =========================
def trade(symbol, side):
    try:
        if symbol in open_positions:
            return "Already in trade"

        exchange.set_leverage(LEVERAGE, symbol)

        qty = position_size(symbol)
        order = exchange.create_market_order(symbol, side, qty)
        entry = order['average']

        if side == "buy":
            sl = entry * 0.98
            tp = entry * 1.04
        else:
            sl = entry * 1.02
            tp = entry * 0.96

        open_positions[symbol] = {
            "side": side,
            "sl": sl,
            "tp": tp
        }

        send_telegram(f"🚀 {side.upper()} {symbol}\nEntry: {entry}\nSL: {sl}\nTP: {tp}")

        return "Trade executed"

    except Exception as e:
        return str(e)

# =========================
# 🔄 MANAGE
# =========================
def manage():
    results = {}
    for symbol, pos in list(open_positions.items()):
        price = exchange.fetch_ticker(symbol)['last']

        if pos['side'] == "buy":
            if price <= pos['sl'] or price >= pos['tp']:
                exchange.create_market_order(symbol, "sell", position_size(symbol))
                send_telegram(f"❌ Closed {symbol}")
                del open_positions[symbol]
                results[symbol] = "Closed"

        if pos['side'] == "sell":
            if price >= pos['sl'] or price <= pos['tp']:
                exchange.create_market_order(symbol, "buy", position_size(symbol))
                send_telegram(f"❌ Closed {symbol}")
                del open_positions[symbol]
                results[symbol] = "Closed"

    return results

# =========================
# 🤖 BOT
# =========================
def run_bot():
    results = {}

    for s in SYMBOLS:
        try:
            df = get_data(s)
            sig = signal(df)

            if sig:
                results[s] = trade(s, sig)
            else:
                results[s] = "No trade"

        except Exception as e:
            results[s] = f"Error: {str(e)}"

    results.update(manage())
    return results

# =========================
# 🌐 ROUTES
# =========================
@app.route('/')
def home():
    return "BOT RUNNING 🚀"

@app.route('/run-bot')
def run():
    return jsonify(run_bot())

@app.route('/status')
def status():
    return jsonify(open_positions)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)