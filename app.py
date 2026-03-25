from flask import Flask, jsonify
import ccxt
import pandas as pd
import os

app = Flask(__name__)

exchange = ccxt.delta({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

# 🔥 Best coins (< $2 + active)
SYMBOLS = ['XRP/USD', 'ADA/USD', 'DOGE/USD', 'WLD/USD', 'WIF/USD']

TIMEFRAME = '5m'
TRADE_SIZE = 1
last_signal = {}

# Data
def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=50)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        return df
    except Exception as e:
        return None

# Strategy
def strategy(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()

    if df['ema9'].iloc[-1] > df['ema21'].iloc[-1]:
        return "buy"
    elif df['ema9'].iloc[-1] < df['ema21'].iloc[-1]:
        return "sell"
    return None

# 🚨 REAL TRADE FUNCTION
def execute_trade(symbol, signal, price):
    global last_signal

    if last_signal.get(symbol) == signal:
        return "No duplicate trade"

    try:
        # Stop Loss & Target
        if signal == "buy":
            sl = price * 0.99
            tp = price * 1.02
            order = exchange.create_market_buy_order(symbol, TRADE_SIZE)

        elif signal == "sell":
            sl = price * 1.01
            tp = price * 0.98
            order = exchange.create_market_sell_order(symbol, TRADE_SIZE)

        last_signal[symbol] = signal

        return {
            "signal": signal,
            "entry": price,
            "stop_loss": sl,
            "target": tp
        }

    except Exception as e:
        return str(e)

# Routes
@app.route('/')
def home():
    return "🔥 PRO BOT RUNNING"

@app.route('/run-bot')
def run_bot():
    results = {}

    for symbol in SYMBOLS:
        df = get_data(symbol)

        if df is None:
            results[symbol] = "Data error"
            continue

        signal = strategy(df)
        price = df['close'].iloc[-1]

        if signal:
            results[symbol] = execute_trade(symbol, signal, price)
        else:
            results[symbol] = "No signal"

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)