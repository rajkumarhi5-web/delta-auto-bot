from flask import Flask
import ccxt
import pandas as pd
import os
import requests
import time
import threading

app = Flask(__name__)

API_KEY = os.getenv("API_KEY")
API_SECRET = os.getenv("API_SECRET")
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

exchange = ccxt.delta({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
})

SYMBOL = "XRP/USDT"
TIMEFRAME = '5m'
LEVERAGE = 3

open_positions = {}
last_trade_time = 0

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg})
    except:
        pass

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

def get_signal(df):
    last = df.iloc[-1]

    if last['c'] > last['ema20'] > last['ema50'] and last['rsi'] > 52:
        return "buy"

    if last['c'] < last['ema20'] < last['ema50'] and last['rsi'] < 48:
        return "sell"

    return None

def execute_trade(side):
    global last_trade_time

    try:
        if SYMBOL in open_positions:
            return

        if time.time() - last_trade_time < 120:
            return

        exchange.set_leverage(LEVERAGE, SYMBOL)

        balance = exchange.fetch_balance()
        usdt = balance['USDT']['free']

        if usdt < 2:
            return

        price = exchange.fetch_ticker(SYMBOL)['last']
        risk = usdt * 0.4
        qty = round((risk * LEVERAGE) / price, 1)

        if qty <= 0:
            return

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

        last_trade_time = time.time()

        send_telegram(f"TRADE OPENED {side} {SYMBOL}")

    except Exception as e:
        send_telegram(f"Error: {str(e)}")

def manage_trade():
    if SYMBOL not in open_positions:
        return

    try:
        pos = open_positions[SYMBOL]
        price = exchange.fetch_ticker(SYMBOL)['last']

        if pos['side'] == "buy":
            if price >= pos['tp'] or price <= pos['sl']:
                exchange.create_market_order(SYMBOL, "sell", pos['qty'])
                del open_positions[SYMBOL]

        else:
            if price <= pos['tp'] or price >= pos['sl']:
                exchange.create_market_order(SYMBOL, "buy", pos['qty'])
                del open_positions[SYMBOL]

    except:
        pass

def bot_loop():
    send_telegram("BOT STARTED")

    while True:
        try:
            df = get_data()
            signal = get_signal(df)

            if signal:
                execute_trade(signal)

            manage_trade()

        except:
            pass

        time.sleep(60)

@app.route('/')
def home():
    return "BOT RUNNING"

if __name__ == "__main__":
    threading.Thread(target=bot_loop).start()
    app.run(host="0.0.0.0", port=10000)