# Lógica das consultas e origem dos dados

Esta seção descreve o comportamento implementado em [database.py](../modulos/database.py), [bot.py](../modulos/bot.py), [margem_departamento.py](../modulos/margem_departamento.py) e [leitor_barras.py](../modulos/leitor_barras.py). Mudanças nas consultas devem ser acompanhadas da atualização desta documentação.

As consultas Oracle são somente de leitura e usam os nomes das tabelas **sem prefixo de esquema**. O usuário configurado precisa ter acesso às tabelas diretamente ou por sinônimos. Parâmetros são enviados por bind, como `:CODPROD`, sem concatenar o texto digitado ao SQL. Os nomes dos campos da busca por código são escolhidos de uma lista fixa permitida. `executar_consulta` abre uma conexão, executa o SELECT e devolve os registros como dicionários com chaves em minúsculas.

### Mapa das tabelas

| Tabela | Campos utilizados | Finalidade |
|---|---|---|
| `PCPRODUT` | `CODPROD`, `DESCRICAO`, `CODAUXILIAR`, `CODAUXILIAR2`, `CODEPTO` | Identificação, descrição, códigos de busca e departamento do produto. |
| `PCTABPR` | `CODPROD`, `NUMREGIAO`, `PVENDA`, `PTABELA` | Preço de venda e preço programado por região/tabela. |
| `PCREGIAO` | `NUMREGIAO`, `REGIAO`, `STATUS` | Nome e situação da região/tabela de preços. |
| `PCEST` | `CODPROD`, `CODFILIAL`, `CUSTOREAL`, `CUSTOULTENT`, `DTULTENT` | Custos e data da última entrada por filial. |
| `PCMOV` | `CODPROD`, `NUMTRANSENT` | Ligação do produto com as transações de entrada. |
| `PCNFENT` | `NUMTRANSENT`, `CODFILIAL`, `NUMNOTA`, `CODFORNEC`, `DTENT`, `DTEMISSAO` | Identificação e datas da nota de entrada. |
| `PCFORNEC` | `CODFORNEC`, `FORNECEDOR` | Nome do fornecedor da entrada localizada. |
| `PCDEPTO` | `CODEPTO`, `DESCRICAO` | Busca e identificação do departamento no comando `/margem`. |
| `DUAL` | Constante `1` | Teste inicial de conexão Oracle. |

### 1. Consulta por código: CODPROD, CODAUXILIAR e CODAUXILIAR2

Entrada: mensagem com números ASCII, por exemplo `6`. O código é convertido para inteiro antes de ser usado nos binds. As permissões do usuário definem quais comparações entram no `WHERE`:

| Permissão | Comparação |
|---|---|
| `buscar_codprod` | `PCPRODUT.CODPROD = :CODPROD` |
| `buscar_codauxiliar` | `PCPRODUT.CODAUXILIAR = :CODAUXILIAR` |
| `buscar_codauxiliar2` | `PCPRODUT.CODAUXILIAR2 = :CODAUXILIAR2` |

Se houver mais de um campo habilitado, as comparações são ligadas por **OR**, todas com o mesmo código informado. A permissão-base `consulta_preco` também é exigida. Sem campo autorizado, nenhuma consulta de produto é executada.

Relacionamentos da consulta:

```sql
FROM PCPRODUT P
JOIN PCTABPR T ON T.CODPROD = P.CODPROD
JOIN PCREGIAO R ON R.NUMREGIAO = T.NUMREGIAO
WHERE (
    P.CODPROD = :CODPROD
    OR P.CODAUXILIAR = :CODAUXILIAR
    OR P.CODAUXILIAR2 = :CODAUXILIAR2
)
AND R.STATUS = 'A'
ORDER BY R.NUMREGIAO
```

O trecho mostra os três campos habilitados. Na execução, entram apenas os campos autorizados para aquela busca.

Retorno: `P.CODPROD`, `P.DESCRICAO`, `R.NUMREGIAO`, `R.REGIAO AS NOME_TABELA`, `T.PTABELA` e `T.PVENDA`. A mensagem apresenta `PVENDA` como preço de venda e `PTABELA` como programado. Não existe filtro de filial nessa consulta de preços.

Os JOINs são internos: um produto sem registro de preço ou sem região com `STATUS = 'A'` não aparece, mesmo que exista em `PCPRODUT`. O retorno pode conter várias regiões. O filtro não exige que `PVENDA` seja positivo; essa validação é aplicada no cálculo de margem, quando necessário. Não há `ROWNUM` limitando esta consulta nem uma etapa de escolha se o OR encontrar códigos em produtos distintos; a mensagem utiliza a lista retornada e a identificação do primeiro registro.

### 2. Consulta por foto do código de barras

Exige `consulta_preco` e `buscar_por_foto`. A imagem é baixada em memória e decodificada com OpenCV e ZXing; não é enviada ao Oracle nem salva como arquivo pelo fluxo de consulta.

Tentativas de leitura: imagem original, tons de cinza, contraste CLAHE, ampliação de 1,5 e 2 vezes e recortes em faixas. O leitor tenta rotação, redução e inversão. Aceita o primeiro resultado numérico ASCII com 8, 12, 13 ou 14 dígitos. Essa validação verifica formato e comprimento, sem uma validação adicional de dígito verificador implementada pelo projeto.

Depois da leitura, o código entra na mesma consulta de preços da seção anterior, mas somente nas comparações:

```sql
P.CODAUXILIAR = :CODAUXILIAR OR P.CODAUXILIAR2 = :CODAUXILIAR2
```

O fluxo por foto não compara `CODPROD` e não exige separadamente as permissões de busca manual `buscar_codauxiliar` e `buscar_codauxiliar2`. Sem código identificado, não consulta o banco.

### 3. Pesquisa por nome e seleção do produto

Exige `consulta_preco` e pelo menos três caracteres. Usa os mesmos JOINs de `PCPRODUT`, `PCTABPR` e `PCREGIAO`, com:

```sql
R.STATUS = 'A'
AND UPPER(P.DESCRICAO) LIKE :NOME
```

O bind `NOME` recebe `%` + termo em maiúsculas + `%`. A busca ignora diferença entre maiúsculas e minúsculas, mas não implementa remoção de acentos. Caracteres `%` e `_` digitados mantêm a semântica de curingas do `LIKE`.

Seleciona `DISTINCT P.CODPROD, P.DESCRICAO`, ordena por descrição e código e aplica `ROWNUM <= 11` na consulta externa. O bot mostra até dez botões; o 11º registro permite avisar que há mais resultados. Ao clicar, consulta preços somente por `P.CODPROD`, revalidando `consulta_preco`; não exige `buscar_codprod` separadamente nesse fluxo.

### 4. Custos e dados da última entrada

Depois de localizar o produto, `consultar_custos` é executada se houver permissão `ver_custos` ou `ver_margem_produto`. Recebe o `CODPROD` do primeiro registro da consulta de preços, sem usar diretamente o código de barras como código interno.

A consulta principal relaciona `PCPRODUT P` e `PCEST E` por `E.CODPROD = P.CODPROD`, filtra `P.CODPROD = :CODPROD_PRINCIPAL` e ordena por `E.CODFILIAL`. Retorna as filiais com registro em `PCEST`; não filtra saldo de estoque ou uma filial específica. Retorna `E.CUSTOREAL`, `E.CUSTOULTENT` e `E.DTULTENT`. A mensagem e os cálculos atuais usam **CUSTOULTENT**, não `CUSTOREAL`.

Para localizar a nota de entrada, a CTE `ULTIMA_NF` faz:

| Ligação/filtro | Comparação |
|---|---|
| Movimento com nota | `PCMOV.NUMTRANSENT = PCNFENT.NUMTRANSENT` |
| Estoque do produto | `PCEST.CODPROD = PCMOV.CODPROD` |
| Mesma filial | `PCEST.CODFILIAL = PCNFENT.CODFILIAL` |
| Produto desejado | `PCMOV.CODPROD = :CODPROD_CTE` |
| Dia da última entrada | `TRUNC(PCNFENT.DTENT) = TRUNC(PCEST.DTULTENT)` |

Os dois binds de produto recebem o mesmo `CODPROD`. A CTE usa `ROW_NUMBER()` particionado por produto e filial, ordenado por `PCNFENT.DTENT DESC, PCNFENT.NUMTRANSENT DESC`. A consulta principal usa `LEFT JOIN` com `RN = 1`, produto e filial iguais. Assim, a falta de uma nota correspondente não elimina o registro de custo.

O fornecedor é obtido por `LEFT JOIN PCFORNEC F ON F.CODFORNEC = U.CODFORNEC`. Os dados mostrados, quando encontrados, são número da nota (`NUMNOTA`), código/nome do fornecedor (`CODFORNEC`, `FORNECEDOR`), emissão (`DTEMISSAO`) e transação (`NUMTRANSENT`). A data exibida como última entrada vem de `PCEST.DTULTENT`.

O SQL atual não adiciona filtros de cancelamento, tipo de operação ou quantidade de movimento. A nota escolhida é a mais recente entre as que atendem ao produto, filial e dia descritos acima. Valores de custo são exibidos com cinco casas decimais. Dados de custo e nota só são mostrados com `ver_custos`; poder calcular margem não libera sua exibição.

### 5. Margem do produto

Exige `ver_margem_produto`. O bloco **MARGEM DO PRODUTO** é separado dos custos e combina cada preço `PCTABPR.PVENDA` retornado com `PCEST.CUSTOULTENT` de cada filial retornada pela consulta de custos:

```text
Margem do produto (%) = ((PVENDA - CUSTOULTENT) / PVENDA) × 100
```

O cálculo usa `Decimal` e apresenta duas casas decimais. Exemplo: preço `18,29`, custo `13,59` → margem `25,70%`. Preço ou custo nulo, ou preço menor ou igual a zero, produz “Indisponível”. Custo zero é aceito; não há filtro específico de custo negativo. Margens negativas podem ocorrer quando o custo excede o preço.

Não desconta impostos/despesas adicionais nem usa o preço programado `PTABELA`. Não é markup sobre o custo. Uma falha na consulta complementar de custos/margem é informada sem descartar os preços já encontrados.

### 6. Margem média do departamento na consulta do produto

Exige `ver_margem_departamento`, independentemente de `ver_margem_produto` e `ver_custos`. Executada por `consultar_margens_departamento_produto` após a consulta de preços.

1. Obtém o departamento por `SELECT CODEPTO FROM PCPRODUT WHERE CODPROD = :CODPROD`.
2. Seleciona os produtos com `P.CODEPTO` igual ao departamento encontrado.
3. Relaciona `PCTABPR` pelo `CODPROD`, `PCREGIAO` pelo `NUMREGIAO` e `PCEST` pelo `CODPROD`.
4. Exige `R.STATUS = 'A'`, `T.PVENDA > 0` e `E.CUSTOULTENT IS NOT NULL`.
5. Restringe regiões por `EXISTS` em `PCTABPR TP`, comparando `TP.CODPROD = :CODPROD` e `TP.NUMREGIAO = T.NUMREGIAO`.
6. Restringe filiais por `EXISTS` em `PCEST EP`, comparando `EP.CODPROD = :CODPROD` e `EP.CODFILIAL = E.CODFILIAL`.
7. Agrupa por `P.CODEPTO, E.CODFILIAL, T.NUMREGIAO, R.REGIAO` e ordena por filial e região.

Cada grupo retorna `SUM(T.PVENDA) AS TOTAL_PRECOS`, `SUM(E.CUSTOULTENT) AS TOTAL_CUSTOS` e `COUNT(*) AS PRODUTOS_VALIDOS`. O parâmetro é o código interno do produto localizado. O custo zero participa; custo nulo e preço não positivo ficam fora. Os `EXISTS` exigem registro do produto consultado naquela região/filial, não saldo positivo em estoque.

```text
Margem do mix (%) = ((TOTAL_PRECOS - TOTAL_CUSTOS) / TOTAL_PRECOS) × 100
```

Embora a mensagem use “margem média”, o cálculo é a **margem global das somas**, equivalente à média das margens ponderada pelo preço de cada produto, e não a média aritmética simples dos percentuais. Considera uma unidade por produto válido em cada filial/região, sem ponderação por vendas ou estoque. O resumo exibe departamento, filial, nome da tabela, margem e quantidade considerada, sem revelar os totais de custo. Não depende de `PCDEPTO`, pois identifica o departamento pelo código em `PCPRODUT`.

Se não houver dados válidos, informa a ausência. Se esta consulta falhar, os preços e os outros blocos já calculados continuam sendo enviados.

### 7. Análise de departamento pelo comando `/margem`

Exige `ver_margem_departamento` e conversa privada. As etapas de seleção são:

| Etapa | Tabelas, campos e comparações |
|---|---|
| Departamento por código | `PCDEPTO.CODEPTO = :COD`; retorna `CODEPTO, DESCRICAO`. |
| Departamento por código textual/nome | `TO_CHAR(D.CODEPTO) = :COD OR UPPER(D.DESCRICAO) LIKE :TERMO`; `TERMO` recebe `%texto em maiúsculas%`. Ordena descrição/código e busca até 21 para mostrar até 20 opções. |
| Filiais disponíveis | `PCEST E JOIN PCPRODUT P ON P.CODPROD = E.CODPROD`, com `P.CODEPTO = :DEPTO`; retorna `DISTINCT E.CODFILIAL`, ordenado por filial. Não exige saldo positivo. |
| Regiões disponíveis | `PCREGIAO R JOIN PCTABPR T ON T.NUMREGIAO = R.NUMREGIAO JOIN PCPRODUT P ON P.CODPROD = T.CODPROD`, com `R.STATUS = 'A' AND P.CODEPTO = :DEPTO`; retorna código/nome distintos, ordenados por região. A seleção de regiões não filtra filial nessa etapa. |

Após escolher filial e todas as regiões ou uma região específica, `calcular_margens_departamento` cria a CTE `BASE` com estes filtros:

```sql
FROM PCPRODUT P
JOIN PCTABPR T ON T.CODPROD = P.CODPROD
JOIN PCREGIAO R ON R.NUMREGIAO = T.NUMREGIAO
JOIN PCEST E ON E.CODPROD = P.CODPROD
WHERE P.CODEPTO = :DEPTO
  AND E.CODFILIAL = :FILIAL
  AND R.STATUS = 'A'
  AND (:REGIAO IS NULL OR T.NUMREGIAO = :REGIAO)
```

`REGIAO = NULL` considera todas as tabelas ativas, **separadamente**. O agrupamento externo é `NUMREGIAO, NOME_TABELA`; a filial já foi filtrada. Para cada grupo:

| Resultado | Regra |
|---|---|
| `TOTAL_PRODUTOS` | `COUNT(*)` das linhas da base. |
| `PRODUTOS_VALIDOS` | Conta linhas com `PVENDA > 0 AND CUSTOULTENT IS NOT NULL`. |
| `SEM_PRECO` | Conta `PVENDA IS NULL OR PVENDA <= 0`. |
| `SEM_CUSTO` | Conta `CUSTOULTENT IS NULL`. |
| `CUSTO_ZERO` | Conta `CUSTOULTENT = 0`. |
| `TOTAL_PRECOS` | Soma `PVENDA` somente dos produtos válidos. |
| `TOTAL_CUSTOS` | Soma `CUSTOULTENT` somente dos mesmos produtos válidos. |

Usa a fórmula da margem do mix descrita na seção anterior, com duas casas decimais. Totais de preço não positivos tornam a margem indisponível. A diferença bruta é `TOTAL_PRECOS - TOTAL_CUSTOS`. Sem `ver_custos`, o relatório omite soma dos custos, diferença bruta e contagens detalhadas; mantém soma dos preços e margem global.

Os contadores usam linhas dos JOINs, não `COUNT(DISTINCT CODPROD)`. A interpretação de uma unidade por produto pressupõe registros únicos por produto/região em `PCTABPR` e por produto/filial em `PCEST`. A análise não calcula lucro realizado, não usa quantidade vendida ou estoque e não aplica descontos tributários/despesas adicionais.

### 8. Testes de conexão e indicadores do painel

O indicador Oracle abre uma conexão com timeout TCP de 5 segundos e timeout de chamada de 5 segundos. Primeiro executa `SELECT 1 FROM DUAL`. Depois executa a mesma consulta de preços com código `0`, os três campos de busca e a condição adicional `WHERE 1=0 AND (...)`, sem recuperar produtos. O teste do painel possui limite assíncrono de 12 segundos.

Somente passar pelos dois passos produz **ORACLE: OK**. `ORA-00942` ou `ORA-01031` no segundo passo gera uma mensagem específica de falta de acesso às tabelas/sinônimos. O teste não valida antecipadamente `PCEST`, `PCMOV`, `PCNFENT`, `PCFORNEC` ou `PCDEPTO`: custos e departamentos ainda podem falhar mesmo com o indicador verde.

O indicador Telegram usa a API `getMe`, com o token salvo e limite assíncrono de 12 segundos. **TELEGRAM: OK** indica resposta válida da API; não garante que o processo de polling tenha sido reiniciado após uma troca de token. Não consulta tabelas Oracle. Os indicadores atualizam ao entrar no painel, ao salvar a seção correspondente, ao clicar e periodicamente a cada minuto com a página visível.

### 9. Acesso local e rastreamento no terminal

Permissões são verificadas nos JSONs locais antes das consultas; não são permissões do usuário Oracle. O acesso ao bot exige perfil aprovado e as permissões específicas descritas acima. O administrador principal possui acesso total, exceto quando um perfil de teste estiver ativo para seu ID. As permissões `ver_margem_produto`, `ver_margem_departamento` e `ver_custos` são independentes.

As linhas `CONSULTA` do terminal registram ID da atualização, ID/nome/username do Telegram, tipo e etapa da operação, código/termo ou filtros, quantidade de registros e duração em milissegundos. Para erros, registram tipo da exceção e códigos `ORA`, `DPI` ou `DPY`. Consultas complementares têm registros próprios; uma busca pode gerar logs de preços, custos e margem do departamento. Os logs específicos de consultas não registram token, senha, conteúdo da foto ou valores retornados de custo. Exceções também podem produzir traceback no terminal para diagnóstico.
