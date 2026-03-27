# report.py
import os
import httpx
import openai
import json
from datetime import datetime, timedelta

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY")


# =============================================
# 1. Haal vragen op uit Supabase
# =============================================
async def get_questions(client_id: str, days: int = 30):
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{SUPABASE_URL}/rest/v1/chat_logs",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            },
            params={
                "client_id": f"eq.{client_id}",
                "created_at": f"gte.{since}",
                "select": "question,answer,created_at,session_id"
            }
        )
        return res.json()


# =============================================
# 2. Groepeer vragen op betekenis via AI
# =============================================
async def cluster_questions(questions: list):
    if not questions:
        return []

    vragenlijst = "\n".join([f"- {q['question']}" for q in questions])

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": """Je bent een data-analist. Je krijgt een lijst met vragen die bezoekers hebben gesteld aan een chatbot.
Groepeer deze vragen op semantische betekenis in maximaal 8 categorieën.
Geef elke categorie een duidelijke naam en tel hoeveel vragen erin vallen.
Geef ook een korte samenvatting van wat bezoekers willen weten in die categorie.
Antwoord ALLEEN in dit JSON formaat, zonder uitleg of markdown:
[
  {
    "categorie": "naam van categorie",
    "aantal": 5,
    "samenvatting": "korte beschrijving van wat bezoekers willen weten",
    "voorbeeldvraag": "meest representatieve vraag uit deze groep"
  }
]"""
            },
            {
                "role": "user",
                "content": f"Groepeer deze vragen:\n{vragenlijst}"
            }
        ],
        max_tokens=1000
    )

    raw = response["choices"][0]["message"]["content"]
    try:
        return json.loads(raw)
    except:
        return []


# =============================================
# 3. Genereer HTML rapport
# =============================================
def generate_html_report(client_id: str, questions: list, clusters: list, period_days: int = 30):
    total = len(questions)
    unique_sessions = len(set(q['session_id'] for q in questions))
    avg_per_session = round(total / unique_sessions, 1) if unique_sessions > 0 else 0

    period_label = f"Afgelopen {period_days} dagen"
    now = datetime.now().strftime("%d %B %Y")

    # Clusters HTML
    clusters_html = ""
    if clusters:
        sorted_clusters = sorted(clusters, key=lambda x: x['aantal'], reverse=True)
        for i, cluster in enumerate(sorted_clusters):
            percentage = round((cluster['aantal'] / total) * 100) if total > 0 else 0
            clusters_html += f"""
            <div style="background:#f8fffe; border:1px solid #e0f2e9; border-radius:8px; padding:20px; margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <strong style="color:#1a1a1a; font-size:16px;">{cluster['categorie']}</strong>
                    <span style="background:#2d6a4f; color:white; padding:4px 12px; border-radius:20px; font-size:13px; font-weight:600;">{cluster['aantal']} vragen</span>
                </div>
                <div style="background:#e0f2e9; border-radius:4px; height:8px; margin-bottom:10px;">
                    <div style="background:#2d6a4f; height:8px; border-radius:4px; width:{percentage}%;"></div>
                </div>
                <p style="color:#555; font-size:14px; margin:0 0 8px 0;">{cluster['samenvatting']}</p>
                <p style="color:#888; font-size:13px; margin:0;"><em>Voorbeeld: "{cluster['voorbeeldvraag']}"</em></p>
            </div>
            """
    else:
        clusters_html = "<p style='color:#888;'>Nog niet genoeg data voor clustering.</p>"

    html = f"""
<!DOCTYPE html>
<html lang="nl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chatbot Rapport — {client_id}</title>
</head>
<body style="margin:0; padding:0; background:#f4f4f2; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">

    <div style="max-width:640px; margin:40px auto; background:white; border-radius:12px; overflow:hidden; box-shadow: 0 4px 24px rgba(0,0,0,0.08);">

        <!-- Header -->
        <div style="background:#0a0a0a; padding:40px; text-align:center;">
            <p style="color:#52b788; font-size:12px; letter-spacing:3px; text-transform:uppercase; margin:0 0 8px 0;">Chatbot Rapport</p>
            <h1 style="color:white; font-size:28px; margin:0 0 8px 0; font-weight:700;">{client_id.capitalize()}</h1>
            <p style="color:rgba(255,255,255,0.4); font-size:14px; margin:0;">{period_label} · Gegenereerd op {now}</p>
        </div>

        <!-- Stats -->
        <div style="display:flex; border-bottom:1px solid #eee;">
            <div style="flex:1; padding:28px; text-align:center; border-right:1px solid #eee;">
                <div style="font-size:36px; font-weight:800; color:#2d6a4f;">{total}</div>
                <div style="font-size:13px; color:#888; margin-top:4px;">Totaal vragen</div>
            </div>
            <div style="flex:1; padding:28px; text-align:center; border-right:1px solid #eee;">
                <div style="font-size:36px; font-weight:800; color:#2d6a4f;">{unique_sessions}</div>
                <div style="font-size:13px; color:#888; margin-top:4px;">Unieke bezoekers</div>
            </div>
            <div style="flex:1; padding:28px; text-align:center;">
                <div style="font-size:36px; font-weight:800; color:#2d6a4f;">{avg_per_session}</div>
                <div style="font-size:13px; color:#888; margin-top:4px;">Vragen per bezoeker</div>
            </div>
        </div>

        <!-- Clusters -->
        <div style="padding:32px;">
            <h2 style="font-size:18px; font-weight:700; color:#1a1a1a; margin:0 0 20px 0;">Meest gestelde onderwerpen</h2>
            {clusters_html}
        </div>

        <!-- Footer -->
        <div style="background:#f8f8f8; padding:24px; text-align:center; border-top:1px solid #eee;">
            <p style="color:#aaa; font-size:12px; margin:0;">Dit rapport is automatisch gegenereerd door <strong style="color:#2d6a4f;">AI-Migo</strong></p>
            <p style="color:#aaa; font-size:12px; margin:4px 0 0 0;">Vragen? Mail naar <a href="mailto:info@ai-migo.nl" style="color:#2d6a4f;">info@ai-migo.nl</a></p>
        </div>

    </div>
</body>
</html>
"""
    return html


# =============================================
# 4. Verstuur rapport via Resend
# =============================================
async def send_report_email(to_email: str, client_id: str, html: str):
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "from": "onboarding@resend.dev",
                "to": [to_email],
                "subject": f"📊 Chatbot Rapport — {client_id.capitalize()} — {datetime.now().strftime('%B %Y')}",
                "html": html
            }
        )
        return res.status_code, res.text


# =============================================
# 5. Hoofdfunctie — alles samenvoegen
# =============================================
async def generate_and_send_report(client_id: str, to_email: str, days: int = 30):
    print(f"📊 Rapport genereren voor {client_id}...")

    questions = await get_questions(client_id, days)
    print(f"✅ {len(questions)} vragen opgehaald")

    clusters = await cluster_questions(questions)
    print(f"✅ {len(clusters)} categorieën gevonden")

    html = generate_html_report(client_id, questions, clusters, days)
    print(f"✅ HTML rapport gegenereerd")

    status, response = await send_report_email(to_email, client_id, html)
    print(f"✅ E-mail verstuurd — status: {status}")

    return {
        "success": status == 200,
        "questions": len(questions),
        "clusters": len(clusters),
        "email": to_email
    }
