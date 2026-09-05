import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

import pandas as pd
import yfinance as yf

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
    # Nuevos CEDEARs incorporados por Banco Comafi (agosto 2026)
    "GEV", "TLN", "KLAC", "DELL", "WDC", "IBKR", "WELL", "PLD", "LIN", "SHW", "NTRA",
    # Nuevos tickers agregados (septiembre 2026)
    "SPCX", "RKLB", "BRK-B", "MSTR", "SQ", "NU", "SONY", "EA", "GLOB",
    "ROKU", "PM", "MO", "KHC", "MDLZ", "UL", "TM", "RACE", "STLA",
    "PBR", "VALE", "SHEL", "VIST", "AZN", "GSK", "MRNA",
]

SMA_CORTA = 50
SMA_LARGA = 200

# 6 años de historia diaria: de ahí sale suficiente data semanal
# (~300 semanas) para poder calcular SMA200 también en esa temporalidad.
PERIODO_DESCARGA = "6y"


def detectar_golden_cross(serie_cierre: pd.Series) -> bool:
    """
    True si en la última vela se confirmó el cruce ascendente:
    - vela anterior: SMA50 <= SMA200
    - vela actual:   SMA50 >  SMA200
    (evita marcar tickers que ya vienen cruzados hace tiempo)
    """
    if len(serie_cierre) < SMA_LARGA + 2:
        return False

    sma50 = serie_cierre.rolling(SMA_CORTA).mean()
    sma200 = serie_cierre.rolling(SMA_LARGA).mean()

    if sma50.iloc[-2:].isna().any() or sma200.iloc[-2:].isna().any():
        return False

    cruzo_ahora = sma50.iloc[-1] > sma200.iloc[-1]
    no_cruzado_antes = sma50.iloc[-2] <= sma200.iloc[-2]

    return bool(cruzo_ahora and no_cruzado_antes)


def enviar_mail(golden_daily: list[str], golden_weekly: list[str]) -> None:
    remitente = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]
    destinatario = os.environ["EMAIL_TO"]

    fecha = datetime.now().strftime("%d/%m/%Y")
    total = len(golden_daily) + len(golden_weekly)

    filas = ""
    for t in golden_daily:
        filas += f"<tr><td>{t}</td><td>Diario</td></tr>"
    for t in golden_weekly:
        filas += f"<tr><td>{t}</td><td>Semanal</td></tr>"

    if total == 0:
        cuerpo = f"<h2>NO HAY CRUCE GOLDEN CROSS</h2><p>No se detectaron cruces SMA50/SMA200 ascendentes el {fecha}.</p>"
    else:
        cuerpo = f"""
        <h2>Golden Cross detectado(s)</h2>
        <p>{fecha} - {total} ticker(s) con cruce ascendente reciente:</p>
        <table border="1" cellpadding="6" cellspacing="0">
            <tr><th>Ticker</th><th>Temporalidad</th></tr>
            {filas}
        </table>
        """

    asunto = f"NO HAY CRUCE GOLDEN CROSS - {fecha}" if total == 0 else f"Golden Cross - {fecha} ({total} señal(es))"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = destinatario
    msg.attach(MIMEText(cuerpo, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(remitente, password)
        server.sendmail(remitente, destinatario, msg.as_string())


def main() -> None:
    print(f"Descargando {PERIODO_DESCARGA} de historial diario para {len(TICKERS)} tickers...")
    data = yf.download(
        TICKERS,
        period=PERIODO_DESCARGA,
        interval="1d",
        auto_adjust=True,
        threads=True,
        progress=False,
    )

    golden_daily = []
    golden_weekly = []

    for ticker in TICKERS:
        try:
            cierre_diario = data["Close"][ticker].dropna()
        except KeyError:
            print(f"Sin datos para {ticker}, se salteó.")
            continue

        if detectar_golden_cross(cierre_diario):
            golden_daily.append(ticker)

        cierre_semanal = cierre_diario.resample("W-FRI").last().dropna()
        if detectar_golden_cross(cierre_semanal):
            golden_weekly.append(ticker)

    print(f"Golden Cross diario: {golden_daily}")
    print(f"Golden Cross semanal: {golden_weekly}")

    enviar_mail(golden_daily, golden_weekly)


if __name__ == "__main__":
    main()
