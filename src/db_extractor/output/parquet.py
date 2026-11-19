import pandas as pd
import polars as pl
import pyarrow.parquet as pq


def aplicar_downcasting_polars(df: pl.DataFrame) -> pl.DataFrame:
    """Compacta automaticamente tipos numéricos e strings repetitivas em Rust."""
    expressoes = []
    n_linhas = len(df)

    for col, dtype in df.schema.items():
        if dtype.is_numeric():
            expressoes.append(pl.col(col).shrink_dtype())
        elif dtype == pl.String and n_linhas > 0:
            if df[col].n_unique() / n_linhas < 0.05:
                expressoes.append(pl.col(col).cast(pl.Categorical))

    return df.with_columns(expressoes) if expressoes else df


def exportar_parquet(
    chunks,
    arquivo_saida: str,
    compression: str = "snappy",
    downcast: bool = True,
    colunas: list[str] | None = None,
) -> int:
    writer = None
    schema_fixo = None
    total_linhas = 0

    try:
        for chunk in chunks:
            if chunk is None:
                continue

            # Converte o chunk para pl.DataFrame independente da origem
            if isinstance(chunk, pl.DataFrame):
                if chunk.is_empty():
                    continue
                df = chunk
            elif isinstance(chunk, pd.DataFrame):
                if chunk.empty:
                    continue
                df = pl.from_pandas(chunk)
            else:
                # Lista de tuplas/linhas direto de cursor.fetchmany()
                if not chunk:
                    continue
                df = pl.DataFrame(chunk, schema=colunas, orient="row")

            if downcast:
                df = aplicar_downcasting_polars(df)

            # Conversão zero-copy para Apache Arrow
            table = df.to_arrow()

            if schema_fixo is None:
                schema_fixo = table.schema
                writer = pq.ParquetWriter(
                    arquivo_saida,
                    schema_fixo,
                    compression=compression,
                )
            else:
                table = table.cast(schema_fixo, safe=False)

            writer.write_table(table)
            total_linhas += len(df)

        return total_linhas

    finally:
        if writer is not None:
            writer.close()