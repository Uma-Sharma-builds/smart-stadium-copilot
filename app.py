from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configure Gemini API
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("WARNING: GEMINI_API_KEY not found in .env file!")
else:
    genai.configure(api_key=api_key)

model = genai.GenerativeModel("gemini-2.0-flash")

# In-memory storage for reports (simple list, resets when server restarts)
reports = []


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
        # Clean up if Gemini wraps response in markdown code fences
        text = text.replace("```json", "").replace("```", "").strip()

        import json
        ai_result = json.loads(text)

        report_entry = {
            "id": len(reports) + 1,
            "location": location,
            "description": description,
            "category": ai_result.get("category", "Other"),
            "urgency": ai_result.get("urgency", "Medium"),
            "suggestion": ai_result.get("suggestion", "No suggestion available"),
        }

        reports.append(report_entry)
        return jsonify(report_entry), 200

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"error": f"AI processing failed: {str(e)}"}), 500


@app.route("/reports", methods=["GET"])
def get_reports():
    urgency_order = {"High": 0, "Medium": 1, "Low": 2}
    sorted_reports = sorted(reports, key=lambda r: urgency_order.get(r["urgency"], 3))
    return jsonify(sorted_reports), 200


if __name__ == "__main__":
    app.run(debug=True, port=5000)
