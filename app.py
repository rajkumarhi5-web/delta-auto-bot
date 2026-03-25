from flask import Flask, request, jsonify
import ccxt
import pandas as pd
import time

app = Flask(__name__)

# API (abhi dummy hai - baad me secure add karenge)
import os

exchange = ccxt.delta({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

# Coins
SYMBOLS = ['XRPUSDT', 'ADAUSDT']

# Settings
TIMEFRAME = '5m'
TRADE_SIZE = 1   # small capital friendly
last_signal = {}

def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    return df

def strategy(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()

    if df['ema9'].iloc[-1] > df['ema21'].iloc[-1]:
        return "buy"
    elif df['ema9'].iloc[-1] < df['ema21'].iloc[-1]:
        return "sell"
    else:
        return None

def execute_trade(symbol, signal):
    global last_signal

    if last_signal.get(symbol) == signal:
        return "No duplicate trade"

    try:
        if signal == "buy":
            order = exchange.create_market_buy_order(symbol, TRADE_SIZE)
        elif signal == "sell":
            order = exchange.create_market_sell_order(symbol, TRADE_SIZE)

        last_signal[symbol] = signal
        return order

    except Exception as e:
        return str(e)

@app.route('/')
def home():
    return "Bot is running"

@app.route('/run-bot')
def run_bot():
    results = {}

    for symbol in SYMBOLS:
        df = get_data(symbol)
        signal = strategy(df)

        if signal:
            result = execute_trade(symbol, signal)
            results[symbol] = result
        else:
            results[symbol] = "No signal"

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
