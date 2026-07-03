# dependency
import pandas as pd
from ..utils import expandir_parametros_lista


def executar_consulta(engine, consulta, chunksize=None, parametros=None):
    consulta, parametros = expandir_parametros_lista(consulta, parametros)
    if chunksize is None:
        with engine.connect() as conn:
            result = conn.exec_driver_sql(consulta, parametros or {})
            colunas = [col[0] for col in result.cursor.description]
            rows = result.fetchall()
            return pd.DataFrame(rows, columns=colunas)

    def generator():
        conn = engine.connect()
        try:
            result = conn.exec_driver_sql(consulta, parametros or {})
            colunas = [col[0] for col in result.cursor.description]
            while True:
                rows = result.fetchmany(chunksize)
                if not rows:
                    break
                yield pd.DataFrame(rows, columns=colunas)
        finally:
            conn.close()
    return generator()