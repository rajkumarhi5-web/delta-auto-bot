from flask import Flask, jsonify
import ccxt
import pandas as pd
import os

app = Flask(__name__)

# ===== EXCHANGE SETUP =====
exchange = ccxt.delta({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
    'enableRateLimit': True
})

# ===== SAFE WORKING SYMBOLS (CONFIRMED) =====
SYMBOLS = [
    "XRP/USDT",
    "DOGE/USDT"
]

TIMEFRAME = '5m'
TRADE_SIZE = 1

last_signal = {}
trade_log = {}

# ===== FETCH DATA =====
def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        return df
    except Exception as e:
        return str(e)

# ===== STRATEGY (SMART ENTRY) =====
def strategy(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()

    # Volume filter (whale activity)
    avg_vol = df['volume'].mean()
    last_vol = df['volume'].iloc[-1]

    if last_vol < avg_vol:
        return None  # avoid low volume trade

    if df['ema9'].iloc[-1] > df['ema21'].iloc[-1]:
        return "buy"
    elif df['ema9'].iloc[-1] < df['ema21'].iloc[-1]:
        return "sell"

    return None

# ===== EXECUTE TRADE =====
def execute_trade(symbol, signal):
    global last_signal

    if last_signal.get(symbol) == signal:
        return "No duplicate trade"

    try:
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']

        # SAFE MODE (no real order yet)
        result = f"{signal.upper()} signal detected"

        # ===== LIVE TRADE ENABLE (later) =====
        # if signal == "buy":
        #     order = exchange.create_market_buy_order(symbol, TRADE_SIZE)
        # elif signal == "sell":
        #     order = exchange.create_market_sell_order(symbol, TRADE_SIZE)
        # result = order

        last_signal[symbol] = signal

        trade_log[symbol] = {
            "signal": signal,
            "price": price
        }

        return result

    except Exception as e:
        return f"Error: {str(e)}"

# ===== HOME =====
@app.route('/')
def home():
    return "🚀 Auto Trading Bot Running"

# ===== RUN BOT =====
@app.route('/run-bot')
def run_bot():
    results = {}

    for symbol in SYMBOLS:
        df = get_data(symbol)

        if isinstance(df, str):
            results[symbol] = f"Data error: {df}"
            continue

        signal = strategy(df)

        if signal:
            result = execute_trade(symbol, signal)
            results[symbol] = result
        else:
            results[symbol] = "No trade (low volume or no signal)"

    return jsonify(results)

# ===== STATUS =====
@app.route('/status')
def status():
    return jsonify(trade_log)

# ===== SYMBOL CHECK =====
@app.route('/symbols')
def symbols():
    return jsonify(SYMBOLS)

# ===== RUN =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)