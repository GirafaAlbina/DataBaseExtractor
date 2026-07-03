import os
from datetime import datetime


def memoria_dataframe_mb(df):
    return (memoria_dataframe(df) / 1024**2)


def formatar_tamanho(bytes_valor):
    if bytes_valor >= 1024**3:
        return f"{bytes_valor / 1024**3:.2f} GB"
    if bytes_valor >= 1024**2:
        return f"{bytes_valor / 1024**2:.2f} MB"
    if bytes_valor >= 1024:
        return f"{bytes_valor / 1024:.2f} KB"
    return f"{bytes_valor} B"


def memoria_dataframe(df):
    if hasattr(df, "estimated_size"):
        return df.estimated_size()
    return df.memory_usage(deep=True).sum()


def memoria_dataframe_formatada(df):
    memoria = memoria_dataframe(df)
    return formatar_tamanho(memoria)


def tamanho_arquivo(caminho):
    if not os.path.exists(caminho):
        return 0
    return os.path.getsize(caminho)


def tamanho_arquivo_formatado(caminho):
    tamanho = tamanho_arquivo(caminho)
    return formatar_tamanho(tamanho)


def timestamp():
    return datetime.now().strftime("%H:%M:%S")


def imprimir_chunk(numero_chunk, linhas_chunk, total_linhas, memoria_chunk):
    print()
    print(f"[{timestamp()}]")
    print(f"Chunk..........: {numero_chunk}")
    print(f"Linhas Chunk...: {linhas_chunk:,}")
    print(f"Total Linhas...: {total_linhas:,}")
    print(f"Memória Chunk..: {formatar_tamanho(memoria_chunk)}")


def imprimir_dataframe(df, tempo_execucao, dataframe="pandas"):
    print()
    print("Consulta Finalizada")
    print(f"DataFrame......: {dataframe}")
    print(f"Linhas.........: {len(df):,}")
    print(f"Colunas........: {len(df.columns)}")
    print(f"Memória........: {memoria_dataframe_formatada(df)}")
    print(f"Tempo..........: {tempo_execucao:.2f} s")


def imprimir_exportacao(arquivo, linhas, tempo_execucao):
    print()
    print("Exportação Finalizada")
    print(f"Arquivo........: {arquivo}")
    print(f"Linhas.........: {linhas:,}")
    print(f"Tamanho........: {tamanho_arquivo_formatado(arquivo)}")
    print(f"Tempo..........: {tempo_execucao:.2f} s")