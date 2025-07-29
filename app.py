from flask import Flask, request, jsonify
import os
import re
from dotenv import load_dotenv
from openai import OpenAI

# Carica variabili d'ambiente da .env
load_dotenv()

# Inizializza client OpenAI con Groq endpoint
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# Configurazione Flask
app = Flask(__name__)

# Preprompt per contestualizzare il chatbot
SYSTEM_PROMPT = """Sei un analizzatore esperto di sicurezza informatica. 
Riceverai in input il contenuto di un messaggio e-mail. 
Il tuo compito è:
1. Determinare se il messaggio è sospetto o può essere un attacco di phishing (rispondi solo con "Phishing" o "Non phishing").
2. Dare una breve spiegazione (massimo 2 frasi) del perché hai classificato il messaggio in quel modo.

Formatta la risposta così:
Classificazione: [Phishing / Non phishing]
Motivo: ..."""

@app.route("/chat", methods=["POST"])
def chat():
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

"{threat_name}"

Restituisci solo le seguenti informazioni, senza introduzioni, saluti o commenti extra.

Descrizione: (massimo 2 frasi, tono semplice e chiaro)  
Target: (es. Windows, macOS, multipiattaforma)  
Pericolosità: (Alta / Media / Bassa / Falso positivo probabile)

Rispondi esattamente in questo formato:

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


# Avvio locale
if __name__ == "__main__":
    app.run(debug=True)

