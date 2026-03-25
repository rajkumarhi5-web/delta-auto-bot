from flask import Flask, jsonify
import ccxt
import pandas as pd
import os
import time
from threading import Thread

app = Flask(__name__)

exchange = ccxt.delta({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
    'enableRateLimit': True,
})

# 🔥 LOAD MARKETS
markets = exchange.load_markets()

# 🔍 AUTO FIND VALID SYMBOLS
TARGET_COINS = ['XRP', 'ADA', 'DOGE']

SYMBOLS = []
for m in markets:
    for coin in TARGET_COINS:
        if coin in m and "USDT" in m:
            SYMBOLS.append(m)

SYMBOLS = list(set(SYMBOLS))[:3]  # limit 3

print("Using symbols:", SYMBOLS)

TIMEFRAME = '5m'
TRADE_SIZE = 1
last_signal = {}

# ---------------- DATA ----------------
def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
        df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])
        return df
    except Exception as e:
        return None

# ---------------- STRATEGY ----------------
def strategy(df):
    df['ema9'] = df['c'].ewm(span=9).mean()
    df['ema21'] = df['c'].ewm(span=21).mean()

    if df['ema9'].iloc[-1] > df['ema21'].iloc[-1]:
        return "buy"
    elif df['ema9'].iloc[-1] < df['ema21'].iloc[-1]:
        return "sell"
    return None

# ---------------- BOT LOOP ----------------
def bot_loop():
    while True:
        for symbol in SYMBOLS:
            df = get_data(symbol)
            if df is None:
                continue

            signal = strategy(df)

            if signal:
                print(f"{symbol} -> {signal}")

        time.sleep(300)

# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return "🔥 PERFECT AUTO BOT RUNNING"

@app.route('/symbols')
def symbols():
    return jsonify(SYMBOLS)

# ---------------- START ----------------
def start_bot():
    t = Thread(target=bot_loop)
    t.daemon = True
    t.start()

start_bot()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)