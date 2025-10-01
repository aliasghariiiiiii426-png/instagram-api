import os
import requests
from flask import Flask, request, redirect, session
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "your-random-secret-key"  # Needed for session storage

APP_ID = os.getenv("APP_ID")
APP_SECRET = os.getenv("APP_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")


# ----------------------------
# Step 1: Instagram Business Login
# ----------------------------
@app.route("/login")
def login():
    auth_url = (
        f"https://www.facebook.com/v21.0/dialog/oauth?"
        f"client_id={APP_ID}&redirect_uri={REDIRECT_URI}"
        f"&scope=instagram_basic,pages_show_list,instagram_manage_insights,instagram_manage_comments"
    )
    return redirect(auth_url)


# ----------------------------
# Step 2: OAuth Callback
# ----------------------------
@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Error: No code received", 400

    token_url = "https://graph.facebook.com/v21.0/oauth/access_token"
    params = {
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "client_secret": APP_SECRET,
        "code": code
    }

    res = requests.get(token_url, params=params).json()
    access_token = res.get("access_token")
    session["short_lived_token"] = access_token

    return f"Short-lived token received! <a href='/exchange'>Exchange for long-lived</a>"


# ----------------------------
# Step 3: Exchange Short-lived → Long-lived Token
# ----------------------------
@app.route("/exchange")
def exchange():
    short_token = session.get("short_lived_token")
    if not short_token:
        return "No short-lived token. Please login again.", 400

    url = "https://graph.facebook.com/v21.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": APP_ID,
        "client_secret": APP_SECRET,
        "fb_exchange_token": short_token
    }

    res = requests.get(url, params=params).json()
    session["long_lived_token"] = res.get("access_token")

    return f"Long-lived token saved! <a href='/profile'>Get IG Profile</a>"


# ----------------------------
# Step 4: Fetch Instagram Profile
# ----------------------------
@app.route("/profile")
def profile():
    token = session.get("long_lived_token")
    if not token:
        return "No token. Please login again.", 400

    # Get user pages
    url = "https://graph.facebook.com/v21.0/me/accounts"
    params = {"access_token": token}
    res = requests.get(url, params=params).json()

    # Take first page (example)
    page_id = res["data"][0]["id"]

    # Get IG Business Account linked to Page
    url = f"https://graph.facebook.com/v21.0/{page_id}"
    params = {"fields": "instagram_business_account", "access_token": token}
    res = requests.get(url, params=params).json()

    ig_user_id = res["instagram_business_account"]["id"]

    # Get IG profile info
    url = f"https://graph.facebook.com/v21.0/{ig_user_id}"
    params = {"fields": "id,username,followers_count,media_count", "access_token": token}
    res = requests.get(url, params=params).json()

    return res


# ----------------------------
# Step 5: Webhook Verification (GET)
# ----------------------------
@app.route("/webhook", methods=["GET"])
def webhook_verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    else:
        return "Verification failed", 403


# ----------------------------
# Step 6: Webhook Listener (POST)
# ----------------------------
@app.route("/webhook", methods=["POST"])
def webhook_receive():
    data = request.json
    print("📩 Webhook event received:", data)

    # Example: handle new IG comment
    if "entry" in data:
        for entry in data["entry"]:
            changes = entry.get("changes", [])
            for change in changes:
                print("Change detected:", change)

    return "EVENT_RECEIVED", 200


# ----------------------------
# Run Flask on Port 80
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
