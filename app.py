from flask import Flask, jsonify
import ccxt
import pandas as pd
import os
import requests

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
        })
    except Exception as e:
        print("Telegram Error:", e)

# =========================
# 📊 DATA
# =========================
def get_data():
    ohlcv = exchange.fetch_ohlcv(SYMBOL, TIMEFRAME, limit=100)
    df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])

    # RSI
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))

    # EMA
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

        if usdt < 1:
            return "Low balance"

        price = exchange.fetch_ticker(SYMBOL)['last']

        risk = usdt * 0.4
        qty = round((risk * LEVERAGE) / price, 1)

        if qty <= 0:
            return "Qty low"

        order = exchange.create_market_order(SYMBOL, side, qty)
        entry = order['average'] if order['average'] else price

        if side == "buy":
            sl = entry * 0.992
            tp = entry * 1.012
        else:
            sl = entry * 1.008
            tp = entry * 0.988

        open_positions[SYMBOL] = {
            "side": side,
            "qty": qty,
            "sl": sl,
            "tp": tp
        }

        send_telegram(
            f"✅ TRADE OPENED\n{side.upper()} {SYMBOL}\nEntry: {entry}\nSL: {sl}\nTP: {tp}"
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
    return "BOT LIVE 🚀"

@app.route('/run-bot')
def run_bot():
    try:
        df = get_data()
        signal = get_signal(df)

        result = "No Signal"

        if signal:
            result = execute_trade(signal)

        manage_trade()

        # 🔥 ALWAYS TELEGRAM UPDATE
        send_telegram(f"📊 Price: {df.iloc[-1]['c']} | Signal: {result}")

        return jsonify({
            "price": df.iloc[-1]['c'],
            "status": result
        })

    except Exception as e:
        send_telegram(f"❌ BOT ERROR: {str(e)}")
        return str(e)

# =========================
# ▶ START
# =========================
if __name__ == "__main__":
    send_telegram("🚀 BOT STARTED SUCCESSFULLY")

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)