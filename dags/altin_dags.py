"""Altın pipeline'ının zamanlanmış işleri.

altin_gunluk        : Her iş gününden sonra (Salı–Cumartesi 01:00)  veri çek -> kalite kontrol -> tahmin
altin_aylik_egitim  : Her ayın 1'i 03:00                            modeli yeniden eğit

Airflow sadece "ne zaman, hangi sırayla" sorusunu yönetir. Asıl iş src/ altındaki
script'lerde, kendi Python ortamlarında (altin-venv) çalışır.
"""

import os
from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

# Projenin container içindeki yeri ve projeye ait Python (Airflow'unkinden AYRI ortam)
PROJE = os.environ.get("ALTIN_PROJE", "/opt/altin")
PYTHON = os.environ.get("ALTIN_PYTHON", "/home/airflow/altin-venv/bin/python")


def komut(script: str) -> str:
    """src/ altındaki bir script'i projenin Python'uyla çalıştıran komut."""
    return f"cd {PROJE} && {PYTHON} src/{script}"


varsayilan = {
    "owner": "kadir",
    "retries": 2,                          # Hata olursa 2 kez daha dene
    "retry_delay": timedelta(minutes=5),   # Denemeler arasında 5 dakika bekle
}

with DAG(
    dag_id="altin_gunluk",
    description="Veri çek, kalite kontrol, tahmin",
    schedule="0 1 * * 2-6",  # Salı–Cumartesi 01:00 (Pazartesi–Cuma kapanışlarından sonra)
    start_date=pendulum.datetime(2026, 10, 1, tz="Europe/Istanbul"),
    catchup=False,           # Kaçırılan günleri tek tek çalıştırma (pipeline zaten son 10 günü çekiyor)
    default_args=varsayilan,
    tags=["altin"],
) as gunluk:
    veri_cek = BashOperator(task_id="veri_cek", bash_command=komut("pipeline.py"))
    kalite = BashOperator(task_id="kalite_kontrol", bash_command=komut("quality.py"))
    tahmin = BashOperator(task_id="tahmin", bash_command=komut("predict.py"))

    veri_cek >> kalite >> tahmin

with DAG(
    dag_id="altin_aylik_egitim",
    description="Modeli en güncel veriyle yeniden eğit",
    schedule="0 3 1 * *",    # Her ayın 1'i 03:00
    start_date=pendulum.datetime(2026, 10, 1, tz="Europe/Istanbul"),
    catchup=False,
    default_args=varsayilan,
    tags=["altin"],
) as aylik:
    BashOperator(task_id="egit", bash_command=komut("train.py"))