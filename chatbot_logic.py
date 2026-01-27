import os
import json
import sqlite3
import re
from datetime import datetime
from flask import session

# =========================
# LOAD MENU
# =========================
MENU_PATH = "bots/food/menu.json"

if os.path.exists(MENU_PATH):
    with open(MENU_PATH, encoding="utf-8") as f:
        MENU = json.load(f)
else:
    print("Menu file not found.")

MENU_ITEMS = {}
if "categories" in MENU:
    for category, items in MENU["categories"].items():
        for item, price in items.items():
            MENU_ITEMS[item.lower()] = price
else:
    MENU_ITEMS = {k.lower(): v for k, v in MENU.items()}

# =========================
# SESSION MEMORY (per-user)
# =========================
def get_user_session():
    if 'order' not in session:
        session['order'] = []
    return session

# =========================
# NORMALIZATION
# =========================
def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()

# =========================
# INTENT DETECTION
# =========================
def is_greeting(text):
    return any(w in text for w in ["hi", "hello", "salam", "assalamualaikum", "aoa", "hey"])

def is_menu_request(text):
    return any(w in text for w in ["menu", "what do you have"])

def is_confirmation(text):
    return any(w in text for w in ["confirm"])

def is_negative(text):
    return text in ["no", "nah", "nope"]

# =========================
# PARSE ORDER ITEMS
# =========================
from spacy.matcher import PhraseMatcher

matcher = PhraseMatcher(nlp.vocab)
# Create patterns from your MENU_ITEMS keys
patterns = [nlp.make_doc(text) for text in MENU_ITEMS.keys()]
matcher.add("MENU_LIST", patterns)

def extract_complex_order(text):
    doc = nlp(text.lower())
    matches = matcher(doc)
    found = []

    for match_id, start, end in matches:
        span = doc[start:end] # This is the food item (e.g., "zinger burger")
        qty = 1
        
        # Look at the word immediately before the food item
        if start > 0:
            previous_word = doc[start - 1]
            if previous_word.pos_ == "NUM":
                # Convert "two" to 2 or use .text if it's "2"
                qty = int(previous_word.text) 
                
        found.append((span.text, qty))
    return found

# =========================
# DATABASE
# =========================
def save_order(order, user_id):
    conn = sqlite3.connect("orders.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            item TEXT,
            quantity INTEGER,
            price INTEGER,
            total INTEGER,
            order_time TEXT
        )
    """)
    for o in order:
        cur.execute("""
            INSERT INTO orders VALUES (NULL,?,?,?,?,?,?)
        """, (
            user_id,
            o["item"],
            o["qty"],
            o["price"],
            o["total"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
    conn.commit()
    conn.close()

# =========================
# MENU DISPLAY
# =========================
def show_menu():
    reply = "🍽️ *FoodExpress Café Menu*\n\n"
    if "categories" in MENU:
        for category, items in MENU["categories"].items():
            reply += f"**{category.replace('_', ' ').title()}**\n"
            for item, price in items.items():
                reply += f"• {item.title()} — Rs. {price}\n"
            reply += "\n"
    else:
        for item, price in MENU_ITEMS.items():
            reply += f"• {item.title()} — Rs. {price}\n"
    reply += "🛒 You can order like:\n`2 zinger burgers and 1 latte`"
    return reply

# =========================
# MAIN CHAT LOGIC
# =========================
def get_response(user_input, bot_id="food"):
    user_session = get_user_session()
    text = normalize(user_input)
    user_id = session.get('user_id', 'anonymous')  # Simple user ID, can be improved

    # ---- GREETING ----
    if is_greeting(text):
        return "👋 Salam! Welcome to *FoodExpress Café*.\nType *menu* to see our items 🍔☕"

    # ---- MENU ----
    if is_menu_request(text):
        return show_menu()

    # ---- CONFIRM ORDER ----
    if is_confirmation(text):
        if not user_session["order"]:
            return "🛒 You haven’t ordered anything yet."
        save_order(user_session["order"], user_id)
        user_session["order"].clear()
        return "✅ *Order Confirmed!*\n🚚 Delivery in 30–45 minutes.\nThank you 💜"

    # ---- ORDER PARSING ----
    items = extract_complex_order(text)

    if items:
        reply = ""
        for item, qty in items:
            price = MENU_ITEMS.get(item, 0)
            total = price * qty
            user_session["order"].append({
                "item": item,
                "qty": qty,
                "price": price,
                "total": total
            })
            reply += f"✅ {qty} × {item.title()} added (Rs. {total})\n"

        reply += "\nWould you like to order anything else? (yes / confirm)"
        return reply

    # ---- ITEM NOT FOUND ----
    if any(w in text for w in ["burger", "pizza", "zinger", "icecream"]):
        return "❌ Sorry, that item is not available in our menu.\nType *menu* to see available items."

    # ---- DELIVERY INFO ----
    if "delivery" in text:
        if "charge" in text:
            return "🚚 No delivery charges 😊"
        return "⏱️ Delivery time is 30–45 minutes."

    # ---- FALLBACK ----
    return "🤔 I didn’t understand that.\nTry typing *menu* or place an order like:\n`1 burger and 1 fries`"
