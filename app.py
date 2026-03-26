from flask import Flask, jsonify
import ccxt
import pandas as pd
import os
import time
import threading

app = Flask(__name__)

# ===== Exchange =====
exchange = ccxt.delta({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

# ===== SETTINGS =====
SYMBOLS = ["XRP/USDT", "SOL/USDT"]
TIMEFRAME = '5m'
TRADE_SIZE = 2
SL_PERCENT = 0.01
TP_PERCENT = 0.02

last_signal = {}

# ===== DATA =====
def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        return df
    except Exception as e:
        return None

# ===== RSI =====
def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = -delta.clip(upper=0).rolling(period).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    return df

# ===== STRATEGY =====
def strategy(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    df = calculate_rsi(df)

    last = df.iloc[-1]
    avg_vol = df['volume'].rolling(10).mean().iloc[-1]

    if last['volume'] < avg_vol:
        return None

    if last['ema9'] > last['ema21'] and last['rsi'] > 55:
        return "buy"

    elif last['ema9'] < last['ema21'] and last['rsi'] < 45:
        return "sell"

    return None

# ===== TRADE =====
def execute_trade(symbol, signal):
    global last_signal

    if last_signal.get(symbol) == signal:
        return

    try:
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']

        if signal == "buy":
            exchange.create_market_buy_order(symbol, TRADE_SIZE)
            sl = price * (1 - SL_PERCENT)
            tp = price * (1 + TP_PERCENT)
            side = "sell"

        else:
            exchange.create_market_sell_order(symbol, TRADE_SIZE)
            sl = price * (1 + SL_PERCENT)
            tp = price * (1 - TP_PERCENT)
            side = "buy"

        # SL
        exchange.create_order(
            symbol,
            'stop_market',
            side,
            TRADE_SIZE,
            None,
            {'stopPrice': round(sl, 4)}
        )

        # TP
        exchange.create_limit_order(
            symbol,
            side,
            TRADE_SIZE,
            round(tp, 4)
        )

        last_signal[symbol] = signal
        print(f"{symbol} {signal.upper()} | SL {sl} TP {tp}")

    except Exception as e:
        print(f"Trade error: {e}")

# ===== AUTO LOOP =====
def auto_trading():
    while True:
        print("Running bot cycle...")

        for symbol in SYMBOLS:
            df = get_data(symbol)
            if df is None:
                continue

            signal = strategy(df)

            if signal:
                execute_trade(symbol, signal)

        time.sleep(300)  # 5 min

# ===== START THREAD =====
threading.Thread(target=auto_trading).start()

# ===== HEALTH CHECK =====
@app.route('/')
def home():
    return "AUTO BOT RUNNING 24/7 🚀"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)