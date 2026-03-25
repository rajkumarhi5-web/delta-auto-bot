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

# ✅ FINAL WORKING SYMBOLS
SYMBOLS = [
    'XRP/USD:USDT',
    'DOGE/USD:USDT'
]

TIMEFRAME = '5m'
HIGHER_TF = '15m'

last_signal = {}
last_trade_time = {}

COOLDOWN = 300

# ---------------- DATA ----------------
def get_df(symbol, tf):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=50)
        df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])
        return df
    except Exception as e:
        return None

# ---------------- STRATEGY ----------------
def signal(df):
    df['ema9'] = df['c'].ewm(span=9).mean()
    df['ema21'] = df['c'].ewm(span=21).mean()

    if df['ema9'].iloc[-1] > df['ema21'].iloc[-1]:
        return "buy"
    elif df['ema9'].iloc[-1] < df['ema21'].iloc[-1]:
        return "sell"
    return None

def volume_ok(df):
    return df['v'].iloc[-1] > df['v'].mean() * 1.5

# ---------------- TRADE ----------------
def execute(symbol, sig, price):
    global last_signal, last_trade_time

    now = time.time()

    if symbol in last_trade_time and now - last_trade_time[symbol] < COOLDOWN:
        return "Cooldown"

    if last_signal.get(symbol) == sig:
        return "Duplicate"

    if sig == "buy":
        sl = price * 0.99
        tp = price * 1.02
    else:
        sl = price * 1.01
        tp = price * 0.98

    last_signal[symbol] = sig
    last_trade_time[symbol] = now

    return {
        "signal": sig,
        "entry": round(price, 4),
        "sl": round(sl, 4),
        "tp": round(tp, 4)
    }

# ---------------- LOOP ----------------
def bot():
    while True:
        for s in SYMBOLS:
            df = get_df(s, TIMEFRAME)
            df_htf = get_df(s, HIGHER_TF)

            if df is None or df_htf is None:
                continue

            sig = signal(df)
            htf = signal(df_htf)

            if not sig or sig != htf:
                continue

            if not volume_ok(df):
                continue

            price = df['c'].iloc[-1]

            res = execute(s, sig, price)
            print("TRADE:", s, res)

        time.sleep(300)

# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return "🔥 AUTO BOT PERFECT RUNNING"

# ---------------- START ----------------
def start():
    t = Thread(target=bot)
    t.daemon = True
    t.start()

start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)