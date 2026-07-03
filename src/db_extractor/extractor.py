from time import perf_counter
import os

# db_extractor
from ._config import obter_config_banco
from ._constants import DEFAULT_SHEET_NAME, DEFAULT_CSV_SEPARATOR

# db_extractor/folder
from .connection import criar_conexao
from .query import carregar_consulta, executar_consulta
from .output import exportar_csv, exportar_xlsx, exportar_parquet
from .models import ExportResult
from .utils import (normalizar_banco, normalizar_consulta, normalizar_saida, 
                    normalizar_nome_planilha, normalizar_chunksize, validar_saida,
                    validar_consulta, validar_chunksize, validar_nome_planilha,
                    resolver_saida, imprimir_exportacao, imprimir_chunk,
                    memoria_dataframe, imprimir_dataframe)


def _monitorar_chunks(chunks):
    total_linhas = 0
    numero_chunk = 0
    for chunk in chunks:
        numero_chunk += 1
        linhas_chunk = len(chunk)
        total_linhas += linhas_chunk
        imprimir_chunk(
            numero_chunk=numero_chunk,
            linhas_chunk=linhas_chunk,
            total_linhas=total_linhas,
            memoria_chunk=memoria_dataframe(chunk)
        )
        yield chunk


def exportar_consulta(
    banco,
    consulta,
    saida,
    separador=DEFAULT_CSV_SEPARATOR,
    chunksize=None,
    parametros=None,
    nome_planilha=DEFAULT_SHEET_NAME,
    monitorar=True
):
    """
    Executa uma consulta SQL/VQL e exporta o resultado.

    Parameters
    ----------
    banco : str                 - Nome do banco cadastrado no config.json.
    consulta : str              - Caminho do arquivo .sql ou .vql.
    saida : str                 - Arquivo de saída (.csv ou .xlsx).
    chunksize : int | None      - Tamanho dos lotes para leitura.
    parametros : dict | None    - Parâmetros da consulta.
    nome_planilha : str         - Nome base da planilha Excel.

    Returns
    -------
    ExportResult
    """

    banco = normalizar_banco(banco)
    consulta = normalizar_consulta(consulta)
    saida = normalizar_saida(saida)
    saida = resolver_saida(saida)
    chunksize = normalizar_chunksize(chunksize)
    nome_planilha = normalizar_nome_planilha(nome_planilha)

    validar_consulta(consulta)
    validar_saida(saida)
    validar_chunksize(chunksize)
    validar_nome_planilha(nome_planilha)

    inicio = perf_counter()
    engine = None

    try:

        cfg = obter_config_banco(banco)
        engine = criar_conexao(cfg)
        sql = carregar_consulta(consulta)
        chunks = executar_consulta(
            engine=engine,
            consulta=sql,
            chunksize=chunksize,
            parametros=parametros
        )
        if chunksize is None:
            chunks = [chunks]
            
        if monitorar and chunksize is not None:
            chunks = _monitorar_chunks(chunks)

        extensao = os.path.splitext(saida)[1].lower()
        abas = 1

        if extensao == ".csv":
            linhas = exportar_csv(
                chunks=chunks, arquivo_saida=saida, separador=separador
            )

        elif extensao == ".xlsx":
            resultado = exportar_xlsx(
                chunks=chunks, arquivo_saida=saida, nome_planilha=nome_planilha
            )
            linhas = resultado["linhas"]
            abas = resultado["abas"]

        elif extensao == ".parquet":
            linhas = exportar_parquet(chunks, saida)
            abas = 1

        else:
            raise ValueError(f"Formato não suportado: {extensao}")

        fim = perf_counter()
        if monitorar:
            imprimir_exportacao(
                arquivo=saida,
                linhas=linhas,
                tempo_execucao=fim - inicio
            )

        return ExportResult(
            arquivo=saida,
            formato=extensao[1:],
            banco=banco,
            consulta=consulta,
            linhas=linhas,
            abas=abas,
            chunksize=chunksize,
            tempo_execucao=round(fim - inicio,2)
        )

    finally:
        if engine is not None:
            try:
                engine.dispose()
            except Exception:
                pass


def consultar_dataframe(
    banco,
    consulta,
    parametros=None,
    chunksize=None,
    dataframe="pandas",
    monitorar=True
):
    """
    Executa uma consulta SQL/VQL.

    Parameters
    ----------
    banco : str                 - Nome do banco.
    consulta : str              - Arquivo SQL ou VQL.
    parametros : dict | None    - Parâmetros da consulta.
    chunksize : int | None      - Tamanho dos lotes.

    Returns
    -------
    pandas.DataFrame            - Quando chunksize=None.
    Generator[pandas.DataFrame] - Quando chunksize é informado.
    """

    banco = normalizar_banco(banco)
    consulta = normalizar_consulta(consulta)
    chunksize = normalizar_chunksize(chunksize)

    validar_consulta(consulta)
    validar_chunksize(chunksize)

    dataframe = dataframe.lower()
    if dataframe not in ("pandas", "polars"):
        raise ValueError("dataframe deve ser 'pandas' ou 'polars'")
    
    inicio = perf_counter()
    cfg = obter_config_banco(banco)
    db_engine = criar_conexao(cfg)
    
    try:
        sql = carregar_consulta(consulta)
        if chunksize is None:
            resultado = executar_consulta(
                engine=db_engine,
                consulta=sql,
                parametros=parametros,
                chunksize=None
            )
            if resultado is None:
                return None
            
            if dataframe == "polars":
                import polars as pl
                resultado_polars = (pl.from_pandas(resultado))
                fim = perf_counter()
                if monitorar:
                    imprimir_dataframe(
                        df=resultado_polars,
                        tempo_execucao=(fim - inicio),
                        dataframe="polars"
                    )
                return resultado_polars

            fim = perf_counter()
            if monitorar:
                imprimir_dataframe(
                    df=resultado,
                    tempo_execucao=(fim - inicio),
                    dataframe="pandas"
                )
            return resultado

        def generator():
            total_linhas = 0
            numero_chunk = 0
            try:
                for chunk in executar_consulta(
                    engine=db_engine,
                    consulta=sql,
                    parametros=parametros,
                    chunksize=chunksize
                ):
                    numero_chunk += 1
                    linhas_chunk = len(chunk)
                    total_linhas += (linhas_chunk)
                    if monitorar:
                        imprimir_chunk(
                            numero_chunk=numero_chunk,
                            linhas_chunk=linhas_chunk,
                            total_linhas=total_linhas,
                            memoria_chunk=memoria_dataframe(chunk)
                        )

                    if dataframe == "polars":
                        import polars as pl
                        yield pl.from_pandas(chunk)

                    else:

                        yield chunk

            finally:
                if hasattr(db_engine,"dispose"):
                    db_engine.dispose()

        return generator()

    except Exception:
        if hasattr(db_engine,"dispose"):
            db_engine.dispose()
        raise