"""
Alerta Pre-Mercado vs Cierre Regular del dia anterior
--------------------------------------------------------------------
Corre UNA SOLA VEZ por dia, a las 10:00 hs Argentina (antes de que
abra el mercado regular de EEUU a las 10:30 hs ART).

Compara:
  - PRECIO: el PRE-MERCADO de HOY (04:00 a 09:30 hs de Nueva York)
    contra el CIERRE DEL MERCADO REGULAR del DIA ANTERIOR (para
    capturar el movimiento completo desde antes de un balance u
    otra noticia, incluyendo lo que ya se movio en el afterhours).
  - VOLUMEN: el volumen de PRE-MERCADO de HOY contra el PROMEDIO
    del volumen de PRE-MERCADO de los ULTIMOS 2 DIAS HABILES (misma
    franja horaria, mismo tipo de sesion - comparacion pareja).

Condicion de alerta (las DOS deben cumplirse):
  1) El precio de pre-mercado de hoy sube 3.5% o mas vs. el cierre
     regular de ayer
  2) El volumen de pre-mercado de hoy es 3x o mas el promedio del
     volumen de pre-mercado de los ultimos 2 dias habiles

Manda UN SOLO mail (HTML, con fecha y tamaño legible en celular) con
todos los tickers que cumplen la condicion.

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
UMBRAL_PORCENTAJE = 3.0
UMBRAL_VOLUMEN = 1.5
TEST_MODE = False
ZONA_NY = "America/New_York"
ZONA_ART = "America/Argentina/Buenos_Aires"

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
    "GEV", "TLN", "KLAC", "WDC", "IBKR", "WELL", "PLD", "LIN", "SHW", "NTRA",
    "DELL", "SPCX", "RKLB", "BRK-B", "MSTR", "SQ", "NU", "SONY", "EA",
    "GLOB", "ROKU", "PM", "MO", "KHC", "MDLZ", "UL", "TM", "RACE",
    "STLA", "PBR", "VALE", "SHEL", "VIST", "AZN", "GSK", "MRNA",
]

GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
TO_EMAIL = os.environ.get("TO_EMAIL", GMAIL_USER)

DIAS_ES = {
    0: "Lunes", 1: "Martes", 2: "Miercoles", 3: "Jueves",
    4: "Viernes", 5: "Sabado", 6: "Domingo",
}
MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
    7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre",
    12: "Diciembre",
}


def fecha_hoy_ar_texto() -> str:
    ahora = datetime.datetime.now(datetime.timezone.utc).astimezone(
        __import__("zoneinfo").ZoneInfo(ZONA_ART)
    )
    dia_semana = DIAS_ES[ahora.weekday()]
    mes = MESES_ES[ahora.month]
    return f"{dia_semana} {ahora.day} de {mes} de {ahora.year}"


def enviar_mail(asunto: str, cuerpo_html: str):
    msg = MIMEText(cuerpo_html, "html")
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
        data = t.history(period="10d", interval="5m", prepost=True)
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

        # Volumen base: PROMEDIO del volumen de PRE-MERCADO de los ultimos
        # 2 dias habiles (misma franja horaria, mismo tipo de sesion -
        # comparacion "manzanas con manzanas", no contra la rueda regular).
        ultimos_2_dias = dias_anteriores[-2:]
        volumenes_premarket_previos = []
        for dia in ultimos_2_dias:
            df_dia = data[data.index.date == dia]
            pre_dia = df_dia.between_time("04:00", "09:30")
            if not pre_dia.empty:
                volumenes_premarket_previos.append(float(pre_dia["Volume"].sum()))

        if not volumenes_premarket_previos:
            return None, "sin premarket en los ultimos dias para calcular el promedio base"
        volumen_premarket_promedio = sum(volumenes_premarket_previos) / len(volumenes_premarket_previos)

        df_hoy = data[data.index.date == hoy]
        pre_hoy = df_hoy.between_time("04:00", "09:30")
        if pre_hoy.empty:
            return None, "sin operaciones en premarket de hoy (todavia)"
        precio_pre_hoy = float(pre_hoy["Close"].iloc[-1])
        volumen_pre_hoy = float(pre_hoy["Volume"].sum())

        if cierre_regular_ayer == 0 or volumen_premarket_promedio == 0:
            return None, "cierre o volumen base en cero, no se puede calcular"

        variacion_pct = (precio_pre_hoy - cierre_regular_ayer) / cierre_regular_ayer * 100
        ratio_volumen = volumen_pre_hoy / volumen_premarket_promedio
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


def armar_html(encontrados, fecha_texto: str) -> str:
    """Arma el cuerpo del mail en HTML, con tamaño de letra mediano
    pensado para que se lea comodo desde el celular."""
    estilo_base = (
        "font-family:Arial,Helvetica,sans-serif;font-size:16px;"
        "line-height:1.5;color:#111;"
    )
    if not encontrados:
        html = f"""\
<html>
  <body style="{estilo_base}margin:0;padding:16px;">
    <p style="font-size:18px;font-weight:bold;margin:0 0 4px 0;">🌅 Alerta Pre-Mercado</p>
    <p style="font-size:15px;color:#555;margin:0 0 16px 0;">{fecha_texto}</p>
    <p style="font-size:18px;font-weight:bold;color:#c00000;margin:0;">
      NO HAY MATCH CON LAS ACCIONES
    </p>
    <p style="font-size:15px;color:#555;margin:8px 0 0 0;">
      Ninguna accion cumplio hoy la condicion de precio y volumen.
    </p>
  </body>
</html>
"""
        return html

    filas = ""
    for r in encontrados:
        filas += f"""
        <tr>
          <td style="padding:8px 6px;border-bottom:1px solid #ddd;font-weight:bold;font-size:17px;">{r['ticker']}</td>
          <td style="padding:8px 6px;border-bottom:1px solid #ddd;color:#0a7a2f;font-weight:bold;font-size:16px;">+{r['variacion_pct']:.1f}%</td>
          <td style="padding:8px 6px;border-bottom:1px solid #ddd;font-size:16px;">Vol x{r['ratio_volumen']:.1f}</td>
        </tr>"""

    html = f"""\
<html>
  <body style="{estilo_base}margin:0;padding:16px;">
    <p style="font-size:18px;font-weight:bold;margin:0 0 4px 0;">🌅 Alerta Pre-Mercado</p>
    <p style="font-size:15px;color:#555;margin:0 0 16px 0;">{fecha_texto}</p>
    <p style="font-size:17px;font-weight:bold;margin:0 0 10px 0;">
      {len(encontrados)} accion(es) detectada(s)
    </p>
    <table style="border-collapse:collapse;width:100%;{estilo_base}">
      <tr>
        <th style="text-align:left;padding:6px;border-bottom:2px solid #333;font-size:15px;">Ticker</th>
        <th style="text-align:left;padding:6px;border-bottom:2px solid #333;font-size:15px;">%</th>
        <th style="text-align:left;padding:6px;border-bottom:2px solid #333;font-size:15px;">Volumen</th>
      </tr>
      {filas}
    </table>
  </body>
</html>
"""
    return html


def main():
    encontrados = []
    fecha_texto = fecha_hoy_ar_texto()
    print(f"Empezando a chequear {len(TICKERS)} tickers... ({fecha_texto})")

    for i, ticker in enumerate(TICKERS, start=1):
        resultado, motivo = chequear_ticker(ticker)
        print(f"[{i}/{len(TICKERS)}] {ticker}: {motivo}")
        if resultado:
            encontrados.append(resultado)

    if not encontrados:
        print("Ninguna accion cumplio la condicion hoy.")
        enviar_mail(
            "🌅 Pre-Mercado - NO HAY MATCH CON LAS ACCIONES",
            armar_html([], fecha_texto),
        )
        return

    encontrados.sort(key=lambda x: x["variacion_pct"], reverse=True)
    asunto = f"🌅 Pre-Mercado - {len(encontrados)} accion(es) detectada(s)"
    cuerpo_html = armar_html(encontrados, fecha_texto)
    enviar_mail(asunto, cuerpo_html)


if __name__ == "__main__":
    main()
