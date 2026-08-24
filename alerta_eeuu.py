# Guardar este archivo en: .github/workflows/alerta-eeuu.yml
name: Alerta de precios EEUU

on:
  schedule:
    # Corre cada 15 minutos, de lunes a viernes,
    # entre las 12:00 y 20:45 UTC (9:00 a 17:45 hora Argentina),
    # con margen para cubrir bien el rango pedido de 9:30 a 17:30
    - cron: "*/15 12-20 * * 1-5"
  workflow_dispatch: {}   # permite tambien ejecutarlo a mano desde GitHub

jobs:
  chequear-precios:
    runs-on: ubuntu-latest
    steps:
      - name: Clonar repo
        uses: actions/checkout@v4

      - name: Configurar Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Instalar dependencias
        run: pip install -r requirements.txt

      - name: Ejecutar alerta
        env:
          GMAIL_USER: ${{ secrets.GMAIL_USER }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          TO_EMAIL: ${{ secrets.TO_EMAIL }}
        run: python alerta_eeuu.py
