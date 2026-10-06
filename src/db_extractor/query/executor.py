import pandas as pd
from ..utils import expandir_parametros_lista


def executar_consulta(
    engine,
    consulta,
    chunksize=None,
    parametros=None
):
    consulta, parametros = expandir_parametros_lista(consulta, parametros)

    # SQLAlchemy - Oracle
    if hasattr(engine, "connect"):
        if chunksize is None:
            with engine.connect() as conn:
                result = conn.exec_driver_sql(consulta, parametros or {})
                colunas = [col[0] for col in result.cursor.description]
                rows = result.fetchall()
                return pd.DataFrame(rows, columns=colunas)

        def generator():
            with engine.connect() as conn:
                result = conn.exec_driver_sql(consulta, parametros or {})
                colunas = [col[0] for col in result.cursor.description]
                while True:
                    rows = result.fetchmany(chunksize)
                    if not rows:
                        break

                    yield pd.DataFrame(rows, columns=colunas)

        return generator()

    # DBAPI - Denodo
    if hasattr(engine, "cursor"):
        if chunksize is None:
            cursor = engine.cursor()
            try:
                cursor.execute(consulta, parametros or {})
                colunas = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                return pd.DataFrame(rows, columns=colunas)

            finally:
                cursor.close()
                engine.close()

        def generator():
            cursor = engine.cursor()
            try:
                cursor.execute(consulta, parametros or {})
                colunas = [col[0] for col in cursor.description]
                while True:
                    rows = cursor.fetchmany(chunksize)
                    if not rows:
                        break

                    yield pd.DataFrame(rows, columns=colunas)

            finally:
                cursor.close()
                engine.close()

        return generator()

    raise TypeError(f"Tipo de conexão não suportado: {type(engine)}")