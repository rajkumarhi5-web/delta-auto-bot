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
    'options': {'defaultType': 'future'}
})

# SETTINGS FOR ₹1,000 Capital
SYMBOL = "XRP/USDT"  # ₹1k ke liye XRP best hai (low margin requirement)
TIMEFRAME = '15m'    # 15 min zyada stable signals deta hai
LEVERAGE = 3         # Safe leverage (₹1,000 ke liye 3x sahi hai)
open_positions = {}

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TG_CHAT_ID, "text": msg})
    except:
        pass

# =========================
# 📊 INDICATORS
# =========================
def get_data(symbol):
    ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=100)
    df = pd.DataFrame(ohlcv, columns=['t','o','h','l','c','v'])
    
    # RSI Calculation
    delta = df['c'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # EMA 50 - Trend Filter
    df['ema_50'] = df['c'].ewm(span=50, adjust=False).mean()
    return df

# =========================
# 🧠 SMART SIGNAL
# =========================
def signal(df):
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # BUY: Trend UP (Price > EMA) and RSI Recovery from 40
    if last['c'] > last['ema_50'] and prev['rsi'] < 40 and last['rsi'] > 40:
        return "buy"
    
    # SELL: Trend DOWN (Price < EMA) and RSI Falling from 60
    if last['c'] < last['ema_50'] and prev['rsi'] > 60 and last['rsi'] < 60:
        return "sell"
    
    return None

# =========================
# 🚀 TRADE EXECUTION
# =========================
def execute_trade(side):
    try:
        if SYMBOL in open_positions:
            return "Already in trade"

        exchange.set_leverage(LEVERAGE, SYMBOL)
        
        # Calculate Position Size for ₹1,000 (~$12)
        bal = exchange.fetch_balance()
        available_usdt = bal['USDT']['free']
        price = exchange.fetch_ticker(SYMBOL)['last']
        
        # Use 90% of available balance
        qty = round(((available_usdt * 0.9) * LEVERAGE) / price, 1)

        order = exchange.create_market_order(SYMBOL, side, qty)
        entry = order['average'] if order['average'] else price

        # SL 1.5% | TP 3%
        sl = entry * 0.985 if side == "buy" else entry * 1.015
        tp = entry * 1.03 if side == "buy" else entry * 0.97

        open_positions[SYMBOL] = {"side": side, "qty": qty, "sl": sl, "tp": tp}
        
        send_telegram(f"✅ TRADE PLACED!\nSide: {side.upper()}\nEntry: {entry}\nSL: {sl}\nTP: {tp}")
        return f"Entered {side}"

    except Exception as e:
        return str(e)

# =========================
# 🔄 MANAGE POSITION
# =========================
def manage_trades():
    if SYMBOL not in open_positions:
        return
    
    try:
        pos = open_positions[SYMBOL]
        curr_price = exchange.fetch_ticker(SYMBOL)['last']
        
        close_trade = False
        if pos['side'] == "buy":
            if curr_price >= pos['tp'] or curr_price <= pos['sl']:
                close_trade = True
                order_side = "sell"
        else:
            if curr_price <= pos['tp'] or curr_price >= pos['sl']:
                close_trade = True
                order_side = "buy"

        if close_trade:
            exchange.create_market_order(SYMBOL, order_side, pos['qty'])
            send_telegram(f"❌ TRADE CLOSED\nPrice: {curr_price}")
            del open_positions[SYMBOL]
            
    except Exception as e:
        print(f"Manage Error: {e}")

# =========================
# 🌐 ROUTES
# =========================
@app.route('/')
def home():
    return "*****BOT IS ONLINE 🚀*****"

@app.route('/run-bot')
def run():
    df = get_data(SYMBOL)
    sig = signal(df)
    
    result = "Scanning..."
    if sig:
        result = execute_trade(sig)
    
    manage_trades()
    return jsonify({"status": result, "price": df.iloc[-1]['c']})

if __name__ == "__main__":
    # Notification when script starts
    send_telegram("🚀 BOT STARTED SUCCESSFULLY! (₹1,000 Strategy)")
    
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
