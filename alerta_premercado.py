# Guardar este archivo en: .github/workflows/alerta-premercado.yml
name: Alerta Pre-Mercado

on:
  schedule:
    # Corre UNA VEZ por dia, de lunes a viernes, a las 13:00 UTC
    # (10:00 hs Argentina - antes de que abra el mercado a las 10:30 ART)
    - cron: "0 13 * * 1-5"
  workflow_dispatch: {}   # permite ejecutarlo a mano tambien

jobs:
  chequear-premercado:
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

      - name: Ejecutar alerta de pre-mercado
        env:
          GMAIL_USER: ${{ secrets.GMAIL_USER }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          TO_EMAIL: ${{ secrets.TO_EMAIL }}
        run: python alerta_premercado.py
