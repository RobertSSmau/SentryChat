from flask import Flask, request, jsonify, render_template
import os
import re
from dotenv import load_dotenv
from openai import OpenAI
from flask_cors import CORS
import requests
import json

app = Flask(__name__, template_folder="templates")
CORS(app)  # abilita CORS su tutte le rotte

# Carica variabili d'ambiente da .env
load_dotenv()

# Inizializza client OpenAI con Groq endpoint
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

@app.route("/check-spam", methods=["POST"])
def check_spam():
    data = request.get_json()
    subject = data.get("subject", "")
    body = data.get("body", "")

    if not subject and not body:
        return jsonify({"error": "Subject o body mancanti"}), 400

    result = check_email_spam(subject, body)

    if result is None:
        return jsonify({"error": "Errore durante la verifica spam"}), 500

    return jsonify(result)

def check_phone_abstract(phone_number):
    api_key = os.getenv("ABSTRACT_API_KEY_PHONE")
    url = "https://phonevalidation.abstractapi.com/v1/"
    params = {
        "api_key": api_key,
        "phone": phone_number
    }

    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print("Errore Phone Validation:", response.status_code, response.text)
            return None
    except Exception as e:
        print("Errore durante richiesta Phone Validation:", str(e))
        return None

def formatta_phone_con_llm(phone_json):
    SYSTEM_PROMPT = """
Sei un assistente esperto di sicurezza digitale.

Riceverai una risposta tecnica da un'API che analizza un numero di telefono.

Fornisci una breve spiegazione per l’utente:  
– Il numero è valido?  
– A quale paese appartiene?  
– È un numero mobile o fisso?  
– L'operatore telefonico è noto?

Scrivi in modo semplice, diretto, senza usare codice o elenchi puntati.
"""

    try:
        prompt = f"Ecco i dati ricevuti dall'API:\n\n{json.dumps(phone_json, indent=2)}"

        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        print("Errore LLM Phone:", e)
        return "Errore durante la formattazione della risposta."

@app.route("/check-phone-llm", methods=["POST"])
def check_phone_llm():
    data = request.get_json()
    phone_number = data.get("phone", "")

    if not phone_number:
        return jsonify({"error": "Numero di telefono mancante"}), 400

    # Chiamata all'API Abstract
    validation = check_phone_abstract(phone_number)

    if validation is None:
        return jsonify({"error": "Errore durante la verifica"}), 500

    # Spiegazione naturale con LLM
    spiegazione = formatta_phone_con_llm(validation)

    return jsonify({
        "raw": validation,
        "spiegazione": spiegazione
    })

def formatta_reputation_con_llm(email_reputation_json):
    SYSTEM_PROMPT = """
Sei un assistente di sicurezza informatica.

Riceverai una risposta tecnica da un'API che valuta la reputazione di un indirizzo email.

La tua risposta deve essere scritta in linguaggio naturale, adatta a un utente non esperto.  
Spiega se l'email è sicura, compromessa, o sospetta.  
Non usare codice, non scrivere "json", non formattare in markdown.  
Non servono elenchi puntati. Dai una risposta fluida, breve, chiara e rassicurante (o allarmante se serve).
"""

    try:
        prompt = f"Ecco i dati ricevuti dall'API:\n\n{json.dumps(email_reputation_json, indent=2)}"

        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )

        return response.choices[0].message.content

    except Exception as e:
        print("Errore LLM:", e)
        return "Errore durante la formattazione della risposta."

@app.route("/email-reputation-llm", methods=["POST"])
def email_reputation_llm():
    data = request.get_json()
    email = data.get("email", "")

    if not email:
        return jsonify({"error": "Email mancante"}), 400

    reputation_raw = check_email_reputation(email)

    if reputation_raw is None:
        return jsonify({"error": "Errore durante la verifica"}), 500

    spiegazione = formatta_reputation_con_llm(reputation_raw)

    return jsonify({
        "raw": reputation_raw,
        "spiegazione": spiegazione
    })

def sintesi_email_reputation(data):
    return {
        "email": data.get("email_address"),
        "valid_format": data["email_deliverability"]["is_format_valid"],
        "smtp_valid": data["email_deliverability"]["is_smtp_valid"],
        "catchall": data["email_quality"]["is_catchall"],
        "disposable": data["email_quality"]["is_disposable"],
        "free_email": data["email_quality"]["is_free_email"],
        "domain_risk": data["email_risk"]["domain_risk_status"],
        "score": data["email_quality"]["score"],
        "provider": data["email_sender"]["email_provider_name"]
    }

def analizza_con_llm(reputation_data, spam_data):
    SYSTEM_PROMPT = """
Agisci come un analista di sicurezza informatica.

Riceverai l'analisi tecnica di un indirizzo email (reputation) e del contenuto di un messaggio (spam detection).

Fornisci un'unica risposta riassuntiva in linguaggio naturale, chiara, e con un consiglio pratico per l’utente. Non usare markdown, non scrivere righe vuote.
"""

    prompt = f"""
Dati Reputation Email:
- Formato valido: {reputation_data.get('valid_format')}
- SMTP valido: {reputation_data.get('smtp_valid')}
- Catch-all: {reputation_data.get('catchall')}
- Disposable: {reputation_data.get('disposable')}
- Dominio rischioso: {reputation_data.get('domain_risk')}
- Provider: {reputation_data.get('provider')}
- Score reputazione: {reputation_data.get('score')}

Dati Spam Detection:
{spam_data}
"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

    except Exception as e:
        print("Errore LLM:", e)
        return "Errore durante l'elaborazione della risposta."

def check_email_reputation(email):
    api_key = os.getenv("ABSTRACT_API_KEY")
    url = "https://emailreputation.abstractapi.com/v1/"
    params = {
        "api_key": api_key,
        "email": email
    }

    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print("Errore Email Reputation:", response.status_code, response.text)
            return None
    except Exception as e:
        print("Errore durante richiesta Email Reputation:", str(e))
        return None
    
def check_email_spam(subject, body):
    api_key = os.getenv("ABSTRACT_API_KEY")
    url = "https://email-spam-detection.abstractapi.com/v1/"
    params = {
        "api_key": api_key,
        "subject": subject,
        "body": body
    }

    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print("Errore Spam Detection:", response.status_code, response.text)
            return None
    except Exception as e:
        print("Errore durante richiesta Spam Detection:", str(e))
        return None

def search_intelx(term):
    url = "https://free.intelx.io/phonebook/search"
    headers = {
        "x-key": os.getenv("INTELX_API_KEY"),
        "Content-Type": "application/json",
        "User-Agent": "SentryChatBot"
    }
    data = {
        "term": term,
        "maxresults": 5,
        "media": 0,
        "target": 1
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            return {"status": "ok", "records": response.json().get("records", [])}
        elif response.status_code == 429:
            return {"status": "error", "message": "Limite giornaliero superato."}
        else:
            return {"status": "error", "code": response.status_code, "message": response.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.route("/intelx-search", methods=["POST"])
def intelx_search():
    data = request.get_json()
    email = data.get("email", "")

    if not email:
        return jsonify({"error": "Email mancante"}), 400

    result = search_intelx(email)
    return jsonify(result)

@app.route("/chat", methods=["POST"])
def chat():
    # Preprompt per contestualizzare il chatbot
    SYSTEM_PROMPT = """Assumi il ruolo di un esperto di sicurezza informatica. Rispondi in modo semplice, diretto e professionale.
      Le spiegazioni devono essere brevi e comprensibili anche per chi ha poca esperienza tecnica. Limita la risposta a massimo 6 righe.
        Evita elenchi puntati, simboli grafici o formattazioni speciali. Usa solo testo semplice."""

    data = request.get_json()
    user_message = data.get("message", "")

    if not user_message:
        return jsonify({"error": "Messaggio mancante"}), 400

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ]
        )
        reply = response.choices[0].message.content
        return jsonify({"response": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/check-email", methods=["POST"])
def check_email_text():
    data = request.get_json()
    email_text = data.get("email", "")

    if not email_text:
        return jsonify({"error": "Testo email mancante"}), 400

    # Controlla se contiene link sospetti (http, https o www)
    if not re.search(r'(https?://|www\.)[^\s]+', email_text):
        return jsonify({"response": "Non sembra contenere link. Nessun rischio evidente."})

    system_prompt = """Sei un classificatore esperto di email sospette.

Analizza il contenuto del messaggio e:
1. Indica se si tratta di Phishing o Non phishing.
2. Dai un motivo breve.
3. Se è presente un link, valuta se il dominio è affidabile (es. amazon.com, google.com) o sospetto.

Rispondi esattamente con:

Classificazione: [Phishing / Non phishing]  
Motivo: ...  
Dominio: [Affidabile / Sospetto / Nessun link]
"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": email_text}
            ]
        )
        reply = response.choices[0].message.content
        return jsonify({"response": reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/check-password", methods=["POST"])
def check_password():
    data = request.get_json()
    password = data.get("password", "")

    if not password:
        return jsonify({"error": "Password mancante"}), 400

    PASSWORD_PROMPT = f"""Sei un esperto di cybersecurity.

Analizza la seguente password: "{password}"

Devi restituire esattamente e solo 4 righe nel formato seguente:

Valutazione: [Debole / Media / Forte]  
Memorizzabile: [Sì / No]  
Suggerimenti: [massimo 1 frase]  
Password suggerita: [una password sicura ma memorizzabile]

NON aggiungere commenti, spiegazioni, paragrafi o motivazioni.  
Rispondi solo con 4 righe, chiare e nel formato indicato.

Esempio:
Valutazione: Debole  
Memorizzabile: Sì  
Suggerimenti: Aggiungi lettere maiuscole e simboli speciali.  
Password suggerita: Sole$Giallo2024
"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "user", "content": PASSWORD_PROMPT}
            ]
        )
        return jsonify({"response": response.choices[0].message.content})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/analyze-threat", methods=["POST"])
def analyze_threat():
    data = request.get_json()
    threat_name = data.get("input", "")

    if not threat_name:
        return jsonify({"error": "Nome della minaccia mancante"}), 400

    prompt = f"""Agisci come un esperto in sicurezza informatica.

Analizza la seguente minaccia identificata da un antivirus o malware scanner:

\"{threat_name}\"

Se il nome è inventato o non riconosciuto, dichiara che non hai informazioni affidabili.  
Non inventare, non usare markdown, non scrivere introduzioni o asterischi.

Rispondi SOLO in questo formato:

Descrizione: ...  
Target: ...  
Pericolosità: ...
"""


    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return jsonify({"response": response.choices[0].message.content})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def home():
    return render_template("index.html")

# Avvio locale
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)

