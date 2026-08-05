# dependency
import pandas as pd
# db_export
from .._constants import MAX_EXCEL_ROWS


def _gerar_nome_planilha(nome_base, indice):
    if indice == 0:
        nome = nome_base
    else:
        nome = f"{nome_base}_{indice}"
    return nome[:31]


def exportar_xlsx(chunks, arquivo_saida, nome_planilha="Dados"):

    total_linhas = 0
    total_abas = 0
    aba_atual = 0
    linhas_aba = 0
    writer = pd.ExcelWriter(arquivo_saida,engine="openpyxl")

    try:
        for chunk in chunks:
            inicio = 0
            while inicio < len(chunk):
                espaco_disponivel = (MAX_EXCEL_ROWS - linhas_aba)
                parte = chunk.iloc[
                    inicio:
                    inicio + espaco_disponivel
                ]

                sheet_name = _gerar_nome_planilha(nome_planilha,aba_atual)

                if linhas_aba == 0:
                    parte.to_excel(
                        writer,
                        sheet_name=sheet_name,
                        index=False,
                        startrow=0
                    )
                    linhas_escritas = len(parte)

                else:
                    ws = writer.sheets[sheet_name]
                    startrow = ws.max_row
                    parte.to_excel(
                        writer,
                        sheet_name=sheet_name,
                        index=False,
                        header=False,
                        startrow=startrow
                    )
                    linhas_escritas = len(parte)

                linhas_aba += linhas_escritas
                total_linhas += linhas_escritas
                inicio += linhas_escritas
                if linhas_aba >= MAX_EXCEL_ROWS:
                    aba_atual += 1
                    total_abas += 1
                    linhas_aba = 0

        if linhas_aba > 0:
            total_abas += 1

        writer.close()
        return {
            "arquivo": arquivo_saida,
            "linhas": total_linhas,
            "abas": total_abas
        }

    finally:
        try:
            writer.close()
        except:
            pass