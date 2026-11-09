from time import perf_counter
import os

# db_extractor
from ._config import (
    obter_config_banco, 
    montar_e_validar_config_direta
)
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


def _fechar_conexao(conexao):
    if conexao is None:
        return

    if hasattr(conexao, "dispose"):
        conexao.dispose()
    elif hasattr(conexao, "close"):
        conexao.close()


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
    monitorar=True,
    arquivo_config=None
):
    """
    Executa uma consulta SQL/VQL e exporta o resultado.

    Parameters
    ----------
    banco : str                 - Nome do banco cadastrado no config.json.
    consulta : str              - Caminho do arquivo .sql ou .vql.
    saida : str                 - Arquivo de saída (.csv, .xlsx ou .parquet).
    separador : str             - Separador para arquivos CSV.
    chunksize : int | None      - Tamanho dos lotes para leitura.
    parametros : dict | None    - Parâmetros da consulta.
    nome_planilha : str         - Nome base da planilha Excel.
    monitorar : bool            - Exibir progresso da execução.
    arquivo_config : str | None - Caminho de um JSON de configuração alternativo.

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
        # Repassa arquivo_config para a resolução
        cfg = obter_config_banco(banco, arquivo_config=arquivo_config)
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
            tempo_execucao=round(fim - inicio, 2)
        )

    finally:
        _fechar_conexao(engine)


def exportar_consulta_direto(
    host: str,
    porta: int | str,
    usuario: str,
    database_ou_service: str,
    consulta: str,
    saida: str,
    separador: str = DEFAULT_CSV_SEPARATOR,
    chunksize: int | None = None,
    parametros: dict | None = None,
    nome_planilha: str = DEFAULT_SHEET_NAME,
    monitorar: bool = True,
    banco_alias: str | None = None,
) -> ExportResult:
    """
    Executa uma consulta SQL/VQL conectando diretamente aos parâmetros informados
    (sem dependência de config.json) e exporta o resultado.

    Parameters
    ----------
    host : str                  - Endereço IP ou hostname do servidor.
    porta : int | str           - Porta da conexão: 1521 (Oracle) ou 9996 (Denodo).
    usuario : str               - Nome de usuário da conexão.
    database_ou_service : str   - Service Name (para Oracle) ou Database (para Denodo).
    consulta : str              - Caminho do arquivo .sql ou .vql.
    saida : str                 - Caminho do arquivo de saída (.csv, .xlsx, .parquet).
    separador : str             - Separador para arquivos CSV (padrão ';').
    chunksize : int | None      - Tamanho dos lotes para leitura particionada.
    parametros : dict | None    - Parâmetros da consulta.
    nome_planilha : str         - Nome da aba no Excel (para .xlsx).
    monitorar : bool            - Exibir progresso da exportação no terminal.
    banco_alias : str | None    - Rótulo customizado para identificar a credencial no cofre.

    Returns
    -------
    ExportResult
    """
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
        alias, cfg = montar_e_validar_config_direta(
            host=host,
            porta=porta,
            usuario=usuario,
            database_ou_service=database_ou_service,
            banco_alias=banco_alias,
        )
        engine = criar_conexao(cfg)
        sql = carregar_consulta(consulta)
        chunks = executar_consulta(
            engine=engine,
            consulta=sql,
            chunksize=chunksize,
            parametros=parametros,
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
                tempo_execucao=fim - inicio,
            )

        return ExportResult(
            arquivo=saida,
            formato=extensao[1:],
            banco=alias,
            consulta=consulta,
            linhas=linhas,
            abas=abas,
            chunksize=chunksize,
            tempo_execucao=round(fim - inicio, 2),
        )

    finally:
        _fechar_conexao(engine)


def consultar_dataframe(
    banco,
    consulta,
    parametros=None,
    chunksize=None,
    dataframe="pandas",
    monitorar=True,
    arquivo_config=None
):
    """
    Executa uma consulta SQL/VQL e retorna DataFrame Pandas ou Polars.

    Parameters
    ----------
    banco : str                 - Nome do banco.
    consulta : str              - Arquivo SQL ou VQL.
    parametros : dict | None    - Parâmetros da consulta.
    chunksize : int | None      - Tamanho dos lotes.
    dataframe : str             - 'pandas' ou 'polars'.
    monitorar : bool            - Exibir progresso da execução.
    arquivo_config : str | None - Caminho de um JSON de configuração alternativo.

    Returns
    -------
    pandas.DataFrame | polars.DataFrame | Generator
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
    # Repassa arquivo_config para a resolução
    cfg = obter_config_banco(banco, arquivo_config=arquivo_config)
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
                resultado_polars = pl.from_pandas(resultado)
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
                    total_linhas += linhas_chunk
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
                _fechar_conexao(db_engine)

        return generator()

    except Exception:
        _fechar_conexao(db_engine)
        raise


def consultar_dataframe_direto(
    host: str,
    porta: int | str,
    usuario: str,
    database_ou_service: str,
    consulta: str,
    parametros: dict | None = None,
    chunksize: int | None = None,
    dataframe: str = "pandas",
    monitorar: bool = True,
    banco_alias: str | None = None,
):
    """
    Executa uma consulta SQL/VQL conectando diretamente aos parâmetros informados
    (sem dependência de config.json) e retorna um DataFrame (pandas ou polars).
    """
    consulta = normalizar_consulta(consulta)
    chunksize = normalizar_chunksize(chunksize)

    validar_consulta(consulta)
    validar_chunksize(chunksize)

    dataframe = dataframe.lower()
    if dataframe not in ("pandas", "polars"):
        raise ValueError("dataframe deve ser 'pandas' ou 'polars'")

    inicio = perf_counter()
    alias, cfg = montar_e_validar_config_direta(
        host=host,
        porta=porta,
        usuario=usuario,
        database_ou_service=database_ou_service,
        banco_alias=banco_alias,
    )
    db_engine = criar_conexao(cfg)

    try:
        sql = carregar_consulta(consulta)
        if chunksize is None:
            resultado = executar_consulta(
                engine=db_engine,
                consulta=sql,
                parametros=parametros,
                chunksize=None,
            )
            if resultado is None:
                return None

            if dataframe == "polars":
                import polars as pl
                resultado_polars = pl.from_pandas(resultado)
                fim = perf_counter()
                if monitorar:
                    imprimir_dataframe(
                        df=resultado_polars,
                        tempo_execucao=(fim - inicio),
                        dataframe="polars",
                    )
                return resultado_polars

            fim = perf_counter()
            if monitorar:
                imprimir_dataframe(
                    df=resultado,
                    tempo_execucao=(fim - inicio),
                    dataframe="pandas",
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
                    chunksize=chunksize,
                ):
                    numero_chunk += 1
                    linhas_chunk = len(chunk)
                    total_linhas += linhas_chunk
                    if monitorar:
                        imprimir_chunk(
                            numero_chunk=numero_chunk,
                            linhas_chunk=linhas_chunk,
                            total_linhas=total_linhas,
                            memoria_chunk=memoria_dataframe(chunk),
                        )

                    if dataframe == "polars":
                        import polars as pl
                        yield pl.from_pandas(chunk)
                    else:
                        yield chunk

            finally:
                _fechar_conexao(db_engine)

        return generator()

    except Exception:
        _fechar_conexao(db_engine)
        raise
