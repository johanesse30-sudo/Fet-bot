from flask import Flask, request, jsonify
import hmac, hashlib, time, requests, json, os

app = Flask(__name__)

# ─── CONFIG BINANCE ───
API_KEY    = os.environ.get("BINANCE_API_KEY")
API_SECRET = os.environ.get("BINANCE_API_SECRET")
BASE_URL   = "https://fapi.binance.com"

def sign(params):
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()
    return query + f"&signature={sig}"

def place_order(symbol, side, order_type="MARKET", quantity=10):
    params = {
        "symbol":    symbol,
        "side":      side,
        "type":      order_type,
        "quantity":  quantity,
        "timestamp": int(time.time() * 1000)
    }
    headers = {"X-MBX-APIKEY": API_KEY}
    url = f"{BASE_URL}/fapi/v1/order?{sign(params)}"
    res = requests.post(url, headers=headers)
    return res.json()

# ─── WEBHOOK ENDPOINT ───
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("Signal reçu:", data)

    side   = data.get("side")
    symbol = data.get("symbol", "FETUSDT")

    if side in ["BUY", "SELL"]:
        result = place_order(symbol, side)
        return jsonify({"status": "ok", "result": result})

    return jsonify({"status": "ignored"})

@app.route("/")
def index():
    return "Bot actif ✅"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
