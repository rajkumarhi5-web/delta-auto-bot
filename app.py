from flask import Flask, jsonify
import ccxt
import pandas as pd
import time
import os

app = Flask(__name__)

# =========================
# 🔐 EXCHANGE SETUP
# =========================
exchange = ccxt.delta({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'
    }
})

# =========================
# ⚙️ SETTINGS
# =========================
SYMBOLS = [
    "XRP/USDT",
    "SOL/USDT",
    "DOGE/USDT",
    "TRX/USDT"
]

TIMEFRAME = '5m'
RISK_PER_TRADE = 0.2   # 20% capital use
LEVERAGE = 5

# Track open trades
open_positions = {}

# =========================
# 📊 INDICATORS
# =========================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    df['rsi'] = compute_rsi(df['close'])
    return df

def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# =========================
# 🧠 SIGNAL LOGIC
# =========================
def get_signal(df):
    last = df.iloc[-1]

    # Volume spike
    vol_avg = df['volume'].rolling(20).mean().iloc[-1]

    if last['volume'] > vol_avg * 1.5:
        if last['rsi'] < 35:
            return "BUY"
        elif last['rsi'] > 65:
            return "SELL"

    return None

# =========================
# 💰 POSITION SIZE
# =========================
def get_position_size(symbol):
    balance = exchange.fetch_balance()
    usdt = balance['USDT']['free']

    amount = usdt * RISK_PER_TRADE
    ticker = exchange.fetch_ticker(symbol)

    qty = amount / ticker['last']
    return round(qty, 2)

# =========================
# ⚡ EXECUTE TRADE
# =========================
def execute_trade(symbol, side):
    try:
        if symbol in open_positions:
            return "Already in trade"

        exchange.set_leverage(LEVERAGE, symbol)

        qty = get_position_size(symbol)

        order = exchange.create_market_order(symbol, side.lower(), qty)

        entry_price = order['average']

        # SL / TP
        if side == "BUY":
            sl = entry_price * 0.98
            tp = entry_price * 1.04
        else:
            sl = entry_price * 1.02
            tp = entry_price * 0.96

        open_positions[symbol] = {
            "side": side,
            "entry": entry_price,
            "sl": sl,
            "tp": tp
        }

        return f"{side} executed at {entry_price}"

    except Exception as e:
        return f"Error: {str(e)}"

# =========================
# 🔄 MONITOR TRADES
# =========================
def manage_trades():
    results = {}

    for symbol, pos in list(open_positions.items()):
        try:
            ticker = exchange.fetch_ticker(symbol)
            price = ticker['last']

            if pos['side'] == "BUY":
                if price <= pos['sl'] or price >= pos['tp']:
                    exchange.create_market_order(symbol, "sell", get_position_size(symbol))
                    results[symbol] = "Closed (SL/TP)"
                    del open_positions[symbol]

            elif pos['side'] == "SELL":
                if price >= pos['sl'] or price <= pos['tp']:
                    exchange.create_market_order(symbol, "buy", get_position_size(symbol))
                    results[symbol] = "Closed (SL/TP)"
                    del open_positions[symbol]

        except Exception as e:
            results[symbol] = f"Error: {str(e)}"

    return results

# =========================
# 🚀 BOT RUNNER
# =========================
def run_bot():
    results = {}

    for symbol in SYMBOLS:
        try:
            df = get_data(symbol)
            signal = get_signal(df)

            if signal:
                results[symbol] = execute_trade(symbol, signal)
            else:
                results[symbol] = "No trade"

        except Exception as e:
            results[symbol] = f"Data error: {str(e)}"

    # Manage existing trades
    manage = manage_trades()
    results.update(manage)

    return results

# =========================
# 🌐 ROUTES
# =========================
@app.route('/')
def home():
    return "AUTO BOT RUNNING 24/7 🚀"

@app.route('/run-bot')
def run():
    return jsonify(run_bot())

@app.route('/status')
def status():
    return jsonify(open_positions)