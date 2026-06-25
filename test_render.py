"""Test live Render deployment"""
import sys
import requests
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://vrai-trade-buddy.onrender.com"

print("=== HEALTH ===")
r = requests.get(f"{BASE}/health", timeout=20)
print(r.json())

print("\n=== FII/DII ===")
r2 = requests.get(f"{BASE}/market/fii-dii", timeout=20)
d = r2.json()
print(f"FII Net: {d.get('fii_net')} Cr | DII Net: {d.get('dii_net')} Cr | Date: {d.get('date')}")

print("\n=== OI WALLS (Render IP) ===")
r3 = requests.get(f"{BASE}/market/walls?symbol=NIFTY", timeout=25)
w = r3.json()
print("Spot:", w.get("spot"))
print("CE Walls:", w.get("ce_walls", []))
print("PE Walls:", w.get("pe_walls", []))

print("\n=== CHAT TEST ===")
r4 = requests.post(f"{BASE}/chat", json={"message": "Aaj market kaisi hai? Quick 1 line mein bolo."}, timeout=30)
resp = r4.json()
print("AI:", resp.get("response", "")[:200])

print("\nAll tests done!")
