"""Quick test runner for VRAI Trade Buddy"""
import sys
import os
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

PASS = "[PASS]"
FAIL = "[FAIL]"


def test_market_data():
    print("\n--- TEST 1: NSE Index Quote ---")
    from data.market_data import fetcher
    result = fetcher.get_index_quote("NIFTY 50")
    if result and result.get("last"):
        print(f"{PASS} NIFTY 50 last: {result['last']}, change: {result['pchange']}%")
    else:
        print(f"{FAIL} No index data returned")


def test_oi_walls():
    print("\n--- TEST 2: OI Walls ---")
    from data.market_data import fetcher
    walls = fetcher.find_oi_walls("NIFTY")
    if walls and walls.get("spot"):
        print(f"{PASS} Spot: {walls['spot']}, Expiry: {walls['expiry']}, PCR: {round(walls['pcr'], 2)}")
        for w in walls.get("ce_walls", []):
            print(f"  CE Wall: {w['strike']} (OI: {w['oi']:,})")
        for w in walls.get("pe_walls", []):
            print(f"  PE Wall: {w['strike']} (OI: {w['oi']:,})")
    else:
        print(f"{FAIL} No OI walls data")


def test_fii_dii():
    print("\n--- TEST 3: FII/DII Data ---")
    from data.market_data import fetcher
    data = fetcher.get_fii_dii_data()
    if data and data.get("date"):
        print(f"{PASS} Date: {data['date']}")
        print(f"  FII Net: {data['fii_net']}, DII Net: {data['dii_net']}")
    else:
        print(f"{FAIL} No FII/DII data")


def test_ai_brain():
    print("\n--- TEST 4: AI Brain ---")
    from core.brain import brain
    response = brain.chat("Say hello in 10 words as a trading expert")
    if response and len(response) > 5:
        print(f"{PASS} AI responded: {response[:100]}...")
    else:
        print(f"{FAIL} No AI response")


def test_morning_brief():
    print("\n--- TEST 5: Morning Brief Generation ---")
    from scanners.morning_brief import generate_morning_brief
    brief = generate_morning_brief()
    if brief and len(brief) > 50:
        print(f"{PASS} Morning brief generated ({len(brief)} chars)")
        print(f"  Preview: {brief[:200]}...")
    else:
        print(f"{FAIL} Morning brief empty or too short")


def test_btst_scan():
    print("\n--- TEST 6: BTST Scanner (dry run) ---")
    from scanners.btst_scanner import run_btst_scan
    result = run_btst_scan()
    if result:
        print(f"{PASS} BTST scan returned {len(result)} chars")
        print(f"  Preview: {result[:200]}...")
    else:
        print(f"{FAIL} BTST scan returned nothing")


def test_gamma_blast():
    print("\n--- TEST 7: Gamma Blast Scanner (dry run) ---")
    from scanners.gamma_blast import run_gamma_blast_scan
    alerts = run_gamma_blast_scan()
    print(f"{PASS} Gamma blast ran, alerts: {len(alerts) if alerts else 0}")


def test_notifier():
    print("\n--- TEST 8: Notifier (log only) ---")
    from notifications.notifier import send_notification, get_notification_log
    send_notification("Test message from test_runner.py", "TEST")
    log = get_notification_log()
    if log:
        print(f"{PASS} Notification logged: {log[-1]}")
    else:
        print(f"{FAIL} Notification not logged")


if __name__ == "__main__":
    print("=" * 50)
    print("VRAI Trade Buddy — Test Runner")
    print("=" * 50)

    test_market_data()
    test_oi_walls()
    test_fii_dii()
    test_ai_brain()
    test_morning_brief()
    test_btst_scan()
    test_gamma_blast()
    test_notifier()

    print("\n" + "=" * 50)
    print("All tests done!")
