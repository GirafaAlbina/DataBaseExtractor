import os
from time import perf_counter
import pandas as pd

from ._constants import DEFAULT_CSV_SEPARATOR, DEFAULT_SHEET_NAME
from .connection import ConexaoPreparada, PoolSessao
from .models import ExportResult
from .output import exportar_csv, exportar_parquet, exportar_xlsx
from .query import carregar_consulta, preparar_sql_e_binds
from .utils import (
    imprimir_dataframe,
    imprimir_exportacao,
    normalizar_banco,
    normalizar_chunksize,
    normalizar_consulta,
    normalizar_nome_planilha,
    normalizar_saida,
    resolver_saida,
    validar_chunksize,
    validar_consulta,
    validar_nome_planilha,
    validar_saida,
)


class SessaoExtracao:
    """Gerenciador de contexto público para extração com sessão e cursores persistentes."""

    def __init__(
        self,
        banco: str,
        min_workers: int = 1,
        max_workers: int = 4,
        arraysize: int = 50_000,
        arquivo_config: str | None = None,
        usuario: str | None = None,
    ):
        self.banco = normalizar_banco(banco)
        self._gerenciador_pool = PoolSessao(
            banco=self.banco,
            min_workers=min_workers,
            max_workers=max_workers,
            arraysize=arraysize,
            arquivo_config=arquivo_config,
            usuario=usuario,
        )

    def __enter__(self) -> "SessaoExtracao":
        self._gerenciador_pool.iniciar()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._gerenciador_pool.encerrar()

    def adquirir_conexao(self) -> ConexaoPreparada:
        """Retorna a conexão preparada vinculada à thread atual (usado pelo parallel.py)."""
        return self._gerenciador_pool.adquirir_conexao()

    def resolver_sql(self, consulta: str) -> str:
        """Aceita caminho de arquivo .sql/.vql ou string SQL direta."""
        if os.path.isfile(consulta) or consulta.strip().lower().endswith((".sql", ".vql")):
            arq = normalizar_consulta(consulta)
            validar_consulta(arq)
            return carregar_consulta(arq)
        return consulta

    def consultar_dataframe(
        self,
        consulta: str,
        parametros: dict | None = None,
        chunksize: int | None = None,
        dataframe: str = "pandas",
        monitorar: bool = False,
    ):
        """Executa consulta reaproveitando a conexão e o cursor preparado da sessão."""
        dataframe = dataframe.lower()
        if dataframe not in ("pandas", "polars"):
            raise ValueError("dataframe deve ser 'pandas' ou 'polars'")

        chunksize = normalizar_chunksize(chunksize)
        validar_chunksize(chunksize)

        inicio = perf_counter()
        sql_base = self.resolver_sql(consulta)
        sql_final, binds = preparar_sql_e_binds(sql_base, parametros)

        cursor = self.adquirir_conexao().executar(sql_final, binds)
        colunas = [desc[0] for desc in cursor.description]

        if chunksize is not None:
            def _generator():
                while True:
                    linhas = cursor.fetchmany(chunksize)
                    if not linhas:
                        break
                    if dataframe == "polars":
                        import polars as pl
                        yield pl.DataFrame(linhas, schema=colunas, orient="row")
                    else:
                        yield pd.DataFrame(linhas, columns=colunas)
            return _generator()

        linhas = cursor.fetchall()
        if dataframe == "polars":
            import polars as pl
            df_pl = pl.DataFrame(linhas, schema=colunas, orient="row")
            if monitorar:
                imprimir_dataframe(df=df_pl, tempo_execucao=perf_counter() - inicio, dataframe="polars")
            return df_pl

        df_pd = pd.DataFrame(linhas, columns=colunas)
        if monitorar:
            imprimir_dataframe(df=df_pd, tempo_execucao=perf_counter() - inicio, dataframe="pandas")
        return df_pd

    def exportar_consulta(
        self,
        consulta: str,
        saida: str,
        separador: str = DEFAULT_CSV_SEPARATOR,
        chunksize: int | None = 100_000,
        parametros: dict | None = None,
        nome_planilha: str = DEFAULT_SHEET_NAME,
        compression: str = "snappy",
        downcast: bool = True,
        monitorar: bool = True,
    ) -> ExportResult:
        """Exporta arquivo (.csv, .xlsx ou .parquet) reaproveitando a sessão ativa."""
        saida = resolver_saida(normalizar_saida(saida))
        chunksize = normalizar_chunksize(chunksize)
        nome_planilha = normalizar_nome_planilha(nome_planilha)

        validar_saida(saida)
        validar_chunksize(chunksize)
        validar_nome_planilha(nome_planilha)

        inicio = perf_counter()
        sql_base = self.resolver_sql(consulta)
        sql_final, binds = preparar_sql_e_binds(sql_base, parametros)

        cursor = self.adquirir_conexao().executar(sql_final, binds)
        colunas = [desc[0] for desc in cursor.description]
        extensao = os.path.splitext(saida)[1].lower()
        abas = 1

        def _chunks_tuplas():
            while True:
                linhas = cursor.fetchmany(chunksize or 100_000)
                if not linhas:
                    break
                yield linhas

        def _chunks_pandas():
            for linhas in _chunks_tuplas():
                yield pd.DataFrame(linhas, columns=colunas)

        if extensao == ".parquet":
            linhas = exportar_parquet(
                _chunks_tuplas(),
                arquivo_saida=saida,
                compression=compression,
                downcast=downcast,
                colunas=colunas,
            )
        elif extensao == ".csv":
            linhas = exportar_csv(chunks=_chunks_pandas(), arquivo_saida=saida, separador=separador)
        elif extensao == ".xlsx":
            res = exportar_xlsx(chunks=_chunks_pandas(), arquivo_saida=saida, nome_planilha=nome_planilha)
            linhas, abas = res["linhas"], res["abas"]
        else:
            raise ValueError(f"Formato não suportado: {extensao}")

        fim = perf_counter()
        if monitorar:
            imprimir_exportacao(arquivo=saida, linhas=linhas, tempo_execucao=fim - inicio)

        return ExportResult(
            arquivo=saida,
            formato=extensao[1:],
            banco=self.banco,
            consulta=consulta,
            linhas=linhas,
            abas=abas,
            chunksize=chunksize,
            tempo_execucao=round(fim - inicio, 2),
        )


def abrir_sessao(
    banco: str,
    min_workers: int = 1,
    max_workers: int = 4,
    arraysize: int = 50_000,
    arquivo_config: str | None = None,
    usuario: str | None = None,
) -> SessaoExtracao:
    """Abre um gerenciador de contexto com Pool de Conexões e Cache de Cursores Preparados."""
    return SessaoExtracao(
        banco=banco,
        min_workers=min_workers,
        max_workers=max_workers,
        arraysize=arraysize,
        arquivo_config=arquivo_config,
        usuario=usuario,
    )
