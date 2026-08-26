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

Se compara contra el cierre REGULAR (no el postmarket) para
capturar el movimiento COMPLETO desde antes de una noticia/balance,
incluyendo todo lo que se movio en el afterhours de ayer. Si se
comparara contra el postmarket de ayer, una suba fuerte por balance
publicado ayer despues del cierre ya estaria "absorbida" en la base
de comparacion y el % mostraria un numero mucho mas chico del real.

Condicion de alerta (las DOS deben cumplirse):
  1) El precio de pre-mercado de hoy sube 3.5% o mas vs. el cierre
     regular de ayer
  2) El volumen de pre-mercado de hoy es 3x o mas el volumen del
     postmarket de ayer (se mantiene esta base de volumen porque
     son sesiones de tipo similar - ambas fuera de horario regular)

Manda UN SOLO mail con todos los tickers que cumplen la condicion.

NOTA: los datos intradia de yfinance (prepost=True) no siempre estan
disponibles para todos los tickers, y para las acciones menos
liquidas puede no haber operaciones registradas en esas franjas
horarias. En esos casos el ticker se saltea (no es un error).
"""

import os
import sys
import smtplib
import datetime
from email.mime.text import MIMEText
import yfinance as yf

# Forzar que cada print() se escriba al instante (sin buffer), para que
# el log de GitHub Actions muestre TODAS las lineas y no se pierdan
# por el buffering normal de Python cuando no corre en una terminal.
sys.stdout.reconfigure(line_buffering=True)

# ---------------------------------------------------------------
# CONFIGURACION
# ---------------------------------------------------------------
UMBRAL_PORCENTAJE = 3.5      # % minimo de suba: premarket hoy vs cierre regular ayer
UMBRAL_VOLUMEN = 3.0         # veces el volumen del postmarket de ayer

TEST_MODE = False            # True = manda mail de prueba aunque no haya matches

ZONA_NY = "America/New_York"

# Misma lista de ~100 tickers importantes de EEUU con CEDEAR en BYMA
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

# ---------------------------------------------------------------
# CREDENCIALES (GitHub Secrets - mismas que el otro script)
# ---------------------------------------------------------------
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
    """Compara premarket de hoy vs cierre REGULAR de ayer. Devuelve dict o None."""
    try:
        t = yf.Ticker(ticker)
        # 5 dias de datos en velas de 5 minutos, incluyendo pre/post mercado
        data = t.history(period="5d", interval="5m", prepost=True)
        if data.empty:
            print(f"{ticker}: sin datos intradia disponibles")
            return None

        data.index = data.index.tz_convert(ZONA_NY)
        hoy = datetime.datetime.now(datetime.timezone.utc).astimezone(
            __import__("zoneinfo").ZoneInfo(ZONA_NY)
        ).date()

        dias_disponibles = sorted(set(data.index.date))
        dias_anteriores = [d for d in dias_disponibles if d < hoy]
        if not dias_anteriores:
            print(f"{ticker}: no hay dia anterior con datos")
            return None
        dia_anterior = dias_anteriores[-1]

        df_ayer = data[data.index.date == dia_anterior]

        # Cierre REGULAR de ayer: ultima vela de la rueda normal (antes de las 16:00 NY)
        regular_ayer = df_ayer.between_time("09:30", "16:00")
        if regular_ayer.empty:
            print(f"{ticker}: sin datos de rueda regular de ayer")
            return None
        cierre_regular_ayer = float(regular_ayer["Close"].iloc[-1])

        # Postmarket de ayer: 16:00 a 20:00 hs NY (se usa solo para el volumen base)
        post_ayer = df_ayer.between_time("16:00", "20:00")
        if post_ayer.empty:
            print(f"{ticker}: sin operaciones en postmarket de ayer")
            return None
        volumen_post_ayer = float(post_ayer["Volume"].sum())

        # Premarket de hoy: 04:00 a 09:30 hs NY
        df_hoy = data[data.index.date == hoy]
        pre_hoy = df_hoy.between_time("04:00", "09:30")
        if pre_hoy.empty:
            print(f"{ticker}: sin operaciones en premarket de hoy (todavia)")
            return None
        precio_pre_hoy = float(pre_hoy["Close"].iloc[-1])
        volumen_pre_hoy = float(pre_hoy["Volume"].sum())

        if cierre_regular_ayer == 0 or volumen_post_ayer == 0:
            return None

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
            }

        print(f"{ticker}: sin match (+{variacion_pct:.1f}%, vol x{ratio_volumen:.1f})")
        return None
    except Exception as e:
        print(f"Error con {ticker}: {e}")
        return None


def main():
    encontrados = []

    print(f"Empezando a chequear {len(TICKERS)} tickers...")

    for i, ticker in enumerate(TICKERS, start=1):
        print(f"[{i}/{len(TICKERS)}] Chequeando {ticker}...")
        resultado = chequear_ticker(ticker)
        if resultado:
            encontrados.append(resultado)
            print(f"MATCH: {ticker} +{resultado['variacion_pct']:.1f}% vol x{resultado['ratio_volumen']:.1f}")

    if not encontrados:
        print("Ninguna accion cumplio la condicion hoy.")
        if TEST_MODE:
            enviar_mail(
                "🧪 Test - Alerta Pre-Mercado (sin matches)",
                "Mail de prueba (TEST_MODE = True). El script corrio bien pero "
                "ninguna accion cumplio la condicion hoy."
            )
        return

    encontrados.sort(key=lambda x: x["variacion_pct"], reverse=True)

    lineas = []
    for r in encontrados:
        lineas.append(
            f"{r['ticker']}: cierre regular ayer USD {r['cierre_regular_ayer']:.2f} -> "
            f"pre-mercado hoy USD {r['precio_pre_hoy']:.2f}  |  +{r['variacion_pct']:.1f}%  |  "
            f"Volumen x{r['ratio_volumen']:.1f} del postmarket de ayer"
        )

    cuerpo = (
        "Acciones que subieron {}% o mas del cierre regular de ayer al pre-mercado de hoy, "
        "con volumen {}x o mas el del post-mercado de ayer:\n\n".format(
            UMBRAL_PORCENTAJE, UMBRAL_VOLUMEN
        )
        + "\n".join(lineas)
    )

    asunto = f"🌅 Pre-Mercado - {len(encontrados)} accion(es) detectada(s)"
    enviar_mail(asunto, cuerpo)


if __name__ == "__main__":
    main()
