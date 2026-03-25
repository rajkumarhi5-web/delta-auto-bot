from flask import Flask, jsonify
import ccxt
import pandas as pd
import os
import time

app = Flask(__name__)

# ===== Exchange Setup =====
exchange = ccxt.delta({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

# ===== SETTINGS =====
SYMBOLS = ["XRP/USDT", "SOL/USDT"]
TIMEFRAME = '5m'
TRADE_SIZE = 2   # small capital safe
last_signal = {}

# ===== DATA FETCH =====
def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        return df
    except Exception as e:
        return str(e)

# ===== RSI CALC =====
def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

# ===== STRATEGY =====
def strategy(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    df = calculate_rsi(df)

    last = df.iloc[-1]

    # Volume filter
    avg_vol = df['volume'].rolling(10).mean().iloc[-1]

    if last['volume'] < avg_vol:
        return None

    # BUY
    if last['ema9'] > last['ema21'] and last['rsi'] > 55:
        return "buy"

    # SELL
    elif last['ema9'] < last['ema21'] and last['rsi'] < 45:
        return "sell"

    return None

# ===== EXECUTE TRADE =====
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
        return f"{signal.upper()} executed"

    except Exception as e:
        return f"Trade error: {str(e)}"

# ===== ROUTES =====

@app.route('/')
def home():
    return "PRO BOT RUNNING 🚀"

@app.route('/run-bot')
def run_bot():
    results = {}

    for symbol in SYMBOLS:
        df = get_data(symbol)

        if isinstance(df, str):
            results[symbol] = df
            continue

        signal = strategy(df)

        if signal:
            result = execute_trade(symbol, signal)
            results[symbol] = result
        else:
            results[symbol] = "No trade (filtered)"

    return jsonify(results)

# ===== AUTO LOOP (IMPORTANT) =====
@app.route('/auto')
def auto_trade():
    results = {}

    for symbol in SYMBOLS:
        df = get_data(symbol)

        if isinstance(df, str):
            results[symbol] = df
            continue

        signal = strategy(df)

        if signal:
            result = execute_trade(symbol, signal)
            results[symbol] = result
        else:
            results[symbol] = "No trade"

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)