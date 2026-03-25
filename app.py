from flask import Flask, jsonify
import ccxt
import pandas as pd
import os

app = Flask(__name__)

# Exchange setup (secure API)
exchange = ccxt.delta({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

# Coins (Delta compatible format)
SYMBOLS = ['XRP/USDT', 'ADA/USDT']

# Settings
TIMEFRAME = '5m'
TRADE_SIZE = 1
last_signal = {}

# Get market data
def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        return df
    except Exception as e:
        return str(e)

# Strategy (EMA crossover)
def strategy(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()

    if df['ema9'].iloc[-1] > df['ema21'].iloc[-1]:
        return "buy"
    elif df['ema9'].iloc[-1] < df['ema21'].iloc[-1]:
        return "sell"
    else:
        return None

# Execute trade (SAFE mode)
def execute_trade(symbol, signal):
    global last_signal

    if last_signal.get(symbol) == signal:
        return "No duplicate trade"

    try:
        # ⚠️ अभी order disable रखा है (testing safe mode)
        last_signal[symbol] = signal
        return f"{signal.upper()} signal detected (no trade executed)"

    except Exception as e:
        return str(e)

# Home route
@app.route('/')
def home():
    return "Bot is running"

# Run bot
@app.route('/run-bot')
def run_bot():
    results = {}

    try:
        for symbol in SYMBOLS:
            df = get_data(symbol)

            # Error handling
            if isinstance(df, str):
                results[symbol] = f"Data error: {df}"
                continue

            signal = strategy(df)

            if signal:
                result = execute_trade(symbol, signal)
                results[symbol] = result
            else:
                results[symbol] = "No signal"

        return jsonify(results)

    except Exception as e:
        return jsonify({"error": str(e)})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
