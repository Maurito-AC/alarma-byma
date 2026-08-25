"""
Alerta de Movidas con Volumen - Acciones de EEUU con CEDEAR en BYMA
--------------------------------------------------------------------
Chequea el precio REAL en dolares (no el CEDEAR) de una lista amplia
de acciones importantes de EEUU que tienen CEDEAR en BYMA.

Condicion de alerta (las DOS deben cumplirse):
  1) Suba un 3% o mas en el dia (SOLO ALCISTA, no baja) - vela de
     hoy vs. vela de ayer.
  2) El volumen de hoy sea 2x o mas el volumen PROMEDIO de los
     ultimos 10 dias (no la vela inmediata anterior).

Manda UN SOLO mail por corrida con todos los tickers que cumplen
la condicion (no un mail por ticker).
"""

import os
import smtplib
from email.mime.text import MIMEText
import yfinance as yf

# ---------------------------------------------------------------
# CONFIGURACION DE LA ALERTA
# ---------------------------------------------------------------
UMBRAL_PORCENTAJE = 3.0      # % minimo de suba en el dia (vela vs vela anterior)
UMBRAL_VOLUMEN = 2.0         # veces el volumen PROMEDIO de los ultimos 10 dias

# MODO TEST: si esta en True, manda SIEMPRE un mail al final (aunque
# ninguna accion cumpla la condicion), para confirmar que el envio
# de mail funciona bien. Poner en False cuando ya lo confirmaste.
TEST_MODE = False

# ---------------------------------------------------------------
# LISTA DE TICKERS - ~100 acciones importantes de EEUU con CEDEAR en BYMA
# ---------------------------------------------------------------
TICKERS = [
    # Tecnologia / Mega cap
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA", "NFLX",
    "ORCL", "ADBE", "CRM", "INTC", "AMD", "QCOM", "TXN", "AVGO",
    "CSCO", "IBM", "MU", "AMAT", "LRCX", "MRVL", "ON", "PANW",
    "PLTR", "SNOW", "CRWD", "ZM", "UBER", "ABNB", "SHOP", "SPOT",
    "SNAP", "PINS", "COIN", "RIOT", "MARA", "IONQ", "RGTI", "ASTS",
    "HIMS", "NBIS", "CRWV",
    # Consumo / Retail
    "WMT", "COST", "TGT", "HD", "LOW", "MCD", "SBUX", "NKE", "DIS",
    "KO", "PEP", "PG", "KMB", "EL",
    # Financieras
    "JPM", "BAC", "WFC", "C", "GS", "MS", "V", "MA", "PYPL", "AXP",
    "BLK", "SCHW",
    # Salud
    "JNJ", "PFE", "MRK", "ABBV", "UNH", "LLY", "BMY", "GILD", "AMGN",
    "CVS", "MDT", "ABT",
    # Industriales
    "BA", "CAT", "DE", "GE", "HON", "MMM", "UPS", "RTX", "LMT", "GD",
    "UNP",
    # Energia
    "XOM", "CVX", "COP", "OXY", "SLB", "PSX",
    # Telecom
    "T", "VZ", "TMUS",
    # Autos
    "F", "GM",
    # ADRs chinos
    "BABA", "JD", "PDD", "BIDU", "NTES", "XPEV", "LI",
    # Semis / hardware extra
    "TSM", "ASML",
    # Materiales / mineria
    "FCX", "NEM", "GOLD", "PAAS",
    # Otros
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
    """Devuelve un dict con los datos si cumple la condicion, o None."""
    try:
        data = yf.Ticker(ticker).history(period="1mo", interval="1d")
        if data.empty or len(data) < 11:
            return None

        cierre_hoy = float(data["Close"].iloc[-1])
        cierre_ayer = float(data["Close"].iloc[-2])
        volumen_hoy = float(data["Volume"].iloc[-1])
        # Promedio de volumen de los ultimos 10 dias (sin contar hoy)
        volumen_promedio_10d = float(data["Volume"].iloc[-11:-1].mean())

        if volumen_promedio_10d == 0:
            return None

        variacion_pct = (cierre_hoy - cierre_ayer) / cierre_ayer * 100
        ratio_volumen = volumen_hoy / volumen_promedio_10d

        cumple = (variacion_pct >= UMBRAL_PORCENTAJE) and (ratio_volumen >= UMBRAL_VOLUMEN)

        if cumple:
            return {
                "ticker": ticker,
                "precio": cierre_hoy,
                "variacion_pct": variacion_pct,
                "ratio_volumen": ratio_volumen,
            }
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
        else:
            print(f"{ticker}: sin match")

    if not encontrados:
        print("Ninguna accion cumplio la condicion en esta corrida.")
        if TEST_MODE:
            enviar_mail(
                "🧪 Test - Alerta de precios EEUU (sin matches reales)",
                "Este es un mail de prueba (TEST_MODE = True).\n\n"
                "El script corrio bien y reviso {} tickers, pero ninguno cumplio "
                "la condicion (suba {}% o mas + volumen {}x o mas del promedio de 10 dias).\n\n"
                "Si este mail te llego, el envio de mail funciona correctamente. "
                "Cuando quieras dejar de recibir este aviso de prueba, poné "
                "TEST_MODE = False en el script.".format(
                    len(TICKERS), UMBRAL_PORCENTAJE, UMBRAL_VOLUMEN
                ),
            )
        return

    # Ordenar de mayor a menor variacion
    encontrados.sort(key=lambda x: x["variacion_pct"], reverse=True)

    lineas = []
    for r in encontrados:
        lineas.append(
            f"{r['ticker']}: USD {r['precio']:.2f}  |  +{r['variacion_pct']:.1f}%  |  Volumen x{r['ratio_volumen']:.1f} del promedio de 10 dias"
        )

    cuerpo = "Acciones con suba de {}% o mas y volumen {}x o mas del promedio de 10 dias:\n\n".format(
        UMBRAL_PORCENTAJE, UMBRAL_VOLUMEN
    ) + "\n".join(lineas)

    asunto = f"📈 Movida con Volumen - {len(encontrados)} accion(es) detectada(s)"
    enviar_mail(asunto, cuerpo)


if __name__ == "__main__":
    main()
