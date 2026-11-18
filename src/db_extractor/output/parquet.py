import polars as pl
import pyarrow.parquet as pq


def aplicar_downcasting_polars(df: pl.DataFrame) -> pl.DataFrame:
    """Compacta automaticamente tipos numéricos e strings repetitivas em Rust."""
    expressoes = []
    n_linhas = len(df)

    for col, dtype in df.schema.items():
        # Compacta inteiros e floats para o menor tipo seguro (ex: Int64 -> Int32/Int16)
        if dtype.is_numeric():
            expressoes.append(pl.col(col).shrink_dtype())
        # Converte strings de baixa cardinalidade (< 5% únicos) para Categorical
        elif dtype == pl.String and n_linhas > 0:
            if df[col].n_unique() / n_linhas < 0.05:
                expressoes.append(pl.col(col).cast(pl.Categorical))

    return df.with_columns(expressoes) if expressoes else df


def exportar_parquet_polars(
    chunks,
    arquivo_saida: str,
    compression: str = "zstd",
    downcast: bool = True,
) -> int:
    writer = None
    schema_fixo = None
    total_linhas = 0

    try:
        for chunk in chunks:
            # 'chunk' pode ser a lista de tuplas direto de cursor.fetchmany()
            if not chunk:
                continue

            df = pl.DataFrame(chunk, orient="row")

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
                # Garante compatibilidade de schema entre lotes (ex: colunas nulas em um chunk)
                table = table.cast(schema_fixo, safe=False)

            writer.write_table(table)
            total_linhas += len(df)

        return total_linhas

    finally:
        if writer is not None:
            writer.close()