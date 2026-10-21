import os
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "travel-world-demo-key-change-me")

PACKAGES = [
    {"name": "Jaipur Heritage Escape", "place": "Jaipur, Rajasthan", "days": "3 Days / 2 Nights", "price": "₹6,999", "image": "https://images.unsplash.com/photo-1599661046827-dacff0c0f09a?auto=format&fit=crop&w=900&q=80", "tag": "Culture"},
    {"name": "Goa Beach Break", "place": "Goa, India", "days": "4 Days / 3 Nights", "price": "₹9,499", "image": "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?auto=format&fit=crop&w=900&q=80", "tag": "Beach"},
    {"name": "Himalayan Getaway", "place": "Manali, Himachal Pradesh", "days": "5 Days / 4 Nights", "price": "₹12,999", "image": "https://images.unsplash.com/photo-1626621341517-bbf3d9990a23?auto=format&fit=crop&w=900&q=80", "tag": "Mountains"},
]

@app.get("/")
def home():
    return render_template("index.html", packages=PACKAGES)

@app.post("/api/enquiry")
def enquiry():
    data = request.get_json(silent=True) or request.form
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip()
    destination = str(data.get("destination", "")).strip()
    travel_date = str(data.get("travel_date", "")).strip()
    travellers = str(data.get("travellers", "")).strip()
    message = str(data.get("message", "")).strip()

    if not name or not email or not destination:
        return jsonify(ok=False, message="Please provide your name, email and destination."), 400

    # Demo-only: no database or email is configured. Log enquiry to Vercel function logs.
    print("DEMO ENQUIRY:", {"name": name, "email": email, "destination": destination,
          "travel_date": travel_date, "travellers": travellers, "message": message})
    return jsonify(ok=True, message="Thanks! Your demo enquiry was received. Connect an email or database to store enquiries permanently.")

@app.get("/api/health")
def health():
    return jsonify(status="ok", app="Travel World", mode="demo")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
