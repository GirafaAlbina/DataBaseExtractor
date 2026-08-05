import os

def exportar_csv(chunks, arquivo_saida, separador):
    total_linhas = 0
    primeiro = True
    for chunk in chunks:
        linhas = len(chunk)
        total_linhas += linhas
        chunk.to_csv(
            arquivo_saida,
            mode="w" if primeiro else "a",
            index=False,
            sep=separador,
            decimal=",",
            encoding="utf-8-sig",
            header=primeiro
        )
        primeiro = False

    return total_linhas