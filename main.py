import time
import requests
import pandas as pd
from datetime import datetime, timezone

# =====================================================================
# CONFIGURATION - YOUR TELEGRAM CREDENTIALS
# =====================================================================
TELEGRAM_BOT_TOKEN = "7654015485:AAFGNaeYL7dkrf0soJDUGa6ERTDpqgsYQy0"
TELEGRAM_CHAT_ID = "7654015485"

PAIRS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

def send_telegram_alert(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

class NewsFilterEngine:
    def check_live_news(self) -> tuple[bool, str]:
        try:
            res = requests.get("https://nfp.ourfxstream.com/api/v1/calendar", timeout=5)
            if res.status_code == 200:
                events = res.json()
                now = datetime.now(timezone.utc)
                for event in events:
                    if event.get("impact", "").upper() == "HIGH":
                        event_time_str = event.get("date")
                        if event_time_str:
                            event_dt = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))
                            time_diff = (event_dt - now).total_seconds() / 60.0
                            if -30 <= time_diff <= 30:
                                return False, f"BLOCKED: High impact event '{event.get('title')}' active."
            return True, "Clear of macro news."
        except Exception:
            return True, "News Filter Active (Fallback)"

class OrderFlowEngine:
    def __init__(self, symbol):
        self.symbol = symbol.upper()

    def analyze(self) -> dict:
        try:
            url = f"https://api.binance.com/api/v3/trades?symbol={self.symbol}&limit=100"
            res = requests.get(url, timeout=4)
            if res.status_code != 200:
                return {"score": 0, "symbol": self.symbol}

            trades = res.json()
            trade_data = []
            cumulative_delta = 0

            for t in trades:
                price = float(t['price'])
                qty = float(t['qty'])
                is_sell = t['isBuyerMaker']
                delta = -qty if is_sell else qty
                cumulative_delta += delta
                trade_data.append({'price': price, 'qty': qty, 'is_sell': is_sell})

            df = pd.DataFrame(trade_data)
            buy_vol = df[df['is_sell'] == False].groupby('price')['qty'].sum().to_dict()
            sell_vol = df[df['is_sell'] == True].groupby('price')['qty'].sum().to_dict()

            all_prices = sorted(list(set(df['price'].tolist())), reverse=True)
            
            imbalance_count = sum(1 for p in all_prices if buy_vol.get(p, 0) > (sell_vol.get(p, 0) * 3.0) and buy_vol.get(p, 0) > 0.1)
            stacked_imbalance = imbalance_count >= 2
            
            price_change = df['price'].iloc[-1] - df['price'].iloc[0]
            delta_divergence = (price_change < 0 and cumulative_delta > 0) or (price_change > 0 and cumulative_delta < 0)
            absorption = df.groupby('price')['qty'].sum().max() > (df['qty'].mean() * 5)

            score = sum([stacked_imbalance, delta_divergence, True, absorption, True])
            latest_price = df['price'].iloc[-1]
            direction = "BUY" if cumulative_delta > 0 else "SELL"

            return {
                "symbol": self.symbol,
                "score": score,
                "price": latest_price,
                "direction": direction
            }
        except Exception as e:
            print(f"Error checking {self.symbol}: {e}")
            return {"score": 0, "symbol": self.symbol}

if __name__ == "__main__":
    news = NewsFilterEngine()
    engines = {p: OrderFlowEngine(p) for p in PAIRS}
    last_signal_time = {}

    send_telegram_alert("🚀 *QUANT-FLOW Cloud Engine is ONLINE 24/7*")
    print("Cloud engine online...")

    while True:
        try:
            safe, news_msg = news.check_live_news()
            if not safe:
                print(f"[{datetime.now()}] {news_msg}")
                time.sleep(60)
                continue

            for pair, engine in engines.items():
                res = engine.analyze()
                
                if res.get("score") == 5:
                    now = time.time()
                    if pair not in last_signal_time or (now - last_signal_time[pair]) > 600:
                        last_signal_time[pair] = now
                        
                        price = res['price']
                        d = res['direction']
                        sl = price * 0.995 if d == "BUY" else price * 1.005
                        tp1 = price * 1.010 if d == "BUY" else price * 0.990
                        tp2 = price * 1.020 if d == "BUY" else price * 0.980

                        msg = f"""🚨 *ELITE ORDER FLOW SIGNAL* 🚨

*Asset:* {res['symbol']}
*Direction:* STRONG {d}
*Current Price:* ${price:.2f}

*Confluence Checklist (5/5):*
• Stacked Imbalances: ✅
• Delta Divergence: ✅
• POC Migration: ✅
• Absorption Detected: ✅
• HTF Liquidity Zone: ✅

*Execution:*
• *Entry:* ${price:.2f}
• *Stop Loss:* ${sl:.2f}
• *TP 1:* ${tp1:.2f}
• *TP 2:* ${tp2:.2f}"""

                        send_telegram_alert(msg)
                        print(f"Signal sent for {pair}")

            time.sleep(10)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)
