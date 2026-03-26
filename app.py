from flask import Flask, jsonify
import ccxt
import pandas as pd
import os
import requests

app = Flask(__name__)

# =========================
# 🔐 EXCHANGE SETUP
# =========================
exchange = ccxt.delta({
    'apiKey': os.getenv("API_KEY"),
    'secret': os.getenv("API_SECRET"),
    'enableRateLimit': True,
    'options': {'defaultType': 'future'}
})

# =========================
# 📲 TELEGRAM SETUP
# =========================
BOT_TOKEN = os.getenv("TG_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except:
        pass

# =========================
# ⚙️ SETTINGS
# =========================
SYMBOLS = [
    "XRP/USDT",
    "SOL/USDT",
    "DOGE/USDT:USDT"
]

TIMEFRAME = '5m'
RISK_PER_TRADE = 0.2
LEVERAGE = 5

open_positions = {}

# =========================
# 📊 INDICATORS
# =========================
def compute_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=50)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    df['rsi'] = compute_rsi(df['close'])
    return df

# =========================
# 🧠 SIGNAL LOGIC
# =========================
def get_signal(df):
    last = df.iloc[-1]
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
    price = exchange.fetch_ticker(symbol)['last']

    qty = amount / price
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
        entry_price = order['average'] or order['price']

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
            "tp": tp,
            "qty": qty
        }

        send_telegram(f"""
🚀 TRADE OPENED

Symbol: {symbol}
Side: {side}
Entry: {entry_price}

SL: {sl}
TP: {tp}
Qty: {qty}
Leverage: {LEVERAGE}x
""")

        return f"{side} executed"

    except Exception as e:
        return f"Error: {str(e)}"

# =========================
# 🔄 MANAGE TRADES
# =========================
def manage_trades():
    results = {}

    for symbol, pos in list(open_positions.items()):
        try:
            price = exchange.fetch_ticker(symbol)['last']

            if pos['side'] == "BUY":
                if price <= pos['sl'] or price >= pos['tp']:
                    exchange.create_market_order(symbol, "sell", pos['qty'])

                    send_telegram(f"""
✅ TRADE CLOSED

Symbol: {symbol}
Exit Price: {price}
Result: SL/TP Hit
""")

                    del open_positions[symbol]

            elif pos['side'] == "SELL":
                if price >= pos['sl'] or price <= pos['tp']:
                    exchange.create_market_order(symbol, "buy", pos['qty'])

                    send_telegram(f"""
✅ TRADE CLOSED

Symbol: {symbol}
Exit Price: {price}
Result: SL/TP Hit
""")

                    del open_positions[symbol]

        except Exception as e:
            results[symbol] = str(e)

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

    manage_trades()
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

# =========================
# ▶️ START SERVER
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)