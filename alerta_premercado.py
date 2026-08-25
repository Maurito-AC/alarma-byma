"""
Alerta Pre-Mercado vs Post-Mercado del dia anterior
--------------------------------------------------------------------
Corre UNA SOLA VEZ por dia, a las 10:00 hs Argentina (antes de que
abra el mercado regular de EEUU a las 10:30 hs ART).

Compara:
  - El PRE-MERCADO de HOY (04:00 a 09:30 hs de Nueva York)
  contra
  - El POST-MERCADO (after-hours) del DIA ANTERIOR (16:00 a 20:00
    hs de Nueva York)

Condicion de alerta (las DOS deben cumplirse):
  1) El precio sube 3.5% o mas entre esas dos sesiones
  2) El volumen de pre-mercado de hoy es 3x o mas el volumen que
     hubo en el post-mercado de ayer

Manda UN SOLO mail con todos los tickers que cumplen la condicion.

NOTA: los datos intradia de yfinance (prepost=True) no siempre estan
disponibles para todos los tickers, y para las acciones menos
liquidas puede no haber operaciones registradas en esas franjas
horarias. En esos casos el ticker se saltea (no es un error).
"""

import os
import smtplib
import datetime
from email.mime.text import MIMEText
import yfinance as yf

# ---------------------------------------------------------------
# CONFIGURACION
# ---------------------------------------------------------------
UMBRAL_PORCENTAJE = 3.5      # % minimo de suba entre postmarket ayer y premarket hoy
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
    """Compara premarket de hoy vs postmarket de ayer. Devuelve dict o None."""
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

        # Postmarket de ayer: 16:00 a 20:00 hs NY
        df_ayer = data[data.index.date == dia_anterior]
        post_ayer = df_ayer.between_time("16:00", "20:00")
        if post_ayer.empty:
            print(f"{ticker}: sin operaciones en postmarket de ayer")
            return None
        precio_post_ayer = float(post_ayer["Close"].iloc[-1])
        volumen_post_ayer = float(post_ayer["Volume"].sum())

        # Premarket de hoy: 04:00 a 09:30 hs NY
        df_hoy = data[data.index.date == hoy]
        pre_hoy = df_hoy.between_time("04:00", "09:30")
        if pre_hoy.empty:
            print(f"{ticker}: sin operaciones en premarket de hoy (todavia)")
            return None
        precio_pre_hoy = float(pre_hoy["Close"].iloc[-1])
        volumen_pre_hoy = float(pre_hoy["Volume"].sum())

        if precio_post_ayer == 0 or volumen_post_ayer == 0:
            return None

        variacion_pct = (precio_pre_hoy - precio_post_ayer) / precio_post_ayer * 100
        ratio_volumen = volumen_pre_hoy / volumen_post_ayer

        cumple = (variacion_pct >= UMBRAL_PORCENTAJE) and (ratio_volumen >= UMBRAL_VOLUMEN)

        if cumple:
            return {
                "ticker": ticker,
                "precio_pre_hoy": precio_pre_hoy,
                "precio_post_ayer": precio_post_ayer,
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

    for ticker in TICKERS:
        resultado = chequear_ticker(ticker)
        if resultado:
            encontrados.append(resultado)
            print(f"MATCH: {ticker} +{resultado['variacion_pct']:.1f}% vol x{resultado['ratio_volumen']:.1f}")

    if not encontrados:
        print("Ninguna accion cumplio la condicion hoy.")
        if TEST_MODE:
            enviar_mail(
                "🧪 Test - Alerta Pre-Mercado vs Post-Mercado (sin matches)",
                "Mail de prueba (TEST_MODE = True). El script corrio bien pero "
                "ninguna accion cumplio la condicion hoy."
            )
        return

    encontrados.sort(key=lambda x: x["variacion_pct"], reverse=True)

    lineas = []
    for r in encontrados:
        lineas.append(
            f"{r['ticker']}: post-mercado ayer USD {r['precio_post_ayer']:.2f} -> "
            f"pre-mercado hoy USD {r['precio_pre_hoy']:.2f}  |  +{r['variacion_pct']:.1f}%  |  "
            f"Volumen x{r['ratio_volumen']:.1f} del postmarket de ayer"
        )

    cuerpo = (
        "Acciones que subieron {}% o mas del post-mercado de ayer al pre-mercado de hoy, "
        "con volumen {}x o mas el del post-mercado de ayer:\n\n".format(
            UMBRAL_PORCENTAJE, UMBRAL_VOLUMEN
        )
        + "\n".join(lineas)
    )

    asunto = f"🌅 Pre-Mercado vs Post-Mercado - {len(encontrados)} accion(es) detectada(s)"
    enviar_mail(asunto, cuerpo)


if __name__ == "__main__":
    main()
