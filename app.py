from flask import Flask, jsonify
import ccxt
import pandas as pd
import os
import requests
import traceback

app = Flask(__name__)

# =========================
# 🔐 ENV
# =========================
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# =========================
# 🔐 EXCHANGE
# =========================
exchange = ccxt.delta({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
})

SYMBOL = "XRP/USDT"
TIMEFRAME = '5m'
LEVERAGE = 3

open_positions = {}

# =========================
# 📩 TELEGRAM
# =========================
def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": TG_CHAT_ID,
            "text": msg
        }, timeout=5)
    except Exception as e:
        print("Telegram Error:", e)

# =========================
# 📊 DATA
# =========================
def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100)
    df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])

    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    df['ema20'] = df['c'].ewm(span=20).mean()
    df['ema50'] = df['c'].ewm(span=50).mean()

    return df

# =========================
# 🧠 SIGNAL
# =========================
def get_signal(df):
    last = df.iloc[-1]

    if last['c'] > last['ema20'] > last['ema50'] and last['rsi'] > 52:
        return "buy"

    if last['c'] < last['ema20'] < last['ema50'] and last['rsi'] < 48:
        return "sell"

    return None

# =========================
# 🚀 EXECUTE TRADE
# =========================
def execute_trade(side):
    try:
        if SYMBOL in open_positions:
            return "Already in trade"

        exchange.set_leverage(LEVERAGE, SYMBOL)

        balance = exchange.fetch_balance()
        usdt = balance['USDT']['free']

        if usdt < 2:
            return "Low balance"

        price = exchange.fetch_ticker(SYMBOL)['last']

        risk = usdt * 0.40  # safer
        qty = (risk * LEVERAGE) / price

        qty = round(qty, 3)  # safer precision

        if qty <= 0:
            return "Qty too low"

        order = exchange.create_market_order(SYMBOL, side, qty)
        entry = order.get('average') or price

        if side == "buy":
            sl = entry * 0.993
            tp = entry * 1.015
        else:
            sl = entry * 1.007
            tp = entry * 0.985

        open_positions[SYMBOL] = {
            "side": side,
            "qty": qty,
            "sl": sl,
            "tp": tp
        }

        send_telegram(
            f"✅ OPEN\n{side.upper()} {SYMBOL}\nEntry: {entry:.4f}\nSL: {sl:.4f}\nTP: {tp:.4f}"
        )

        return f"Entered {side}"

    except Exception as e:
        error = str(e)
        print("TRADE ERROR:", error)
        send_telegram(f"❌ Trade Error:\n{error}")
        return error

# =========================
# 🔄 MANAGE TRADE
# =========================
def manage_trade():
    if SYMBOL not in open_positions:
        return

    try:
        pos = open_positions[SYMBOL]
        price = exchange.fetch_ticker(SYMBOL)['last']

        close = False

        if pos['side'] == "buy":
            if price >= pos['tp'] or price <= pos['sl']:
                side = "sell"
                close = True
        else:
            if price <= pos['tp'] or price >= pos['sl']:
                side = "buy"
                close = True

        if close:
            exchange.create_market_order(SYMBOL, side, pos['qty'])
            send_telegram(f"❌ CLOSED @ {price:.4f}")
            del open_positions[SYMBOL]

    except Exception as e:
        print("Manage Error:", traceback.format_exc())

# =========================
# 🌐 ROUTES
# =========================
@app.route('/')
def home():
    return "SCALPING BOT LIVE 🚀"

@app.route('/run-bot')
def run_bot():
    try:
        df = get_data()
        signal = get_signal(df)

        result = "No Signal"

        if signal:
            result = execute_trade(signal)

        manage_trade()

        return jsonify({
            "price": float(df.iloc[-1]['c']),
            "status": result
        })

    except Exception as e:
        return str(e)

# =========================
# ▶ START
# =========================
if __name__ == "__main__":
    send_telegram("🚀 BOT STARTED")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)