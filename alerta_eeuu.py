"""
Alerta de precios - Acciones de EEUU con CEDEAR en BYMA
---------------------------------------------------------
Chequea el precio REAL en dolares (no el CEDEAR) de acciones que
tienen CEDEAR negociable en BYMA, y manda un mail cuando el precio
cruza el nivel que configures.

No necesita ninguna API key para los precios (usa yfinance, gratis).
Solo necesita credenciales de Gmail para poder enviar el mail.
"""

import os
import smtplib
from email.mime.text import MIMEText
import yfinance as yf

# ---------------------------------------------------------------
# 1) CONFIGURA ACA TUS ALERTAS
#    ticker: simbolo tal cual cotiza en EEUU (no el de BYMA)
#    "arriba": te avisa si el precio sube por encima de ese valor
#    "abajo": te avisa si el precio baja por debajo de ese valor
#    (podes dejar solo uno de los dos, o los dos)
# ---------------------------------------------------------------
ALERTAS = {
    "NVDA": {"arriba": 230.0, "abajo": 200.0},
    "AMD":  {"arriba": 200.0, "abajo": 160.0},
    "MELI": {"arriba": None,  "abajo": 1800.0},
    "PLTR": {"arriba": 190.0, "abajo": None},
    # Agrega mas tickers aca. Ejemplos de otros con CEDEAR en BYMA:
    # "AAPL", "MSFT", "TSLA", "JD", "BABA", "MRVL", "CRM", "CRWD",
    # "PDD", "XPEV", "HD", "TGT", "DE", "KO", "GOOGL", "AMZN"
}

# ---------------------------------------------------------------
# 2) CREDENCIALES (se leen de GitHub Secrets / variables de entorno,
#    NUNCA las escribas hardcodeadas aca)
# ---------------------------------------------------------------
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
TO_EMAIL = os.environ.get("TO_EMAIL", GMAIL_USER)


def obtener_precio(ticker: str) -> float | None:
    """Devuelve el ultimo precio disponible del ticker, o None si falla."""
    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        if data.empty:
            return None
        return float(data["Close"].iloc[-1])
    except Exception as e:
        print(f"Error obteniendo precio de {ticker}: {e}")
        return None


def enviar_mail(asunto: str, cuerpo: str):
    msg = MIMEText(cuerpo)
    msg["Subject"] = asunto
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, [TO_EMAIL], msg.as_string())
    print(f"Mail enviado: {asunto}")


def main():
    for ticker, niveles in ALERTAS.items():
        precio = obtener_precio(ticker)
        if precio is None:
            print(f"{ticker}: no se pudo obtener el precio")
            continue

        print(f"{ticker}: USD {precio:.2f}")

        nivel_arriba = niveles.get("arriba")
        nivel_abajo = niveles.get("abajo")

        if nivel_arriba is not None and precio >= nivel_arriba:
            enviar_mail(
                f"🔔 {ticker} superó los USD {nivel_arriba}",
                f"{ticker} está en USD {precio:.2f} (nivel configurado: {nivel_arriba})."
            )

        if nivel_abajo is not None and precio <= nivel_abajo:
            enviar_mail(
                f"🔔 {ticker} cayó por debajo de USD {nivel_abajo}",
                f"{ticker} está en USD {precio:.2f} (nivel configurado: {nivel_abajo})."
            )


if __name__ == "__main__":
    main()
