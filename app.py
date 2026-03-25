from flask import Flask, jsonify
import ccxt
import pandas as pd
import os

app = Flask(__name__)

# ===== EXCHANGE =====
exchange = ccxt.delta({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
    'enableRateLimit': True
})

# ===== CHANGE AFTER CHECKING /all-symbols =====
# 👉 initially empty (safe)
SYMBOLS = []

TIMEFRAME = '5m'
TRADE_SIZE = 1

last_signal = {}
trade_log = {}

# ===== LOAD MARKETS (IMPORTANT) =====
def load_markets_safe():
    try:
        return exchange.load_markets()
    except Exception as e:
        return str(e)

# ===== ALL SYMBOLS (DEBUG TOOL) =====
@app.route('/all-symbols')
def all_symbols():
    markets = load_markets_safe()
    if isinstance(markets, str):
        return jsonify({"error": markets})

    # Filter: only active + derivatives-like symbols
    symbols = []
    for s, m in markets.items():
        if m.get('active'):
            symbols.append(s)

    # first 100 for mobile view
    return jsonify(symbols[:100])

# ===== FETCH DATA =====
def get_data(symbol):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
        df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
        return df
    except Exception as e:
        return str(e)

# ===== STRATEGY =====
def strategy(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()

    # volume filter
    avg_vol = df['volume'].mean()
    last_vol = df['volume'].iloc[-1]
    if last_vol < avg_vol:
        return None

    if df['ema9'].iloc[-1] > df['ema21'].iloc[-1]:
        return "buy"
    elif df['ema9'].iloc[-1] < df['ema21'].iloc[-1]:
        return "sell"
    return None

# ===== EXECUTE =====
def execute_trade(symbol, signal):
    global last_signal

    if last_signal.get(symbol) == signal:
        return "No duplicate trade"

    try:
        ticker = exchange.fetch_ticker(symbol)
        price = ticker['last']

        # SAFE MODE
        result = f"{signal.upper()} signal"

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
    return "Bot Running (Symbol Finder Mode)"

# ===== RUN BOT =====
@app.route('/run-bot')
def run_bot():
    if not SYMBOLS:
        return jsonify({"error": "No symbols set. Use /all-symbols first."})

    results = {}

    for symbol in SYMBOLS:
        df = get_data(symbol)

        if isinstance(df, str):
            results[symbol] = f"Data error: {df}"
            continue

        signal = strategy(df)

        if signal:
            results[symbol] = execute_trade(symbol, signal)
        else:
            results[symbol] = "No trade"

    return jsonify(results)

# ===== STATUS =====
@app.route('/status')
def status():
    return jsonify(trade_log)

# ===== CURRENT SYMBOLS =====
@app.route('/symbols')
def symbols():
    return jsonify(SYMBOLS)

# ===== RUN =====
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)