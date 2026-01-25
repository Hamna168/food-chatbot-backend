# Food Chatbot App Update Plan

## Information Gathered
- **app.py**: Flask app with routes for web UI, API, and health check. Uses CORS, initializes DB.
- **chatbot_logic.py**: Handles responses, loads menu, manages global SESSION for orders, saves to DB. Basic keyword-based intent detection.
- **database.py**: Initializes SQLite DB with orders table (columns: id, item, quantity, price, total, order_time).
- **menu.json**: Structured with categories (burgers, pizzas, etc.), but code flattens it.
- **requirements.txt**: Includes unused scikit-learn.
- **Other files**: deploy.ps1 for Render, runtime.txt, start.sh, templates/index.html (basic UI).

Issues identified:
- DB column mismatch (time vs order_time).
- Global SESSION causes multi-user conflicts.
- Basic intent detection; menu not categorized.
- No per-user sessions, logging, or advanced features.
- Limited error handling.

## Plan
### Phase 1: Core Fixes ✅ COMPLETED
- [x] Fix database column mismatch in chatbot_logic.py.
- [x] Implement per-user sessions using Flask sessions.
- [x] Update menu display to show categories.
- [x] Add basic logging.

### Phase 2: Enhancements (Future)
- [ ] Enhance intent detection with NLP (using scikit-learn for classification).
- [ ] Add order management (view, modify, cancel).
- [ ] Improve error handling in API and DB operations.
- [ ] Update web UI for better UX (e.g., chat history, order summary).

### Phase 3: Optimization (Future)
- [ ] Add production optimizations (e.g., connection pooling for DB).
- [ ] Add health checks and monitoring.

## Dependent Files to be Edited
- chatbot_logic.py (major changes: sessions, intents, menu, orders).
- app.py (add session management, logging).
- database.py (fix schema if needed).
- menu.json (no change, but logic updates).
- requirements.txt (update dependencies).
- templates/index.html (UI improvements).

## Followup Steps
- [ ] Test locally after changes.
- [ ] Run deploy.ps1 to push to Render.
- [ ] Monitor logs on Render for errors.
- [ ] If NLP is added, train model on sample data.
