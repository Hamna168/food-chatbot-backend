import os
import json
import sqlite3
import re
from datetime import datetime
from flask import session
import spacy

# Load spacy model
nlp = spacy.load('en_core_web_sm')

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
        session.modified = True  # Tell Flask the session changed
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
    return any(w in text for w in ["confirm", "checkout", "place order", "yes"])

def is_negative(text):
    return text in ["no", "nah", "nope"]

def is_thanks(text):
    return any(w in text for w in ["thank", "thanks", "shukriya", "jazakallah", "ty"])

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
    
    # You don't need CREATE TABLE here if init_db() already ran
    for o in order:
        cur.execute("""
            INSERT INTO orders (user_id, item, quantity, price, total, order_time) 
            VALUES (?, ?, ?, ?, ?, ?)
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
    # Use <h4> for headings and <div> for spacing
    reply = "<h3>🍽️ FOOD EXPRESS CAFÉ MENU</h3><hr>"

    if "categories" in MENU:
        for category, items in MENU["categories"].items():
            category_name = category.replace('_', ' ').upper()
            reply += f"<div style='margin-top: 15px;'><b>{category_name}</b></div>"
            
            for item, price in items.items():
                reply += f"• <i>{item.title()}</i> — <code>Rs. {price}</code><br>"
    else:
        for item, price in MENU_ITEMS.items():
            reply += f"• <i>{item.title()}</i> — <code>Rs. {price}</code><br>"

    reply += "<hr>🛒 <b>How to Order:</b><br>"
    reply += "Type: <code>2 zinger burgers and 1 latte</code>"
    
    return reply

# =========================
# MAIN CHAT LOGIC
# =========================
def get_response(user_input, bot_id="food"):
    user_session = get_user_session()
    text = normalize(user_input)
    user_id = session.get('user_id', 'anonymous')

    # --- 1. PRIORITY STATE: FINAL CONFIRMATION ---
    # We move this to the top so "confirm" is handled here first!
    if user_session.get("state") == "awaiting_final_confirmation":
        if is_confirmation(text):
            save_order(user_session["order"], user_id)
            user_session["order"].clear()
            user_session["state"] = None
            session.modified = True
            return "✅ <b>Order Confirmed!</b><br>🚚 Delivery in 30–45 mins. Thank you! 💜"
        elif "cancel" in text or "no" in text:
            user_session["order"].clear()
            user_session["state"] = None
            session.modified = True
            return "❌ Order cancelled and cart cleared."

    # --- 2. PRIORITY STATE: AWAITING MORE ITEMS ---
    if user_session.get("state") == "awaiting_more":
        if any(w in text for w in ["yes", "yeah", "sure", "ha"]):
            user_session["state"] = None 
            session.modified = True
            return "Great! What else would you like? 🍔"
        
        elif any(w in text for w in ["no", "nah", "nope", "confirm", "done"]):
            user_session["state"] = "awaiting_final_confirmation"
            session.modified = True
            total = sum(item['total'] for item in user_session["order"])
            return f"Understood. Your total is <b>Rs. {total}</b>.<br>Type <b>CONFIRM</b> to place the order or <b>CANCEL</b> to delete."

    # --- 3. STATE: HANDLE EXISTING CART ON START ---
    if is_greeting(text) and user_session.get("order"):
        user_session["state"] = "handle_existing_cart"
        session.modified = True
        return "👋 Salam! Welcome back. I see items in your cart. 🛒<br>Would you like to <b>Continue</b> or <b>Clear</b>?"

    if user_session.get("state") == "handle_existing_cart":
        if "clear" in text or "cancel" in text:
            user_session["order"].clear()
            user_session["state"] = None
            session.modified = True
            return "🗑️ Cart cleared! What can I get for you today?"
        elif "continue" in text or "yes" in text:
            user_session["state"] = None
            session.modified = True
            return "Perfect! Add more items or type *cart* to see your total. 😊"

    # --- 4. NORMAL FLOW (Keywords) ---
    if is_greeting(text):
        return "👋 Salam! Welcome to *FoodExpress Café*.<br>Type *menu* to see our items 🍔☕"

    # --- HANDLE GRATITUDE ---
    if is_thanks(text):
        # If they just finished an order, make it more personal
        if not user_session.get("order"):
            return "😊 You're very welcome! At you service anytime. Type *menu* to discover our quality food! 🍔"
        else:
            return "😇 It's my pleasure! Would you like to **Confirm** the items in your cart now, or keep browsing the *menu*?"

    if is_menu_request(text):
        return show_menu()

    # SHOW CART LOGIC (Removed "confirm" from keywords here to avoid confusion)
    if any(w in text for w in ["cart", "basket", "show", "view"]) and "menu" not in text:
        if not user_session.get("order"):
            return "🛒 Your cart is currently empty! Type *menu* to see our items. 🍔"
        
        cart_view = "📋 <b>YOUR CURRENT ORDER</b><br>━━━━━━━━━━━━━━━━━━━<br>"
        grand_total = 0
        for o in user_session["order"]:
            cart_view += f"• {o['qty']}x <i>{o['item'].title()}</i> — <code>Rs. {o['total']}</code><br>"
            grand_total += o['total']
        cart_view += f"━━━━━━━━━━━━━━━━━━━<br>💰 <b>Total Bill: Rs. {grand_total}</b><br><br>"
        cart_view += "Would you like to <b>Confirm</b> this order, <b>Clear</b> it, or add <b>More</b>?"
        
        user_session["state"] = "awaiting_more"
        session.modified = True
        return cart_view
    
    # --- 5. ORDER PARSING ---
    items = extract_complex_order(text)
    if items:
        for new_item, new_qty in items:
            price = MENU_ITEMS.get(new_item, 0)
            subtotal = price * new_qty
            found = False
            for existing in user_session["order"]:
                if existing["item"] == new_item:
                    existing["qty"] += new_qty
                    existing["total"] += subtotal
                    found = True
                    break
            if not found:
                user_session["order"].append({"item": new_item, "qty": new_qty, "price": price, "total": subtotal})
        
        user_session["state"] = "awaiting_more"
        session.modified = True
        return "✅ Added to your basket! Would you like to add anything else? (Yes / No)"

    return "🤔 I didn't quite get that. Type *menu* or *cart* to check your order!"