"""
Alerta Pre-Mercado vs Cierre Regular del dia anterior
--------------------------------------------------------------------
Corre UNA SOLA VEZ por dia, a las 10:00 hs Argentina (antes de que
abra el mercado regular de EEUU a las 10:30 hs ART).

Compara:
  - El PRE-MERCADO de HOY (04:00 a 09:30 hs de Nueva York)
  contra
  - El CIERRE DEL MERCADO REGULAR del DIA ANTERIOR (la ultima vela
    de la rueda normal, ANTES de cualquier reaccion de postmarket
    por balances u otras noticias)

Condicion de alerta (las DOS deben cumplirse):
  1) El precio de pre-mercado de hoy sube 3.5% o mas vs. el cierre
     regular de ayer
  2) El volumen de pre-mercado de hoy es 3x o mas el volumen del
     postmarket de ayer

Manda UN SOLO mail con todos los tickers que cumplen la condicion.

Esta version SIEMPRE imprime un resultado por cada ticker (motivo
del descarte incluido), para poder diagnosticar bien cualquier caso.
"""

import os
import sys
import smtplib
import datetime
from email.mime.text import MIMEText
import yfinance as yf

sys.stdout.reconfigure(line_buffering=True)

# ---------------------------------------------------------------
# CONFIGURACION
# ---------------------------------------------------------------
UMBRAL_PORCENTAJE = 3.5
UMBRAL_VOLUMEN = 3.0
TEST_MODE = False
ZONA_NY = "America/New_York"

TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "NFLX",
    "ORCL", "ADBE", "CRM", "INTC", "AMD", "QCOM", "TXN", "AVGO",
    "CSCO", "IBM", "MU", "AMAT", "LRCX", "MRVL", "ON", "PANW",
    "PLTR", "SNOW", "CRWD", "ZM", "UBER", "ABNB", "SHOP", "SPOT",
    "SNAP", "PINS", "COIN", "RIOT", "MARA", "IONQ", "RGTI", "ASTS",
    "HIMS", "NBIS", "CRWV",
    "WMT", "COST", "TGT", "HD", "LOW", "MCD", "SBUX", "NKE", "DIS",
    "KO", "PEP", "PG", "KMB", "EL",
    "JPM", "BAC", "WFC", "C", "GS", "MS", "V", "MA", "PYPL", "AXP",
    "BLK", "SCHW",
    "JNJ", "PFE", "MRK", "ABBV", "UNH", "LLY", "BMY", "GILD", "AMGN",
    "CVS", "MDT", "ABT",
    "BA", "CAT", "DE", "GE", "HON", "MMM", "UPS", "RTX", "LMT", "GD",
    "UNP",
    "XOM", "CVX", "COP", "OXY", "SLB", "PSX",
    "T", "VZ", "TMUS",
    "F", "GM",
    "BABA", "JD", "PDD", "BIDU", "NTES", "XPEV", "LI",
    "TSM", "ASML",
    "FCX", "NEM", "GOLD", "PAAS",
    "MELI",
]

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
TO_EMAIL = os.environ.get("TO_EMAIL", GMAIL_USER)


def enviar_mail(asunto: str, cuerpo: str):
    msg = MIMEText(cuerpo)
    msg["Subject"] = asunto
    msg["From"] = GMAIL_USER
    msg["To"] = TO_EMAIL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, [TO_EMAIL], msg.as_string())
    print(f"Mail enviado: {asunto}")


def chequear_ticker(ticker: str):
    """
    Devuelve SIEMPRE una tupla (resultado, motivo):
      - resultado: dict si cumple la condicion, si no None
      - motivo: string explicando el resultado (para loguear en main)
    """
    try:
        t = yf.Ticker(ticker)
        data = t.history(period="5d", interval="5m", prepost=True)
        if data.empty:
            return None, "sin datos intradia disponibles"

        if data.index.tz is None:
            data.index = data.index.tz_localize("UTC")
        data.index = data.index.tz_convert(ZONA_NY)

        hoy = datetime.datetime.now(datetime.timezone.utc).astimezone(
            __import__("zoneinfo").ZoneInfo(ZONA_NY)
        ).date()

        dias_disponibles = sorted(set(data.index.date))
        dias_anteriores = [d for d in dias_disponibles if d < hoy]
        if not dias_anteriores:
            return None, f"no hay dia anterior con datos (dias disponibles: {dias_disponibles})"
        dia_anterior = dias_anteriores[-1]

        df_ayer = data[data.index.date == dia_anterior]

        regular_ayer = df_ayer.between_time("09:30", "16:00")
        if regular_ayer.empty:
            return None, f"sin datos de rueda regular de {dia_anterior}"
        cierre_regular_ayer = float(regular_ayer["Close"].iloc[-1])

        post_ayer = df_ayer.between_time("16:00", "20:00")
        if post_ayer.empty:
            return None, f"sin operaciones en postmarket de {dia_anterior}"
        volumen_post_ayer = float(post_ayer["Volume"].sum())

        df_hoy = data[data.index.date == hoy]
        pre_hoy = df_hoy.between_time("04:00", "09:30")
        if pre_hoy.empty:
            return None, "sin operaciones en premarket de hoy (todavia)"
        precio_pre_hoy = float(pre_hoy["Close"].iloc[-1])
        volumen_pre_hoy = float(pre_hoy["Volume"].sum())

        if cierre_regular_ayer == 0 or volumen_post_ayer == 0:
            return None, "cierre o volumen base en cero, no se puede calcular"

        variacion_pct = (precio_pre_hoy - cierre_regular_ayer) / cierre_regular_ayer * 100
        ratio_volumen = volumen_pre_hoy / volumen_post_ayer
        cumple = (variacion_pct >= UMBRAL_PORCENTAJE) and (ratio_volumen >= UMBRAL_VOLUMEN)

        if cumple:
            return {
                "ticker": ticker,
                "precio_pre_hoy": precio_pre_hoy,
                "cierre_regular_ayer": cierre_regular_ayer,
                "variacion_pct": variacion_pct,
                "ratio_volumen": ratio_volumen,
            }, f"MATCH +{variacion_pct:.1f}% vol x{ratio_volumen:.1f}"

        return None, f"sin match (+{variacion_pct:.1f}%, vol x{ratio_volumen:.1f})"

    except Exception as e:
        return None, f"ERROR: {type(e).__name__}: {e}"


def main():
    encontrados = []
    print(f"Empezando a chequear {len(TICKERS)} tickers...")

    for i, ticker in enumerate(TICKERS, start=1):
        resultado, motivo = chequear_ticker(ticker)
        print(f"[{i}/{len(TICKERS)}] {ticker}: {motivo}")
        if resultado:
            encontrados.append(resultado)

    if not encontrados:
        print("Ninguna accion cumplio la condicion hoy.")
        if TEST_MODE:
            enviar_mail(
                "🧪 Test - Alerta Pre-Mercado (sin matches)",
                "Mail de prueba. El script corrio bien pero ninguna accion cumplio la condicion hoy."
            )
        return

    encontrados.sort(key=lambda x: x["variacion_pct"], reverse=True)
    lineas = [
        f"{r['ticker']}: cierre regular ayer USD {r['cierre_regular_ayer']:.2f} -> "
        f"pre-mercado hoy USD {r['precio_pre_hoy']:.2f}  |  +{r['variacion_pct']:.1f}%  |  "
        f"Volumen x{r['ratio_volumen']:.1f} del postmarket de ayer"
        for r in encontrados
    ]
    cuerpo = (
        "Acciones que subieron {}% o mas del cierre regular de ayer al pre-mercado de hoy, "
        "con volumen {}x o mas el del post-mercado de ayer:\n\n".format(UMBRAL_PORCENTAJE, UMBRAL_VOLUMEN)
        + "\n".join(lineas)
    )
    asunto = f"🌅 Pre-Mercado - {len(encontrados)} accion(es) detectada(s)"
    enviar_mail(asunto, cuerpo)


if __name__ == "__main__":
    main()
