import hmac, hashlib, time, requests, json, os
import numpy as np

# ─── CONFIG ───
API_KEY    = os.environ.get("BINANCE_API_KEY")
API_SECRET = os.environ.get("BINANCE_API_SECRET")
SYMBOL     = "FETUSDT"
INTERVAL   = "15m"
LEVERAGE   = 10
TP_PCT     = 2.0
SL_PCT     = 1.0
QTY        = 10
BASE_URL   = "https://fapi.binance.com"

# ─── SIGNATURE ───
def sign(params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    return query + f"&signature={sig}"

def headers():
    return {"X-MBX-APIKEY": API_KEY}

# ─── LEVIER ───
def set_leverage():
    params = {"symbol": SYMBOL, "leverage": LEVERAGE, "timestamp": int(time.time()*1000)}
    requests.post(f"{BASE_URL}/fapi/v1/leverage?{sign(params)}", headers=headers())

# ─── PRIX ───
def get_candles():
    url = f"{BASE_URL}/fapi/v1/klines?symbol={SYMBOL}&interval={INTERVAL}&limit=100"
    data = requests.get(url).json()
    closes = [float(c[4]) for c in data]
    return closes

# ─── KALMAN ───
def kalman(closes, gain=0.2):
    kf, velo = closes[0], 0.0
    for price in closes:
        dk = price - kf
        kf = kf + dk * (gain * 2) ** 0.5 + velo
        velo = velo + gain * dk
    return kf

# ─── TREND FILTER 2-POLE ───
def ema(data, period):
    k = 2 / (period + 1)
    result = [data[0]]
    for price in data[1:]:
        result.append(price * k + result[-1] * (1 - k))
    return result

def trend_filter(closes, period=20):
    pole1 = ema(closes, period)
    pole2 = ema(pole1, period)
    return pole2[-1], pole2[-2]

# ─── ORDRE ───
def place_order(side):
    params = {
        "symbol":   SYMBOL,
        "side":     side,
        "type":     "MARKET",
        "quantity": QTY,
        "timestamp": int(time.time()*1000)
    }
    res = requests.post(f"{BASE_URL}/fapi/v1/order?{sign(params)}", headers=headers())
    print(f"Ordre {side}:", res.json())

def close_position(side):
    close_side = "SELL" if side == "BUY" else "BUY"
    params = {
        "symbol":     SYMBOL,
        "side":       close_side,
        "type":       "MARKET",
        "quantity":   QTY,
        "reduceOnly": "true",
        "timestamp":  int(time.time()*1000)
    }
    requests.post(f"{BASE_URL}/fapi/v1/order?{sign(params)}", headers=headers())

# ─── LOGIQUE PRINCIPALE ───
def run():
    set_leverage()
    position = None
    entry_price = 0.0

    print("✅ Bot démarré")

    while True:
        try:
            closes = get_candles()
            price  = closes[-1]
            kf     = kalman(closes)
            trend_now, trend_prev = trend_filter(closes)

            bullish = price > trend_now
            bearish = price < trend_now
            crossover  = trend_prev < closes[-2] and trend_now > closes[-1]
            crossunder = trend_prev > closes[-2] and trend_now < closes[-1]

            long_signal  = bullish and price > kf and crossover
            short_signal = bearish and price < kf and crossunder

            print(f"Prix: {price} | KF: {kf:.4f} | Trend: {trend_now:.4f} | Position: {position}")

            # ─── GESTION TP/SL ───
            if position == "LONG":
                tp = entry_price * (1 + (TP_PCT/100)/LEVERAGE)
                sl = entry_price * (1 - (SL_PCT/100)/LEVERAGE)
                if price >= tp:
                    print("✅ TP atteint")
                    close_position("BUY")
                    position = None
                elif price <= sl:
                    print("❌ SL atteint")
                    close_position("BUY")
                    position = None

            elif position == "SHORT":
                tp = entry_price * (1 - (TP_PCT/100)/LEVERAGE)
                sl = entry_price * (1 + (SL_PCT/100)/LEVERAGE)
                if price <= tp:
                    print("✅ TP atteint")
                    close_position("SELL")
                    position = None
                elif price >= sl:
                    print("❌ SL atteint")
                    close_position("SELL")
                    position = None

            # ─── ENTRÉES ───
            if position is None:
                if long_signal:
                    print("🟢 Signal LONG")
                    place_order("BUY")
                    position = "LONG"
                    entry_price = price
                elif short_signal:
                    print("🔴 Signal SHORT")
                    place_order("SELL")
                    position = "SHORT"
                    entry_price = price

        except Exception as e:
            print("Erreur:", e)

        time.sleep(60)

if __name__ == "__main__":
    run()