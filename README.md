# db_extractor

Biblioteca Python para extração de dados de Oracle e Denodo com exportação para CSV, XLSX e Parquet.

## Funcionalidades

* Conexão com bancos Oracle
* Conexão com Denodo
* Execução de consultas SQL e VQL
* Exportação para CSV
* Exportação para XLSX
* Exportação para Parquet
* Retorno como DataFrame Pandas
* Retorno como DataFrame Polars
* Suporte a leitura em lotes (chunks)
* Suporte a parâmetros de consulta
* Monitoramento de memória
* Monitoramento de progresso
* Divisão automática de planilhas Excel quando excedido o limite de linhas
* Localização automática do arquivo `config.json`
* API simplificada para uso em projetos Python

---

## Instalação

### Instalação local

```bash
pip install .
```

### Instalação em modo desenvolvimento

```bash
pip install -e .
```

### Gerando e instalando wheel

```bash
python -m build 
pip install db_extractor-py3-none-any.whl
```

### Dependências

A biblioteca instala automaticamente:

* pandas
* sqlalchemy
* oracledb
* psycopg2
* openpyxl
* pyarrow
* polars

---

## Estrutura do Projeto

```text
db_extractor/
│
├── pyproject.toml
├── README.md
├── config_example.json
│
├── src/
│   └── db_extractor/
│       │
│       ├── extractor.py
│       ├── credentials.py
│       ├── _config.py
│       ├── _constants.py
│       ├── _exceptions.py
│       ├── _version.py
│       │
│       ├── connection/
│       ├── query/
│       ├── output/
│       ├── utils/
│       └── models/
│
└── tests/
```

---

## Configuração

A biblioteca procura o arquivo `config.json` na seguinte ordem:

1. Variável de ambiente `DB_EXPORT_CONFIG`
2. Diretório do script principal
3. Diretório atual de execução

Exemplo:

```json
{
    "ORACLE_1": {
        "user": "usuario",
        "host": "host",
        "port": "1521",
        "service": "service"
    },

    "ORACLE_2": {
        "user": "usuario",
        "host": "host",
        "port": "1521",
        "service": "service"
    },

    "ORACLE_3": {
        "user": "usuario",
        "host": "host",
        "port": "1521",
        "service": "service"
    },

    "DENODO": {
        "user": "usuario",
        "host": "host",
        "port": "9996",
        "database": "database"
    }
}
```

---

## Funções de Extração

### Funções Principais

* Função de exportação gera o arquivo de saída
* Função que retorna o dataframe polars e pandas

```python
def exportar_consulta(
    banco,                  *Nome do banco no config
    consulta,               *Nome ou caminho do arquivo sql, vql
    saida,                  *Nome ou caminho do arquivo de saida
    separador=";",          Separador, para arquivos csv
    chunksize=None,         Extração por chunks
    parametros=None,        Parâmetros da consulta SQL
    nome_planilha="Dados",  Nome da planliha base, para arquivos xlsx
    monitorar=True          Habilitar Progresso True, False
)
def consultar_dataframe(
    banco,                  *Nome do banco no config
    consulta,               *Nome ou caminho do arquivo sql, vql
    chunksize=None,         Extração por chunks
    parametros=None,        Parâmetros da consulta SQL
    dataframe="pandas",     Bibliteca que retorna o df polars, pandas
    monitorar=True          Habilitar Progresso True, False
)
```

### Funções de credeciais

* Função de cadastro de credencial
* Função de alteração de senha de um cadastro já existente
* Função de remoção de uma credencial
* Função de listagem de credenciais

```python
def cadastrar_credencial(
    banco,                  *Nome do banco no config
    usuario=None,           Usuário (opcional, busca do config.json)
    senha=None              Senha (opcional, solicita no terminal)
)

def alterar_senha(
    banco,                  *Nome do banco no config
    usuario=None,           Usuário (opcional, busca do config.json)
    nova_senha=None         Nova senha (opcional, solicita no terminal)
)

def remover_credencial(
    banco,                  *Nome do banco no config
    usuario=None            Usuário (opcional, busca do config.json)
)

def listar_credenciais()
```

### Versionamento

```python
print(db_extractor.__version__)
print(db_extractor.__title__)
print(db_extractor.__author__)
print(db_extractor.__description__)
```

---

## Segurança e Gerenciamento de Senhas (Keyring)

Para evitar senhas gravadas em texto plano no `config.json`, a biblioteca suporta o armazenamento seguro através do **keyring** (Windows Credential Locker).
O cofre armazena as credenciais isoladas por banco utilizando a convenção de serviço db_extractor_<NOME_BANCO> associada ao respectivo usuário.

Não é obrigatório cadastrar a senha previamente:

* Ao executar exportar_consulta() ou consultar_dataframe(), a biblioteca busca a credencial no cofre do sistema.
* Caso a credencial não exista, o terminal solicitará a senha de forma oculta com máscara (*) e a gravará no cofre automaticamente.
* Nas execuções seguintes, a autenticação ocorre de forma silenciosa e transparente.

Trava de Proteção Contra Bloqueio de Conta:

* Para evitar o bloqueio de usuários no banco de dados corporativo (erros como ORA-28000: the account is locked)
* Antes de processar consultas pesadas, a biblioteca realiza um teste atômico prévio de autenticação com timeout reduzido (SELECT 1).

Se a senha estiver incorreta:

* A credencial inválida é imediatamente expurgada do cofre para evitar repetições involuntárias.
* O terminal concede uma única tentativa interativa de correção.
* Se a nova senha também falhar, a execução é interrompida imediatamente, impedindo sucessivas tentativas que levariam ao bloqueio do usuário.

---

## Uso Básico

### Exportação para CSV

```python
from db_extractor import exportar_consulta

resultado = exportar_consulta(
    banco="ORACLE_1",
    consulta="Municipios.sql",
    saida="Municipios.csv",
    separador=";"
)
print(resultado)
```

---

### Exportação para XLSX

```python
from db_extractor import exportar_consulta

resultado = exportar_consulta(
    banco="ORACLE_1",
    consulta="Municipios.sql",
    saida="Municipios.xlsx",
    nome_planilha="Municipios"
)
print(resultado)
```

---

### Exportação para Parquet

```python
from db_extractor import exportar_consulta

resultado = exportar_consulta(
    banco="ORACLE_1",
    consulta="Municipios.sql",
    saida="Municipios.parquet"
)
print(resultado)
```

---

### Exportação DataFrame

```python
from db_extractor import consultar_dataframe

df = consultar_dataframe(
    banco="ORACLE_1",
    consulta="Municipios.sql",
    parametros={
        "UF": "PR"
    }
)
print(df.head())
```

---

### Uso com Chunks

Para consultas grandes:

```python
resultado = exportar_consulta(
    banco="ORACLE_1",
    consulta="Municipios.sql",
    saida="Municipios.parquet",
    chunksize=50000
)
for chunk in consultar_dataframe(
    banco="ORACLE_1",
    consulta="Municipios.sql",
    chunksize=50000
):
    print(chunk.shape)
```

---

### Uso com Parâmetros

Consulta SQL:

```sql
SELECT *
FROM CLIENTES
WHERE MES = :MES
AND ANO = :ANO
```

Execução:

```python
resultado = exportar_consulta(
    banco="ORACLE_1",
    consulta="Clientes.sql",
    saida="Clientes.xlsx",
    parametros={
        "MES": 6,
        "ANO": 2026
    }
)
```

```sql
SELECT
    COD_MUN_MUN AS "CODIGO_MUN",
    NOM_MUN_MUN AS "MUNICIPIO"
FROM TAB_MUNICIPIO
WHERE COD_MUN_MUN IN ({CODIGOS})
```

Execução:

```python
df = consultar_dataframe(
    banco="ORACLE_2",
    consulta="Municipios.sql",
    parametros={
        "CODIGOS": [
            "04118204",
            "04106902",
            "04104808"
        ]
    }
)
```

---

## Excel e Limite de Linhas

O Excel suporta no máximo:

```text
1.048.576 linhas por planilha
```

A biblioteca realiza automaticamente a divisão em múltiplas abas.

Exemplo:

```python
resultado = exportar_consulta(
    banco="ORACLE_1",
    consulta="GrandesVolumes.sql",
    saida="GrandesVolumes.xlsx",
    nome_planilha="Dados"
)
```

Resultado:

```text
Dados
Dados_1
Dados_2
Dados_3
...
```

---

## Objeto de Retorno

A função retorna um objeto `ExportResult`.

Exemplo:

```python
print(resultado)
```

Saída:

```text
ExportResult(
    arquivo='Municipios.xlsx',
    formato='xlsx',
    banco='ORACLE_1',
    consulta='Municipios.sql',
    linhas=2534871,
    abas=3,
    chunksize=50000,
    tempo_execucao=48.72
)
```

---

## Exceções

A biblioteca fornece exceções específicas.

Exemplo:

```python
from db_extractor import (exportar_consulta, BancoNaoEncontrado)

try:
    exportar_consulta(...)
except BancoNaoEncontrado as e:
    print(e)
```

Exceções disponíveis:

* DBExtractorError
* BancoNaoEncontrado
* ConsultaNaoEncontrada
* ConfigNaoEncontrado
* ConexaoNaoIdentificado
* FormatoConsultaInvalido
* FormatoSaidaInvalido
* ChunksizeInvalido
* NomePlanilhaInvalido

---

## Bancos Suportados

### Oracle

Configuração:

```json
{
    "ORACLE_2": {
        "user": "usuario",
        "password": "senha",
        "host": "host",
        "port": "1521",
        "service": "service"
    }
}
```

---

### Denodo

Configuração:

```json
{
    "DENODO": {
        "user": "usuario",
        "password": "senha",
        "host": "host",
        "port": "9996",
        "database": "database"
    }
}
```

---

## Licença

Uso interno corporativo COPEL.
