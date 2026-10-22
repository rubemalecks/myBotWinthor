
import os
from pathlib import Path

import oracledb
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

oracledb.init_oracle_client(
    lib_dir=str(Path(__file__).resolve().parent.parent / "oracle_client")
)

with oracledb.connect(
    user=os.getenv("ORACLE_USER"),
    password=os.getenv("ORACLE_PASSWORD"),
    host=os.getenv("ORACLE_HOST"),
    port=int(os.getenv("ORACLE_PORT", "1521")),
    service_name=os.getenv("ORACLE_SERVICE"),
) as conexao:

    with conexao.cursor() as cursor:
        cursor.execute("""
            SELECT
                CODPROD,
                DESCRICAO,
                CODAUXILIAR
            FROM PCPRODUT
            WHERE CODPROD = :codigo
        """, codigo=2941)

        produto = cursor.fetchone()

        if produto:
            print("Código:", produto[0])
            print("Descrição:", produto[1])
            print("Código de barras:", produto[2])
        else:
            print("Produto não encontrado.")
