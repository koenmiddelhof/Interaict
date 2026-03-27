# main.py
import os
import httpx
import openai
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from report import generate_and_send_report

chat_memory = {}

openai.api_key = os.getenv("OPENAI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
REPORT_EMAIL = os.getenv("REPORT_EMAIL", "koenmiddelhof@hotmail.com")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================
# Maandelijkse scheduler
# =============================================
scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    # Elke 1e van de maand om 09:00
    scheduler.add_job(
        generate_and_send_report,
        "cron",
        day=1,
        hour=9,
        minute=0,
        kwargs={
            "client_id": "interaict",
            "to_email": REPORT_EMAIL,
            "days": 30
        }
    )
    scheduler.start()
    print("✅ Maandelijkse rapport scheduler gestart")


# =============================================
# Endpoints
# =============================================
@app.get("/")
def index():
    return FileResponse("index.html")


@app.get("/send-report")
async def send_report_manually(
    email: str = "koenmiddelhof@hotmail.com",
    client_id: str = "interaict",
    days: int = 30
):
    """
    Handmatig rapport versturen — voor testen.
    Gebruik: /send-report?email=jouw@mail.nl&client_id=interaict&days=30
    """
    result = await generate_and_send_report(
        client_id=client_id,
        to_email=email,
        days=days
    )
    return JSONResponse(result)


# =============================================
# Supabase logging
# =============================================
async def log_to_supabase(client_id: str, session_id: str, question: str, answer: str):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/chat_logs",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                },
                json={
                    "client_id": client_id,
                    "session_id": session_id,
                    "question": question,
                    "answer": answer
                }
            )
    except Exception as e:
        print(f"Supabase logging error: {e}")


# =============================================
# System prompt — Interaict
# =============================================
SYSTEM_PROMPT = """
Je bent de digitale assistent van Interaict.
Interaict is een onafhankelijk B2B-bedrijf gevestigd in Tilburg dat bedrijven verbindt met de juiste AI-softwareleverancier.

Je bent:
- professioneel en zakelijk
- helder en to-the-point
- behulpzaam en betrouwbaar
- nooit opdringerig

Je helpt bezoekers met vragen over:
- Wat Interaict doet en hoe het matchingproces werkt
- Diensten voor eindgebruikers en softwareleveranciers
- Kennismaking plannen
- Contact opnemen met Jeroen of Maxim

Je verzint nooit informatie. Als je iets niet weet verwijs je naar:
- jeroen@interaict.nl of +31 6 4021 0516
- maxim@interaict.nl of +31 6 3648 4773
"""

INTERAICT_KENNIS = """
Bedrijfsnaam: Interaict
Slogan: Onafhankelijk, helder en resultaatgericht
Type: B2B matchmaker tussen AI-softwareleveranciers en eindgebruikers
Locatie: Tilburg, Noord-Brabant

Oprichters / Team:
- Jeroen van de Sande: jeroen@interaict.nl | +31 6 4021 0516
- Maxim Fontanel: maxim@interaict.nl | +31 6 3648 4773

Wat Interaict doet:
- Helpt eindgebruikers (bedrijven) bij het vinden van de juiste AI-software
- Helpt softwareleveranciers bij het bereiken van besluitvormers in het MKB
- Werkt in 3 fases: Behoefte identificeren → Oplossing selecteren → Succesvolle match

Diensten voor eindgebruikers:
- AI-softwareselectie op maat
- Evaluatie van leveranciers
- Strategische matching
- Begeleide introducties

Diensten voor softwareleveranciers:
- Gekwalificeerde leadgeneratie
- Toegang tot besluitvormers
- Marktpositionering
- Gestructureerde introducties

Sectoren: Zakelijke dienstverlening, Transport, Overheid, Productie, Metaal & Techniek,
Gezondheidszorg, Financiële dienstverlening, Energie, Detailhandel, Bouw, Agrarisch, Horeca

Website: interaict.nl
Chatbot powered by AI-Migo (ai-migo.nl)
"""


# =============================================
# Chat endpoint
# =============================================
@app.get("/chat")
async def chat(message: str, session_id: str, client_id: str = "interaict"):
    try:
        if session_id not in chat_memory:
            chat_memory[session_id] = []

        chat_memory[session_id].append(
            {"role": "user", "content": message}
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": INTERAICT_KENNIS}
        ] + chat_memory[session_id]

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=200
        )

        answer = response["choices"][0]["message"]["content"]

        chat_memory[session_id].append(
            {"role": "assistant", "content": answer}
        )

        await log_to_supabase(
            client_id=client_id,
            session_id=session_id,
            question=message,
            answer=answer
        )

        return {"response": answer}

    except Exception as e:
        return {"response": "Er ging iets mis: " + str(e)}