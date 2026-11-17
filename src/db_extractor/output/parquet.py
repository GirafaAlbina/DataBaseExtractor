import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


def aplicar_downcasting(df: pd.DataFrame) -> pd.DataFrame:
    """Reduz o consumo de RAM e disco convertendo tipos 64-bit para menores quando seguro."""
    for col in df.columns:
        serie = df[col]
        dtype = serie.dtype

        if pd.api.types.is_integer_dtype(dtype):
            df[col] = pd.to_numeric(serie, downcast="integer")
        elif pd.api.types.is_float_dtype(dtype):
            # Verifica se uma coluna float na verdade representa inteiros com NaN
            sem_nulos = serie.dropna()
            if not sem_nulos.empty and (sem_nulos % 1 == 0).all():
                # Usa Int32/Int64 nullable do Pandas para preservar inteiros com NaN
                min_val, max_val = sem_nulos.min(), sem_nulos.max()
                if -2_147_483_648 <= min_val and max_val <= 2_147_483_647:
                    df[col] = serie.astype("Int32")
                else:
                    df[col] = serie.astype("Int64")
            else:
                df[col] = pd.to_numeric(serie, downcast="float")
        elif pd.api.types.is_object_dtype(dtype):
            # Converte colunas de baixa cardinalidade (ex: SITUACAO, FASE, REGIONAL) em dicionário
            if len(df) > 0 and (serie.nunique(dropna=True) / len(df)) < 0.05:
                df[col] = serie.astype("category")

    return df


def exportar_parquet(
    chunks,
    arquivo_saida: str,
    compression: str = "snappy",
    downcast: bool = True,
) -> int:
    writer = None
    schema_fixo = None
    total_linhas = 0

    try:
        for chunk in chunks:
            if chunk.empty:
                continue

            if downcast:
                chunk = aplicar_downcasting(chunk)

            if schema_fixo is None:
                table = pa.Table.from_pandas(chunk, preserve_index=False)
                schema_fixo = table.schema
                writer = pq.ParquetWriter(
                    arquivo_saida,
                    schema_fixo,
                    compression=compression,
                )
            else:
                # Força o mesmo schema do primeiro chunk para evitar erro de tipo entre lotes
                table = pa.Table.from_pandas(
                    chunk,
                    schema=schema_fixo,
                    preserve_index=False,
                    safe=False,
                )

            writer.write_table(table)
            total_linhas += len(chunk)

        return total_linhas

    finally:
        if writer is not None:
            writer.close()