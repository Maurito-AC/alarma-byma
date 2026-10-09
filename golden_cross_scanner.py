import os
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf

ZONA_ART = ZoneInfo("America/Argentina/Buenos_Aires")

# ---------------------------------------------------------------
# MODO: lo define el workflow con la variable de entorno MODO
#   diario  -> velas diarias (1 año de historial)
#   semanal -> velas semanales (5 años de historial)
# ---------------------------------------------------------------
MODO = os.environ.get("MODO", "diario").strip().lower()
ES_SEMANAL = MODO == "semanal"
NOMBRE_MODO = "Semanal" if ES_SEMANAL else "Diario"
PERIODO_DESCARGA = "5y" if ES_SEMANAL else "1y"

# ---------------------------------------------------------------
# WATCHLIST (formato Yahoo Finance)
# ---------------------------------------------------------------
TICKERS_EEUU = [
    "PLTR", "LOMA", "VIST", "PM", "CVX", "PEP", "PSX", "XOM", "SDA", "AGRO",
    "PBR", "CEG", "CRWD", "SPOT", "TGT", "HSY", "RTX", "HD", "BMA", "DELL",
    "NKE", "AAP", "SHOP", "GLOB", "TGS", "PANW", "ADBE", "UBER", "NRG", "IBM",
    "GOOGL", "FSLR", "IRS", "PSQ", "NOW", "TLN", "LRCX", "AAPL", "CAT", "MSFT",
    "BRK-B", "FCX", "ACN", "MRSH", "MRK", "INTC", "HIMS", "UNH", "ROST", "MA",
    "NFLX", "VRTX", "MELI", "SNOW", "DIS", "MUX", "SUPV", "PLD", "MSI", "GLW",
    "AVGO", "SMCI", "ANET", "MS", "ARM", "CEPU", "XPEV", "EFX", "AXP", "AMZN",
    "O", "TEO", "COST", "PYPL", "V", "PFE", "SHEL", "TXN", "GGAL", "CRESY",
    "NVDA", "NIO", "COP", "BIOX", "NVO", "AMD", "ITA", "NEE", "DAL", "RIOT",
    "LMT", "TMUS", "PAAS", "HON", "NEM", "RIO", "BABA", "FISV", "CRM", "MDLZ",
    "MCD", "NTRA", "PAM", "GLNG", "KLAC", "WELL", "TM", "SONY", "YPF", "AMAT",
    "ASML", "META", "TSM", "MRVL", "QCOM", "SKHY", "TS", "HOOD", "DE", "VALE",
    "BKR", "HAL", "SLB", "MP", "NBIS", "NG", "OXY", "NU", "ORLY", "BNY",
    "TSLA", "BA", "TX", "FXI", "BKNG", "CORN", "WDC", "EWY", "EWZ", "CAAP",
    "SNA", "ADI", "IBIT", "ONDS", "GEV", "IBKR", "EDN", "HSBC", "BBAR", "SATL",
    "MSTR", "BB", "SHW", "WFC", "VST", "HPQ", "MRNA", "SOYB", "BX", "SMH",
    "CSCO", "CCL", "SPCX", "ISRG", "JPM", "C", "CCJ", "SAP", "TJX", "GE",
    "ORCL", "CVS", "COIN", "BMY", "MU", "NTES", "ALAB", "RGTI", "JNJ", "SNDK",
    "RKLB", "NOK", "OKLO", "BE", "CRWV", "TEM", "ASTS", "IREN", "LLY", "HUT",
    "MDT",
]

# Bolsa de Buenos Aires (CEDEARs y locales) -> se les agrega ".BA"
TICKERS_BCBA = [
    "MOLI", "ADGO", "WMT", "MO", "BHIP", "IBM", "BOLT", "ECOG", "TGNO4", "SUPVD",
    "JNJ", "METR", "HOG", "LAC", "AXP", "PEP", "UNH", "XOM", "TEN", "SAMI",
    "LAR", "MUX", "TGN4D", "MA", "AMZND", "ABEV", "EFX", "HIMS", "HMC", "ECOGD",
    "SPCE", "NATU3", "CSCO", "SWKS", "XROX", "TMC", "SAP", "TEAM", "SYY", "REIT",
    "MUXD", "SMH", "NVO", "F", "ASMLD", "BNG", "SIEGY", "TWLO", "CVH", "JD",
    "CECO2", "LEDE", "HD", "FSLR", "GS", "AGRO", "IRSA", "TRAN", "GPRK", "NOKA",
    "HARG", "QQQ", "TXAR", "KO", "CEPU", "CELU", "EDN", "CRES", "MOLA", "HPQ",
    "BIDU", "LLY", "RBLX",
]

# Otros mercados (Paris, Mexico, Toronto, Londres internacional, cripto)
TICKERS_OTROS = ["TTE.PA", "AMZN.MX", "CLS.TO", "PAAS.TO", "LAC.TO", "SMSN.IL", "BTC-USD"]

TICKERS = list(dict.fromkeys(
    TICKERS_EEUU + [t + ".BA" for t in TICKERS_BCBA] + TICKERS_OTROS
))

# ---------------------------------------------------------------
# PARAMETROS
# ---------------------------------------------------------------
SMA_CORTA = 50
SMA_LARGA = 200

# "Mas de 2 velas": la SMA50 tiene que llevar exactamente 3 velas seguidas por encima
# de la SMA200 (la vela del cruce cuenta como la 1). Como cada modo corre una vez por
# vela (diario: 1 por dia habil / semanal: 1 por semana), cada cruce avisa una sola vez.
# Poner 1 para avisar en el momento mismo del cruce.
VELAS_CONFIRMACION = 3

TAMANO_TANDA = 60       # tickers por descarga (evita bloqueos de Yahoo)
PAUSA_ENTRE_TANDAS = 2  # segundos


def velas_desde_golden_cross(serie_cierre: pd.Series) -> int | None:
    """
    Cantidad de velas consecutivas con SMA50 > SMA200 desde un cruce ascendente real
    (la vela del cruce cuenta como 1). None si la SMA50 no esta arriba en la ultima
    vela o si no se puede confirmar un cruce real.
    """
    sma50 = serie_cierre.rolling(SMA_CORTA).mean()
    sma200 = serie_cierre.rolling(SMA_LARGA).mean()

    arriba = ((sma50 > sma200) & sma200.notna()).values
    if not arriba[-1]:
        return None

    cuenta = 0
    for valor in arriba[::-1]:
        if valor:
            cuenta += 1
        else:
            break

    idx_previa = len(arriba) - cuenta - 1
    if idx_previa < 0 or pd.isna(sma200.iloc[idx_previa]):
        return None

    return cuenta


def cierre_semanal_confirmado(serie_cierre: pd.Series) -> pd.Series:
    """
    Cierre semanal (W-FRI). Descarta la ultima semana solo si todavia no termino
    (su viernes es hoy o futuro). Asi una semana con feriado en viernes
    (ej. Viernes Santo) se conserva correctamente.
    """
    semanal = serie_cierre.resample("W-FRI").last().dropna()
    hoy = datetime.now(ZONA_ART).date()
    if len(semanal) > 0 and semanal.index[-1].date() >= hoy:
        semanal = semanal.iloc[:-1]
    return semanal


def descargar_cierres(tickers: list[str]) -> dict[str, pd.Series]:
    """Descarga en tandas y devuelve {ticker: serie de cierres diarios}."""
    cierres = {}
    for i in range(0, len(tickers), TAMANO_TANDA):
        tanda = tickers[i:i + TAMANO_TANDA]
        print(f"Descargando tanda {i // TAMANO_TANDA + 1} ({len(tanda)} tickers)...")
        try:
            data = yf.download(
                tanda,
                period=PERIODO_DESCARGA,
                interval="1d",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
            close = data["Close"]
            if isinstance(close, pd.Series):
                close = close.to_frame(tanda[0])
        except Exception as e:
            print(f"Error en la tanda: {e}")
            continue

        for t in tanda:
            if t in close.columns:
                serie = close[t].dropna()
                if len(serie) > 0:
                    cierres[t] = serie
        time.sleep(PAUSA_ENTRE_TANDAS)
    return cierres


def enviar_mail(senales, sin_datos, insuficientes) -> None:
    remitente = os.environ["EMAIL_SENDER"]
    password = os.environ["EMAIL_PASSWORD"]
    destinatario = os.environ["EMAIL_TO"]

    ahora_art = datetime.now(ZONA_ART)
    fecha = ahora_art.strftime("%d/%m/%Y")
    hora = ahora_art.strftime("%H:%M")
    total = len(senales)
    unidad = "semanas" if ES_SEMANAL else "velas diarias"

    if total == 0:
        cuerpo = (
            f"<h2>NO HAY GOLDEN CROSS {NOMBRE_MODO.upper()} CONFIRMADO</h2>"
            f"<p>Ningún ticker tiene la SMA50 con más de 2 velas ({NOMBRE_MODO.lower()}s) por encima "
            f"de la SMA200 desde un cruce reciente. Chequeo realizado el {fecha} a las {hora} hs (ART).</p>"
        )
    else:
        filas = "".join(f"<tr><td>{t}</td><td>{n}</td></tr>" for t, n in senales)
        cuerpo = f"""
        <h2>Golden Cross {NOMBRE_MODO} confirmado(s)</h2>
        <p>Chequeo realizado el {fecha} a las {hora} hs (ART) - {total} ticker(s) con la SMA50 más de 2 velas por encima de la SMA200:</p>
        <table border="1" cellpadding="6" cellspacing="0">
            <tr><th>Ticker</th><th>Velas desde el cruce ({unidad})</th></tr>
            {filas}
        </table>
        """

    if sin_datos:
        cuerpo += (
            f"<p style='color:#666;font-size:12px'>Sin datos en Yahoo ({len(sin_datos)}): "
            f"{', '.join(sin_datos)}</p>"
        )
    if insuficientes:
        cuerpo += (
            f"<p style='color:#666;font-size:12px'>Historial insuficiente para la SMA200 "
            f"({len(insuficientes)}): {', '.join(insuficientes)}</p>"
        )

    asunto = (
        f"NO HAY GOLDEN CROSS {NOMBRE_MODO.upper()} CONFIRMADO - {fecha} {hora}hs"
        if total == 0
        else f"Golden Cross {NOMBRE_MODO} confirmado - {fecha} {hora}hs ({total} señal(es))"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = remitente
    msg["To"] = destinatario
    msg.attach(MIMEText(cuerpo, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(remitente, password)
        server.sendmail(remitente, destinatario, msg.as_string())


def main() -> None:
    print(f"MODO: {NOMBRE_MODO} | {len(TICKERS)} tickers | {PERIODO_DESCARGA} de historial diario")
    cierres = descargar_cierres(TICKERS)

    senales = []
    insuficientes = []
    sin_datos = [t for t in TICKERS if t not in cierres]

    for ticker, cierre_diario in cierres.items():
        serie = cierre_semanal_confirmado(cierre_diario) if ES_SEMANAL else cierre_diario

        if len(serie) < SMA_LARGA + 2:
            insuficientes.append(ticker)
            continue

        n = velas_desde_golden_cross(serie)
        if n is not None and n == VELAS_CONFIRMACION:
            senales.append((ticker, n))

    print(f"Golden Cross {NOMBRE_MODO.lower()} confirmado: {senales}")
    print(f"Sin datos ({len(sin_datos)}): {sin_datos}")
    print(f"Historial insuficiente ({len(insuficientes)}): {insuficientes}")

    enviar_mail(senales, sin_datos, insuficientes)


if __name__ == "__main__":
    main()
