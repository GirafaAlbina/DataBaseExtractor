# dependency
import pyarrow as pa
import pyarrow.parquet as pq


def exportar_parquet(chunks, arquivo_saida):
    writer = None
    total_linhas = 0
    try:
        for chunk in chunks:
            table = pa.Table.from_pandas(chunk, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(arquivo_saida, table.schema)

            writer.write_table(table)
            total_linhas += len(chunk)

        return total_linhas

    finally:
        if writer is not None:
            writer.close()