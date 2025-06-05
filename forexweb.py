from flask import Flask
import pandas as pd
import numpy as np
import ccxt
import requests
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

app = Flask(__name__)

BOT_TOKEN = '8139825360:AAHFPDGy4Yk3t-f88CCpqDrw_WlmD1F1K6g'
CHAT_ID = '1735704344'

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message}
        requests.post(url, data=payload, timeout=10)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

def analyze_forex_pairs(exchange, forex_pairs, timeframe="1h", limit=300):
    signals = {}

    for symbol in forex_pairs:
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)

            # Indicators
            ema_50 = EMAIndicator(close=df['close'], window=50).ema_indicator()
            ema_200 = EMAIndicator(close=df['close'], window=200).ema_indicator()
            rsi = RSIIndicator(close=df['close'], window=14).rsi()
            macd = MACD(close=df['close'])
            atr = AverageTrueRange(high=df['high'], low=df['low'], close=df['close'], window=14)

            df['ema_50'] = ema_50
            df['ema_200'] = ema_200
            df['rsi'] = rsi
            df['macd'] = macd.macd()
            df['macd_signal'] = macd.macd_signal()
            df['atr'] = atr.average_true_range()

            latest = df.iloc[-1]
            current_price = latest['close']
            atr_value = latest['atr']

            buy_signal = (
                latest['ema_50'] > latest['ema_200'] and
                latest['rsi'] > 50 and
                latest['macd'] > latest['macd_signal']
            )
            sell_signal = (
                latest['ema_50'] < latest['ema_200'] and
                latest['rsi'] < 50 and
                latest['macd'] < latest['macd_signal']
            )

            if buy_signal:
                side = "BUY"
                tp = current_price + 2 * atr_value
                sl = current_price - atr_value
            elif sell_signal:
                side = "SELL"
                tp = current_price - 2 * atr_value
                sl = current_price + atr_value
            else:
                side = "NO SIGNAL"
                tp = None
                sl = None

            signals[symbol] = {
                "side": side,
                "price": round(current_price, 5),
                "take_profit": round(tp, 5) if tp else None,
                "stop_loss": round(sl, 5) if sl else None
            }

        except Exception as e:
            signals[symbol] = {"error": str(e)}

    return signals

@app.route('/')
def run_signal_check():
    exchange = ccxt.binance({'enableRateLimit': True})
    forex_pairs = ['EUR/USDT', 'GBP/USDT', 'AUD/USDT', 'TRX/USDT', 'DOGE/USDT']

    results = analyze_forex_pairs(exchange, forex_pairs)
    html_output = "<h2>📊 Trade Signals</h2>"

    for pair, info in results.items():
        html_output += f"<h4>{pair}</h4>"
        if "error" in info:
            html_output += f"<p style='color:red;'>❌ Error: {info['error']}</p>"
        else:
            html_output += f"""
                <p>✅ Signal: {info['side']}<br>
                Price: {info['price']}<br>
                Take Profit: {info['take_profit']}<br>
                Stop Loss: {info['stop_loss']}</p>
            """
            if info["side"] in ["BUY", "SELL"]:
                msg = (
                    f"📊 *{pair}*\n"
                    f"Signal: {info['side']}\n"
                    f"Price: {info['price']}\n"
                    f"TP: {info['take_profit']}\n"
                    f"SL: {info['stop_loss']}"
                )
                send_telegram_message(msg)

    return html_output

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)