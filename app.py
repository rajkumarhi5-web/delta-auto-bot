from flask import Flask, jsonify
import ccxt
import pandas as pd
import os

app = Flask(__name__)

# ✅ Exchange setup (Delta Futures)
exchange = ccxt.delta({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

# ✅ Working symbols (tested format)
SYMBOLS = [
    'BTC/USDT',
    'ETH/USDT',
    'XRP/USDT',
    'SOL/USDT'
]

# Settings
TIMEFRAME = '5m'
TRADE_SIZE = 1
last_signal = {}

# 📊 Get data
def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=TIMEFRAME, limit=50)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        return df
    except Exception as e:
        return str(e)

# 📈 Strategy (EMA)
def strategy(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()

    if df['ema9'].iloc[-1] > df['ema21'].iloc[-1]:
        return "buy"
    elif df['ema9'].iloc[-1] < df['ema21'].iloc[-1]:
        return "sell"
    return None

# 🚀 Execute (SAFE MODE)
def execute_trade(symbol, signal):
    global last_signal

    if last_signal.get(symbol) == signal:
        return "No duplicate trade"

    last_signal[symbol] = signal
    return f"{signal.upper()} signal detected (safe mode - no trade)"

# 🏠 Home
@app.route('/')
def home():
    return "Bot is running"

# 🧪 Test route
@app.route('/test')
def test():
    return jsonify({"status": "ok"})

# 🔥 Main bot route (FIXED)
@app.route('/run-bot')
def run_bot():
    results = {}

    try:
        for symbol in SYMBOLS:
            df = get_data(symbol)

            if isinstance(df, str):
                results[symbol] = f"Error: {df}"
                continue

            signal = strategy(df)

            if signal:
                results[symbol] = execute_trade(symbol, signal)
            else:
                results[symbol] = "No signal"

        return jsonify(results)

    except Exception as e:
        return jsonify({"fatal_error": str(e)})

# 🚀 Run
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
