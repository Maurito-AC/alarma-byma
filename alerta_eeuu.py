"""
Alerta de Movidas con Volumen - Acciones de EEUU con CEDEAR en BYMA
--------------------------------------------------------------------
Chequea el precio REAL en dolares (no el CEDEAR) de una lista amplia
de acciones importantes de EEUU que tienen CEDEAR en BYMA.

Condicion de alerta (las DOS deben cumplirse):
  1) Suba un 3% o mas en el dia (SOLO ALCISTA, no baja) - vela de
     hoy vs. vela de ayer.
  2) El volumen de hoy sea 2x o mas el volumen PROMEDIO de los
     ultimos 2 dias habiles (no la vela inmediata anterior).

Manda UN SOLO mail por corrida con todos los tickers que cumplen
la condicion (no un mail por ticker).

Esta version SIEMPRE imprime un resultado por cada ticker (motivo
exacto incluido: match, sin match con los numeros, sin datos, o
error especifico), para poder diagnosticar bien cualquier caso.
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText
import yfinance as yf

sys.stdout.reconfigure(line_buffering=True)

# ---------------------------------------------------------------
# CONFIGURACION DE LA ALERTA
# ---------------------------------------------------------------
UMBRAL_PORCENTAJE = 3.0      # % minimo de suba en el dia (vela vs vela anterior)
UMBRAL_VOLUMEN = 1.3         # veces el volumen PROMEDIO de los ultimos 2 dias habiles

# MODO TEST: si esta en True, manda SIEMPRE un mail al final (aunque
# ninguna accion cumpla la condicion), para confirmar que el envio
# de mail funciona bien. Poner en False cuando ya lo confirmaste.
TEST_MODE = False

# ---------------------------------------------------------------
# LISTA DE TICKERS - ~100 acciones importantes de EEUU con CEDEAR en BYMA
# ---------------------------------------------------------------
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
# CREDENCIALES (GitHub Secrets)
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
    """
    Devuelve SIEMPRE una tupla (resultado, motivo):
      - resultado: dict si cumple la condicion, si no None
      - motivo: string explicando el resultado (para loguear en main)
    """
    try:
        data = yf.Ticker(ticker).history(period="1mo", interval="1d")
        if data.empty:
            return None, "sin datos disponibles"
        if len(data) < 3:
            return None, f"muy pocos datos historicos ({len(data)} velas)"

        cierre_hoy = float(data["Close"].iloc[-1])
        cierre_ayer = float(data["Close"].iloc[-2])
        volumen_hoy = float(data["Volume"].iloc[-1])
        volumen_promedio_2d = float(data["Volume"].iloc[-3:-1].mean())

        if cierre_ayer == 0 or volumen_promedio_2d == 0:
            return None, "cierre o volumen base en cero, no se puede calcular"

        variacion_pct = (cierre_hoy - cierre_ayer) / cierre_ayer * 100
        ratio_volumen = volumen_hoy / volumen_promedio_2d
        cumple = (variacion_pct >= UMBRAL_PORCENTAJE) and (ratio_volumen >= UMBRAL_VOLUMEN)

        if cumple:
            return {
                "ticker": ticker,
                "precio": cierre_hoy,
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
        print("Ninguna accion cumplio la condicion en esta corrida.")
        if TEST_MODE:
            enviar_mail(
                "🧪 Test - Alerta de precios EEUU (sin matches reales)",
                "Este es un mail de prueba (TEST_MODE = True).\n\n"
                "El script corrio bien y reviso {} tickers, pero ninguno cumplio "
                "la condicion (suba {}% o mas + volumen {}x o mas del promedio de 2 dias habiles).\n\n"
                "Si este mail te llego, el envio de mail funciona correctamente. "
                "Cuando quieras dejar de recibir este aviso de prueba, poné "
                "TEST_MODE = False en el script.".format(
                    len(TICKERS), UMBRAL_PORCENTAJE, UMBRAL_VOLUMEN
                ),
            )
        return

    encontrados.sort(key=lambda x: x["variacion_pct"], reverse=True)
    lineas = [
        f"{r['ticker']}: USD {r['precio']:.2f}  |  +{r['variacion_pct']:.1f}%  |  "
        f"Volumen x{r['ratio_volumen']:.1f} del promedio de 2 dias habiles"
        for r in encontrados
    ]
    cuerpo = "Acciones con suba de {}% o mas y volumen {}x o mas del promedio de 2 dias habiles:\n\n".format(
        UMBRAL_PORCENTAJE, UMBRAL_VOLUMEN
    ) + "\n".join(lineas)

    asunto = f"📈 Movida con Volumen - {len(encontrados)} accion(es) detectada(s)"
    enviar_mail(asunto, cuerpo)


if __name__ == "__main__":
    main()
