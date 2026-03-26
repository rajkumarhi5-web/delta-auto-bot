from flask import Flask, jsonify
import ccxt
import pandas as pd
import os
import requests

app = Flask(__name__)

# =========================
# 🔐 ENV VARIABLES
# =========================
API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# =========================
# 🔐 EXCHANGE SETUP
# =========================
exchange = ccxt.delta({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
})

SYMBOL = "XRP/USDT"
TIMEFRAME = '15m'
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
        })
    except Exception as e:
        print("Telegram Error:", e)

# =========================
# 📊 DATA + INDICATORS
# =========================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=100)
    df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])

    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    df['ema_50'] = df['c'].ewm(span=50).mean()
    return df

# =========================
# 🧠 SIGNAL LOGIC
# =========================
def signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]

    if last['c'] > last['ema_50'] and prev['rsi'] < 40 and last['rsi'] > 40:
        return "buy"

    if last['c'] < last['ema_50'] and prev['rsi'] > 60 and last['rsi'] < 60:
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

        price = exchange.fetch_ticker(SYMBOL)['last']

        qty = round(((usdt * 0.9) * LEVERAGE) / price, 1)

        order = exchange.create_market_order(SYMBOL, side, qty)
        entry = order['average'] if order['average'] else price

        sl = entry * 0.985 if side == "buy" else entry * 1.015
        tp = entry * 1.03 if side == "buy" else entry * 0.97

        open_positions[SYMBOL] = {
            "side": side,
            "qty": qty,
            "sl": sl,
            "tp": tp
        }

        send_telegram(
            f"✅ TRADE OPENED\n"
            f"Side: {side.upper()}\n"
            f"Entry: {entry}\nSL: {sl}\nTP: {tp}"
        )

        return f"Entered {side}"

    except Exception as e:
        send_telegram(f"❌ Trade Error: {str(e)}")
        return str(e)

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
                close = True
                side = "sell"
        else:
            if price <= pos['tp'] or price >= pos['sl']:
                close = True
                side = "buy"

        if close:
            exchange.create_market_order(SYMBOL, side, pos['qty'])
            send_telegram(f"❌ TRADE CLOSED @ {price}")
            del open_positions[SYMBOL]

    except Exception as e:
        print("Manage Error:", e)

# =========================
# 🌐 ROUTES
# =========================

@app.route('/')
def home():
    return "BOT IS RUNNING 🚀"

# 🔍 DEBUG CHECK
@app.route('/test')
def test():
    return {
        "API_KEY": API_KEY,
        "API_SECRET": "OK" if API_SECRET else "MISSING",
        "TG_TOKEN": "OK" if TG_TOKEN else "MISSING",
        "TG_CHAT_ID": TG_CHAT_ID
    }

# 💰 BALANCE CHECK
@app.route('/balance')
def balance():
    try:
        return exchange.fetch_balance()
    except Exception as e:
        return str(e)

# 🤖 RUN BOT
@app.route('/run-bot')
def run_bot():
    try:
        df = get_data(SYMBOL)
        sig = signal(df)

        result = "No Signal"

        if sig:
            result = execute_trade(sig)

        manage_trade()

        return jsonify({
            "status": result,
            "price": df.iloc[-1]['c']
        })

    except Exception as e:
        return str(e)

# =========================
# ▶ START
# =========================
if __name__ == "__main__":
    send_telegram("🚀 BOT STARTED SUCCESSFULLY")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
