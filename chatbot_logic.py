import os
import json
import sqlite3
import re
from datetime import datetime
from flask import Flask, request, jsonify, session
from flask_cors import CORS
import spacy
from spacy.matcher import PhraseMatcher
from thefuzz import process, fuzz

app = Flask(__name__)
app.secret_key = "your_secret_key"
CORS(app, supports_credentials=True)

# Load spacy model
nlp = spacy.load('en_core_web_sm')

# =========================
# LOAD MENU
# =========================
MENU_PATH = "bots/food/menu.json"
MENU_ITEMS = {}
MENU = {}

if os.path.exists(MENU_PATH):
    with open(MENU_PATH, encoding="utf-8") as f:
        MENU = json.load(f)
    if "categories" in MENU:
        for category, items in MENU["categories"].items():
            for item, price in items.items():
                MENU_ITEMS[item.lower()] = price
    else:
        MENU_ITEMS = {k.lower(): v for k, v in MENU.items()}

# PhraseMatcher for exact matches
matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
patterns = [nlp.make_doc(text) for text in MENU_ITEMS.keys()]
matcher.add("MENU_LIST", patterns)

# =========================
# FUZZY INTENT DICTIONARY
# =========================
# Added "cart" and "view" so the bot understands "show my cart"
INTENTS = {
    "greeting": ["hi", "hello", "salam", "hey"],
    "menu_req": ["menu", "what do you have","food","show menu"],
    "confirm": ["confirm", "checkout", "place order", "yes", "yeah", "ok"],
    "cancel": ["no", "nah", "nope", "cancel", "clear", "stop", "done"],
    "add_more": ["add more", "more", "add something else", "buy more", "want more"], # NEW
    "thanks": ["thank", "thanks", "shukriya"],
    "view_cart": ["cart", "basket", "show cart", "view basket"]
}

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
# FUZZY INTENTS
# =========================
def get_fuzzy_intent(text):
    normalized_text = normalize(text)
    words = normalized_text.split()
    
    intent_scores = {} # Store the best score for EACH intent
    
    for intent, synonyms in INTENTS.items():
        current_best = 0
        
        # 1. Check individual words (High Precision)
        for word in words:
            if len(word) < 3: continue
            _, word_score = process.extractOne(word, synonyms, scorer=fuzz.ratio)
            if word_score > current_best:
                current_best = word_score
        
        # 2. Check the whole sentence (Context)
        _, sentence_score = process.extractOne(normalized_text, synonyms, scorer=fuzz.token_set_ratio)
        if sentence_score > current_best:
            current_best = sentence_score
            
        intent_scores[intent] = current_best
        print(f"DEBUG: Intent: {intent:10} | Score: {current_best}")

    # Find the intent with the absolute highest score
    best_intent = max(intent_scores, key=intent_scores.get)
    highest_score = intent_scores[best_intent]

    # Threshold check
    if highest_score > 70:
        return best_intent
            
    return None

# =========================
# FUZZY ORDER PARSING
# =========================
def extract_fuzzy_order(text):
    doc = nlp(text.lower())
    matches = matcher(doc)
    found = []
    matched_indices = set()

    # 1. Exact Matches
    for match_id, start, end in matches:
        span = doc[start:end]
        qty = 1
        if start > 0 and doc[start-1].pos_ == "NUM":
            try:
                # Handle "2" or "two"
                t = doc[start-1].text
                qty = int(t) if t.isdigit() else 1 
            except: qty = 1
        found.append((span.text, qty))
        for i in range(start, end): matched_indices.add(i)

    # 2. Fuzzy Typo Matches (for words not caught by PhraseMatcher)
    words = [t.text for i, t in enumerate(doc) if i not in matched_indices and len(t.text) > 3]
    for word in words:
        match, score = process.extractOne(word, MENU_ITEMS.keys(), scorer=fuzz.ratio)
        if score > 85:
            found.append((match, 1))
            
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
    reply += "<hr>🛒 <b>Order:</b> <code>2 burger and 1 coke</code>"
    return reply

# =========================
# MAIN CHAT LOGIC
# =========================
def get_response(user_input, bot_id="food"):
    user_session = get_user_session()
    intent = get_fuzzy_intent(user_input)
    text = normalize(user_input)
    user_id = session.get('user_id', 'anonymous')

    # --- 1. STATE: FINAL DB COMMIT (The very last step) ---
    if user_session.get("state") == "awaiting_final_confirmation":
        if intent == "confirm":
            save_order(user_session["order"], user_id) 
            user_session["order"].clear()
            user_session["state"] = None
            session.modified = True
            return "✅ <b>Order Confirmed!</b><br>🚚 Delivery in 30–45 mins. Thank you! 💜"
        elif intent == "cancel":
            user_session["order"].clear()
            user_session["state"] = None
            session.modified = True
            return "❌ Order cancelled and cart cleared."

    # --- 2. THE "CONFIRM" TRIGGER (Show order and ask for final OK) ---
    # If user says "confirm" at any time and has items in cart
    if intent == "confirm" and user_session.get("order"):
        user_session["state"] = "awaiting_final_confirmation"
        session.modified = True
        
        cart_view = "📋 <b>ORDER SUMMARY</b><br>━━━━━━━━━━━━━━━━━━━<br>"
        grand_total = sum(o['total'] for o in user_session['order'])
        for o in user_session["order"]:
            cart_view += f"• {o['qty']}x <i>{o['item'].title()}</i> — <code>Rs. {o['total']}</code><br>"
        
        cart_view += f"━━━━━━━━━━━━━━━━━━━<br>💰 <b>Total Bill: Rs. {grand_total}</b><br><br>"
        cart_view += "Is this correct? Type <b>CONFIRM</b> to place your order or <b>ADD MORE</b>."
        return cart_view

    # --- 3. STATE: AWAITING MORE ITEMS (After adding food) ---
    if user_session.get("state") == "awaiting_more":
        if intent == "add_more": 
            user_session["state"] = None 
            session.modified = True
            return "Great! What else would you like to add? 🍔"
        
        elif intent == "cancel": # User said "No" or "That's it"
            # Instead of asking "anything else," we jump to the summary
            return get_response("confirm") # Recursively call confirm logic

    # --- 4. NORMAL FLOW ---
    if intent == "greeting":
        if user_session.get("order"):
            return "👋 Salam! You have items in your cart. Type <b>cart</b> to view them or <b>menu</b> to add more!"
        return "👋 Salam! Welcome to *FoodExpress Café*.<br>Type *menu* to see our items 🍔☕"

    if intent == "menu_req":
        return show_menu()

    if intent == "view_cart":
        if not user_session.get("order"):
            return "🛒 Your cart is empty! Type *menu* to see our items."
        
        # Re-use the same summary logic
        return get_response("confirm") 

    # --- 5. ORDER PARSING ---
    items = extract_fuzzy_order(user_input)
    if items:
        for new_item, new_qty in items:
            price = MENU_ITEMS.get(new_item, 0)
            subtotal = price * new_qty
            found_in_cart = False
            for existing in user_session["order"]:
                if existing["item"] == new_item:
                    existing["qty"] += new_qty
                    existing["total"] += subtotal
                    found_in_cart = True
                    break
            if not found_in_cart:
                user_session["order"].append({"item": new_item, "qty": new_qty, "price": price, "total": subtotal})
        
        user_session["state"] = "awaiting_more"
        session.modified = True
        return "✅ Added to your basket! Would you like to **Add More** or **Confirm** your order?"

    return "🤔 I didn't quite get that. Type *menu* or *cart* to check your order!"