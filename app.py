from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os
import json
import re
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("WARNING: GEMINI_API_KEY not found in .env file!")
else:
    genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-1.5-flash")

# In-memory storage for reports (simple list, resets when server restarts)
reports = []


def fallback_analysis(location, description):
    """
    Rule-based backup analyzer used ONLY if the live Gemini API call fails
    (e.g. quota issues). Keeps the app fully functional for demo purposes.
    """
    text = description.lower()

    if any(word in text for word in ["medical", "injury", "hurt", "faint", "bleeding", "emergency", "doctor"]):
        category, urgency = "Medical", "High"
        suggestion = "Dispatch nearest medical team immediately and clear the surrounding area."
    elif any(word in text for word in ["crowd", "bheed", "rush", "packed", "overcrowd", "stampede"]):
        category, urgency = "Crowd Management", "High"
        suggestion = "Redirect incoming fans to an alternate gate and deploy extra volunteers to manage flow."
    elif any(word in text for word in ["lost", "missing", "child", "bag", "item"]):
        category, urgency = "Lost and Found", "Medium"
        suggestion = "Log the item/person at the nearest help desk and broadcast a short announcement."
    elif any(word in text for word in ["clean", "garbage", "spill", "overflow", "washroom", "toilet"]):
        category, urgency = "Cleanup", "Medium"
        suggestion = "Send a cleaning crew to the location and mark the area for a follow-up check."
    elif any(word in text for word in ["fight", "threat", "suspicious", "security", "unruly"]):
        category, urgency = "Security", "High"
        suggestion = "Alert on-site security personnel and monitor the situation closely."
    else:
        category, urgency = "Other", "Low"
        suggestion = "Log the report and monitor; escalate if the situation develops further."

    return {"category": category, "urgency": urgency, "suggestion": suggestion}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/report", methods=["POST"])
def report():
    data = request.get_json()
    location = data.get("location", "").strip()
    description = data.get("description", "").strip()

    if not location or not description:
        return jsonify({"error": "Location and description are required"}), 400

    ai_result = None
    used_fallback = False

    prompt = f"""
You are an AI assistant helping stadium operations volunteers during a major sports tournament.

A volunteer submitted this issue report:
Location: {location}
Description: {description}

Respond ONLY in this exact JSON format, no extra text:
{{
  "category": "one of: Crowd Management, Cleanup, Medical, Lost and Found, Security, Other",
  "urgency": "one of: Low, Medium, High",
  "suggestion": "a short 1-2 sentence action suggestion for the control room"
}}
"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        text = re.sub(r"```json|```", "", text).strip()
        ai_result = json.loads(text)
    except Exception as e:
        print("Gemini API call failed, using fallback analyzer:", e)
        ai_result = fallback_analysis(location, description)
        used_fallback = True

    report_entry = {
        "id": len(reports) + 1,
        "location": location,
        "description": description,
        "category": ai_result.get("category", "Other"),
        "urgency": ai_result.get("urgency", "Medium"),
        "suggestion": ai_result.get("suggestion", "No suggestion available"),
        "source": "backup analyzer" if used_fallback else "Gemini AI",
    }

    reports.append(report_entry)
    return jsonify(report_entry), 200


@app.route("/reports", methods=["GET"])
def get_reports():
    urgency_order = {"High": 0, "Medium": 1, "Low": 2}
    sorted_reports = sorted(reports, key=lambda r: urgency_order.get(r["urgency"], 3))
    return jsonify(sorted_reports), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
