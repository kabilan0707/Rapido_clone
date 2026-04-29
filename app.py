"""
============================================================
  RAPIDO CLONE — COMPLETE FLASK BACKEND
  File: app.py
  Run: python app.py
  Requires: pip install flask flask-socketio mysql-connector-python
============================================================
"""

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, join_room, emit
import mysql.connector
import random
from decimal import Decimal

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rapido_secret_2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# ============================================================
# HELPER — Convert Decimal/bytes to native Python types for JSON
# ============================================================
def to_float(val):
    if val is None:
        return None
    return float(val)

def clean_ride(ride):
    """Convert all Decimal fields in a ride dict to float."""
    for key in ['distance','amount','pickup_lat','pickup_lng','drop_lat','drop_lng','rating']:
        if key in ride and ride[key] is not None:
            ride[key] = to_float(ride[key])
    return ride

# ============================================================
# DB CONNECTION
# ============================================================
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Tn05z2345",   # <-- Change to your MySQL password
        database="rapido_clone"
    )

# ============================================================
# DEBUG — Test DB connection (remove in production)
# ============================================================
@app.route('/debug')
def debug():
    try:
        db  = get_db()
        cur = db.cursor()
        cur.execute("SHOW TABLES")
        tables = [row[0] for row in cur.fetchall()]
        db.close()
        return jsonify({"status": "DB Connected ✅", "tables": tables})
    except Exception as e:
        return jsonify({"status": "DB Error ❌", "error": str(e)}), 500

# ============================================================
# PAGE ROUTES
# ============================================================
@app.route('/')
def home():
    return render_template("index.html")      # Customer page

@app.route('/rider')
def rider_page():
    return render_template("rider.html")      # Captain page

# ============================================================
# USER LOGIN / REGISTER
# ============================================================
@app.route('/login', methods=['POST'])
def user_login():
    try:
        data   = request.json or {}
        name   = data.get('name', '').strip()
        mobile = data.get('mobile', '').strip()

        if not name or not mobile:
            return jsonify({"error": "Name and mobile required"}), 400

        db  = get_db()
        cur = db.cursor(dictionary=True)

        cur.execute("SELECT id FROM users WHERE mobile = %s", (mobile,))
        existing = cur.fetchone()

        if existing:
            db.close()
            return jsonify({"user_id": existing['id'], "message": "Welcome back!"})

        cur.execute("INSERT INTO users (name, mobile) VALUES (%s, %s)", (name, mobile))
        db.commit()
        user_id = cur.lastrowid
        db.close()
        return jsonify({"user_id": user_id, "message": "Registered!"})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ============================================================
# RIDER (CAPTAIN) LOGIN / REGISTER
# ============================================================
@app.route('/rider_login', methods=['POST'])
def rider_login():
    db = get_db()
    cur = db.cursor(dictionary=True)
    data = request.json
    name       = data.get('name', '').strip()
    mobile     = data.get('mobile', '').strip()
    vehicle_no = data.get('vehicle', '').strip()

    if not name or not mobile or not vehicle_no:
        db.close()
        return jsonify({"error": "All fields required"}), 400

    # Check existing rider
    cur.execute("SELECT id FROM riders WHERE mobile = %s", (mobile,))
    existing = cur.fetchone()

    if existing:
        # Update vehicle number in case changed
        cur.execute("UPDATE riders SET vehicle_no = %s WHERE id = %s",
                    (vehicle_no, existing['id']))
        db.commit()
        db.close()
        return jsonify({"rider_id": existing['id'], "message": "Welcome back Captain!"})

    # New rider
    cur.execute(
        "INSERT INTO riders (name, mobile, vehicle_no) VALUES (%s, %s, %s)",
        (name, mobile, vehicle_no)
    )
    db.commit()
    rider_id = cur.lastrowid
    db.close()
    return jsonify({"rider_id": rider_id, "message": "Captain registered!"})


# ============================================================
# BOOK A RIDE (Customer)
# ============================================================
@app.route('/book', methods=['POST'])
def book_ride():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        # --- Extract fields ---
        user_id    = data.get('user_id')
        pickup     = str(data.get('pickup', '')).strip()
        drop       = str(data.get('drop', '')).strip()
        distance   = data.get('distance')
        pickup_lat = data.get('lat')
        pickup_lng = data.get('lng')
        drop_lat   = data.get('drop_lat')
        drop_lng   = data.get('drop_lng')

        # --- Validate ---
        missing = []
        if not user_id:        missing.append('user_id')
        if not pickup:         missing.append('pickup')
        if not drop:           missing.append('drop')
        if pickup_lat is None: missing.append('pickup_lat')
        if pickup_lng is None: missing.append('pickup_lng')
        if drop_lat   is None: missing.append('drop_lat (drop location select pannuvinga!)')
        if drop_lng   is None: missing.append('drop_lng (drop location select pannuvinga!)')
        if distance   is None: missing.append('distance')

        if missing:
            return jsonify({"error": "Missing: " + ", ".join(missing)}), 400

        # --- Type conversion ---
        user_id    = int(user_id)
        distance   = float(distance)
        pickup_lat = float(pickup_lat)
        pickup_lng = float(pickup_lng)
        drop_lat   = float(drop_lat)
        drop_lng   = float(drop_lng)
        amount     = round(distance * 15, 2)

        db  = get_db()
        cur = db.cursor(dictionary=True)

        # Get user info
        cur.execute("SELECT name, mobile FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        if not user:
            db.close()
            return jsonify({"error": "User not found"}), 404

        # Insert ride
        cur.execute("""
            INSERT INTO rides
                (user_id, pickup, drop_location, distance, amount, status,
                 pickup_lat, pickup_lng, drop_lat, drop_lng)
            VALUES (%s, %s, %s, %s, %s, 'REQUESTED', %s, %s, %s, %s)
        """, (user_id, pickup, drop, distance, amount,
              pickup_lat, pickup_lng, drop_lat, drop_lng))
        db.commit()
        ride_id = cur.lastrowid
        db.close()

        # Broadcast to all captains
        socketio.emit('new_ride', {
            "ride_id":     ride_id,
            "pickup":      pickup,
            "drop":        drop,
            "distance":    distance,
            "amount":      amount,
            "user_name":   user['name'],
            "user_mobile": user['mobile'],
            "pickup_lat":  pickup_lat,
            "pickup_lng":  pickup_lng,
            "drop_lat":    drop_lat,
            "drop_lng":    drop_lng
        })

        return jsonify({"ride_id": ride_id, "amount": amount, "status": "REQUESTED"})

    except Exception as e:
        import traceback
        traceback.print_exc()   # Print full error in terminal
        return jsonify({"error": str(e)}), 500


# ============================================================
# GET ALL PENDING RIDES (Captain page load)
# ============================================================
@app.route('/get_rides')
def get_rides():
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT r.id AS ride_id, r.pickup, r.drop_location, r.distance,
               r.amount, r.status, r.pickup_lat, r.pickup_lng,
               r.drop_lat, r.drop_lng,
               u.name AS user_name, u.mobile AS user_mobile
        FROM rides r
        JOIN users u ON r.user_id = u.id
        WHERE r.status = 'REQUESTED'
        ORDER BY r.requested_at DESC
        LIMIT 20
    """)
    rides = cur.fetchall()
    db.close()

    # Convert Decimal to float for JSON serialization
    rides = [clean_ride(r) for r in rides]

    return jsonify(rides)


# ============================================================
# ACCEPT RIDE (Captain)
# ============================================================
@app.route('/accept', methods=['POST'])
def accept_ride():
    db = get_db()
    cur = db.cursor(dictionary=True)
    data = request.json
    ride_id  = data.get('ride_id')
    rider_id = data.get('rider_id')

    # Check ride still available
    cur.execute("SELECT status, user_id FROM rides WHERE id = %s", (ride_id,))
    ride = cur.fetchone()

    if not ride:
        db.close()
        return jsonify({"error": "Ride not found"}), 404
    if ride['status'] != 'REQUESTED':
        db.close()
        return jsonify({"error": "Ride already taken or cancelled"}), 400

    otp = str(random.randint(1000, 9999))

    cur.execute("""
        UPDATE rides
        SET status = 'ACCEPTED', rider_id = %s, otp = %s, accepted_at = NOW()
        WHERE id = %s
    """, (rider_id, otp, ride_id))
    db.commit()

    # Get rider info to send to user
    cur.execute("SELECT name, mobile, vehicle_no FROM riders WHERE id = %s", (rider_id,))
    rider = cur.fetchone()
    db.close()

    # Send OTP + rider info to specific user
    socketio.emit('ride_accepted', {
        "otp":         otp,
        "ride_id":     ride_id,
        "rider_name":  rider['name'],
        "rider_mobile":rider['mobile'],
        "vehicle_no":  rider['vehicle_no']
    }, room=str(ride['user_id']))

    # Remove ride card from all other captains
    socketio.emit('ride_taken', {"ride_id": ride_id})

    return jsonify({"status": "accepted", "otp": otp})


# ============================================================
# VERIFY OTP + START RIDE (Captain enters OTP)
# ============================================================
@app.route('/verify', methods=['POST'])
def verify_otp():
    db = get_db()
    cur = db.cursor(dictionary=True)
    data = request.json
    ride_id = data.get('ride_id')
    otp     = data.get('otp')

    cur.execute(
        "SELECT * FROM rides WHERE id = %s AND otp = %s AND status = 'ACCEPTED'",
        (ride_id, otp)
    )
    ride = cur.fetchone()

    if not ride:
        db.close()
        return jsonify({"status": "error", "message": "Wrong OTP or ride not in accepted state"}), 400

    cur.execute(
        "UPDATE rides SET status = 'STARTED', started_at = NOW() WHERE id = %s",
        (ride_id,)
    )
    db.commit()
    db.close()

    # Notify user that ride started
    socketio.emit('ride_started', {"ride_id": ride_id}, room=str(ride['user_id']))

    return jsonify({"status": "started"})


# ============================================================
# FINISH RIDE (Captain ends ride)
# ============================================================
@app.route('/finish', methods=['POST'])
def finish_ride():
    db = get_db()
    cur = db.cursor(dictionary=True)
    data = request.json
    ride_id = data.get('ride_id')

    cur.execute(
        "SELECT user_id, rider_id, amount FROM rides WHERE id = %s",
        (ride_id,)
    )
    ride = cur.fetchone()

    if not ride:
        db.close()
        return jsonify({"error": "Ride not found"}), 404

    cur.execute(
        "UPDATE rides SET status = 'COMPLETED', completed_at = NOW() WHERE id = %s",
        (ride_id,)
    )
    # Update rider's total earnings and ride count
    cur.execute("""
        UPDATE riders
        SET total_rides = total_rides + 1,
            total_earnings = total_earnings + %s
        WHERE id = %s
    """, (to_float(ride['amount']), ride['rider_id']))
    db.commit()
    db.close()

    # Notify user to rate the ride
    socketio.emit('ride_completed', {
        "ride_id": ride_id,
        "amount":  to_float(ride['amount'])
    }, room=str(ride['user_id']))

    return jsonify({"status": "completed"})


# ============================================================
# COMPLETE RIDE + RATING (User submits rating)
# ============================================================
@app.route('/complete_ride', methods=['POST'])
def complete_ride():
    db = get_db()
    cur = db.cursor(dictionary=True)
    data    = request.json
    ride_id = data.get('ride_id')
    stars   = int(data.get('rating', 5))
    comment = data.get('comment', '')

    # Get ride for user/rider ids
    cur.execute("SELECT user_id, rider_id FROM rides WHERE id = %s", (ride_id,))
    ride = cur.fetchone()

    if not ride:
        db.close()
        return jsonify({"error": "Ride not found"}), 404

    # Save rating
    cur.execute("""
        INSERT INTO ratings (ride_id, user_id, rider_id, stars, comment)
        VALUES (%s, %s, %s, %s, %s)
    """, (ride_id, ride['user_id'], ride['rider_id'], stars, comment))

    # Update ride's rating column
    cur.execute("UPDATE rides SET rating = %s WHERE id = %s", (stars, ride_id))

    # Recalculate rider's avg rating
    cur.execute("""
        UPDATE riders r
        SET r.rating = (
            SELECT AVG(stars) FROM ratings WHERE rider_id = r.id
        )
        WHERE r.id = %s
    """, (ride['rider_id'],))

    db.commit()
    db.close()
    return jsonify({"status": "rated", "stars": stars})


# ============================================================
# CANCEL RIDE (User cancels)
# ============================================================
@app.route('/cancel', methods=['POST'])
def cancel_ride():
    db = get_db()
    cur = db.cursor(dictionary=True)
    data    = request.json
    ride_id = data.get('ride_id')
    user_id = data.get('user_id')

    cur.execute(
        "SELECT status, rider_id FROM rides WHERE id = %s AND user_id = %s",
        (ride_id, user_id)
    )
    ride = cur.fetchone()

    if not ride:
        db.close()
        return jsonify({"error": "Ride not found"}), 404

    if ride['status'] in ('COMPLETED', 'CANCELLED'):
        db.close()
        return jsonify({"error": "Cannot cancel this ride"}), 400

    cur.execute(
        "UPDATE rides SET status = 'CANCELLED' WHERE id = %s",
        (ride_id,)
    )
    db.commit()
    db.close()

    # Notify all riders (remove the card)
    socketio.emit('ride_cancelled', {"ride_id": ride_id})

    return jsonify({"status": "cancelled"})


# ============================================================
# RIDER HISTORY (Captain sees past rides)
# ============================================================
@app.route('/rider_history/<int:rider_id>')
def rider_history(rider_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT r.id AS ride_id, r.pickup, r.drop_location, r.distance,
               r.amount, r.status, r.rating, r.payment_method,
               r.requested_at, r.completed_at,
               u.name AS user_name
        FROM rides r
        JOIN users u ON r.user_id = u.id
        WHERE r.rider_id = %s
        ORDER BY r.requested_at DESC
        LIMIT 50
    """, (rider_id,))
    rides = cur.fetchall()
    db.close()
    rides = [clean_ride(r) for r in rides]
    return jsonify(rides)


# ============================================================
# USER HISTORY (Customer sees past rides)
# ============================================================
@app.route('/user_history/<int:user_id>')
def user_history(user_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("""
        SELECT r.id AS ride_id, r.pickup, r.drop_location, r.distance,
               r.amount, r.status, r.rating, r.payment_method,
               r.requested_at, r.completed_at,
               rd.name AS rider_name, rd.vehicle_no
        FROM rides r
        LEFT JOIN riders rd ON r.rider_id = rd.id
        WHERE r.user_id = %s
        ORDER BY r.requested_at DESC
        LIMIT 50
    """, (user_id,))
    rides = cur.fetchall()
    db.close()
    rides = [clean_ride(r) for r in rides]
    return jsonify(rides)


# ============================================================
# SOCKET EVENTS — JOIN ROOMS
# ============================================================
@socketio.on('join')
def on_join(data):
    # user_id or rider_id — both join their own room
    room = str(data.get('user_id') or data.get('rider_id'))
    join_room(room)
    print(f"[SOCKET] Joined room: {room}")

@socketio.on('connect')
def on_connect():
    print(f"[SOCKET] Client connected: {request.sid}")

@socketio.on('disconnect')
def on_disconnect():
    print(f"[SOCKET] Client disconnected: {request.sid}")


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  Rapido Clone Backend — Starting...")
    print("  Customer:  http://localhost:5000/")
    print("  Captain:   http://localhost:5000/rider")
    print("=" * 50)
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)