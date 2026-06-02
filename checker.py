import json
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

import yfinance as yf

# ── Credenciales desde secrets de GitHub ──────────────────────────────────────
SENDER_EMAIL   = os.environ["GMAIL_USER"]
SENDER_PASS    = os.environ["GMAIL_APP_PASS"]
RECEIVER_EMAIL = os.environ["RECEIVER_EMAIL"]

# ── Hora actual (para el log) ──────────────────────────────────────────────────
ahora = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
print(f"\n=== Chequeo BYMA — {ahora} ===\n")

# ── Cargar alarmas ─────────────────────────────────────────────────────────────
with open("alarmas.json", encoding="utf-8") as f:
    alarmas = json.load(f)

if not alarmas:
    print("No hay alarmas cargadas en alarmas.json.")
    exit(0)

# ── Obtener precios (una sola llamada por ticker) ──────────────────────────────
tickers_unicos = list(set(a["ticker"] for a in alarmas))
precios = {}

for t in tickers_unicos:
    try:
        data = yf.Ticker(t).history(period="1d", interval="1m")
        if not data.empty:
            precios[t] = float(data["Close"].iloc[-1])
        else:
            # fallback a fast_info si no hay datos intradía (fuera de horario)
            precios[t] = float(yf.Ticker(t).fast_info["lastPrice"])
        print(f"  {t}: ${precios[t]:,.2f}")
    except Exception as e:
        precios[t] = None
        print(f"  {t}: ERROR — {e}")

# ── Función para enviar mail por Gmail SMTP ────────────────────────────────────
def enviar_mail(ticker, tipo, precio_act, precio_obj, nota):
    simbolo = "≥" if tipo == "MAYOR" else "≤"
    asunto  = f"⚠️ ALERTA BYMA: {ticker} ({nota})"
    cuerpo  = (
        f"Tu alarma se activó:\n\n"
        f"  Activo    : {ticker}\n"
        f"  Condición : precio {simbolo} ${precio_obj:,.2f}\n"
        f"  Precio    : ${precio_act:,.2f}\n"
        f"  Nota      : {nota}\n\n"
        f"  Hora      : {ahora}\n"
    )
    msg            = MIMEText(cuerpo, "plain", "utf-8")
    msg["Subject"] = asunto
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECEIVER_EMAIL

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASS)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

# ── Chequear cada alarma ───────────────────────────────────────────────────────
print()
alertas_enviadas = 0

for a in alarmas:
    ticker = a["ticker"]
    tipo   = a["tipo"]
    precio = a["precio"]
    nota   = a.get("nota", "")
    px     = precios.get(ticker)

    if px is None:
        print(f"  ⏭  {ticker}: sin precio, se omite.")
        continue

    cumple = (tipo == "MAYOR" and px >= precio) or \
             (tipo == "MENOR" and px <= precio)

    if cumple:
        try:
            enviar_mail(ticker, tipo, px, precio, nota)
            simbolo = "≥" if tipo == "MAYOR" else "≤"
            print(f"  ✅ ALERTA enviada: {ticker} @ ${px:,.2f} ({simbolo} ${precio:,.2f}) — {nota}")
            alertas_enviadas += 1
        except Exception as e:
            print(f"  ❌ Error enviando mail para {ticker}: {e}")
    else:
        simbolo = "≥" if tipo == "MAYOR" else "≤"
        diff    = ((px - precio) / precio) * 100
        print(f"  ⏳ {ticker}: ${px:,.2f} | objetivo {simbolo} ${precio:,.2f} | distancia {diff:+.1f}%")

print(f"\n=== Fin del chequeo — {alertas_enviadas} alerta(s) enviada(s) ===\n")
