# Lógica das consultas e origem dos dados

Esta seção descreve o comportamento implementado em [database.py](../modulos/database.py), [bot.py](../modulos/bot.py), [margem_departamento.py](../modulos/margem_departamento.py) e [leitor_barras.py](../modulos/leitor_barras.py). Mudanças nas consultas devem ser acompanhadas da atualização desta documentação.

As consultas Oracle são somente de leitura e usam os nomes das tabelas **sem prefixo de esquema**. O usuário configurado precisa ter acesso às tabelas diretamente ou por sinônimos. Parâmetros são enviados por bind, como `:CODPROD`, sem concatenar o texto digitado ao SQL. Os nomes dos campos da busca por código são escolhidos de uma lista fixa permitida. `executar_consulta` abre uma conexão, executa o SELECT e devolve os registros como dicionários com chaves em minúsculas.

**Exclusão de produtos:** consultas que retornam produtos, custos, filiais/regiões de departamento ou agregações exigem `P.DTEXCLUSAO IS NULL`, sendo `P` o alias de `PCPRODUT`. Data preenchida exclui o produto das buscas e de todos os totais/contagens do departamento. A verificação `produto_existe` usa o mesmo filtro, para não confundir produto excluído com produto apenas sem preço. O catálogo administrativo de todas as filiais/tabelas e o cadastro `PCDEPTO` não são filtrados por essa regra.

### Mapa das tabelas

| Tabela | Campos utilizados | Finalidade |
|---|---|---|
| `PCPRODUT` | `CODPROD`, `DESCRICAO`, `CODAUXILIAR`, `CODAUXILIAR2`, `CODEPTO`, `DTEXCLUSAO` | Identificação, descrição, códigos de busca, departamento e exclusão do produto. |
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
AND P.DTEXCLUSAO IS NULL
ORDER BY R.NUMREGIAO
```

O trecho mostra os três campos habilitados. Na execução, entram apenas os campos autorizados para aquela busca.

Retorno: `P.CODPROD`, `P.DESCRICAO`, `R.NUMREGIAO`, `R.REGIAO AS NOME_TABELA`, `T.PTABELA` e `T.PVENDA`. A mensagem apresenta `PVENDA` como preço de venda e `PTABELA` como programado. O preço é regional; quando houver restrição de filial, um `EXISTS` em `PCEST` exige que o produto tenha registro em uma filial autorizada.

Os JOINs são internos: um produto sem registro de preço ou sem região com `STATUS = 'A'` não aparece, mesmo que exista em `PCPRODUT`. O retorno pode conter várias regiões. A consulta exige `T.PVENDA > 0`: tabelas sem preço válido são omitidas. Não há `ROWNUM` limitando esta consulta nem uma etapa de escolha se o OR encontrar códigos em produtos distintos; a mensagem utiliza a lista retornada e a identificação do primeiro registro.

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
AND P.DTEXCLUSAO IS NULL
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

Nas mensagens, o resultado é chamado de **Lucro presumido sobre o custo**: uma estimativa bruta de ganho percentual (markup), sem apuração tributária. A fórmula abaixo permanece a mesma.

Exige `ver_margem_produto`. O bloco **MARGEM DO PRODUTO** é separado dos custos e combina cada preço `PCTABPR.PVENDA` retornado com `PCEST.CUSTOULTENT` de cada filial retornada pela consulta de custos:

```text
Ganho sobre o custo (%) = ((PVENDA - CUSTOULTENT) / CUSTOULTENT) × 100
```

O cálculo usa `Decimal` e apresenta duas casas decimais. Exemplo: preço `18,29`, custo `13,59` → ganho sobre o custo `34,58%`. Preço ou custo nulo, zero ou negativo produz “Indisponível”. O ganho é negativo quando a venda é positiva e fica abaixo do custo.

Não desconta impostos/despesas adicionais nem usa o preço programado `PTABELA`. O percentual é markup (ganho sobre o custo), e não margem sobre a venda. A opção de permissão continua chamada de margem no painel. Uma falha na consulta complementar de custos/margem é informada sem descartar os preços já encontrados.

A consulta individual não executa a agregação do departamento e não inclui seu lucro na resposta, mesmo com `ver_margem_departamento` habilitada. Essa permissão libera a análise separada pelo comando `/margem` e a fórmula de departamento pelo comando `/formula`.

### 6. Análise de departamento pelo comando `/margem`

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
  AND P.DTEXCLUSAO IS NULL
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

Usa a fórmula de ganho sobre o custo do mix descrita na seção anterior, com duas casas decimais. Totais de preço ou custo não positivos tornam o percentual indisponível. A diferença bruta é `TOTAL_PRECOS - TOTAL_CUSTOS`. Sem `ver_custos`, o relatório omite soma dos custos, diferença bruta e contagens detalhadas; mantém soma dos preços e ganho global sobre o custo.

Os contadores usam linhas dos JOINs, não `COUNT(DISTINCT CODPROD)`. A interpretação de uma unidade por produto pressupõe registros únicos por produto/região em `PCTABPR` e por produto/filial em `PCEST`. A análise não calcula lucro realizado, não usa quantidade vendida ou estoque e não aplica descontos tributários/despesas adicionais.

### 7. Testes de conexão e indicadores do painel

O indicador Oracle abre uma conexão com timeout TCP de 5 segundos e timeout de chamada de 5 segundos. Primeiro executa `SELECT 1 FROM DUAL`. Depois executa a mesma consulta de preços com código `0`, os três campos de busca e a condição adicional `WHERE 1=0 AND (...)`, sem recuperar produtos. O teste do painel possui limite assíncrono de 12 segundos.

Somente passar pelos dois passos produz **ORACLE: OK**. `ORA-00942` ou `ORA-01031` no segundo passo gera uma mensagem específica de falta de acesso às tabelas/sinônimos. O teste não valida antecipadamente `PCEST`, `PCMOV`, `PCNFENT`, `PCFORNEC` ou `PCDEPTO`: custos e departamentos ainda podem falhar mesmo com o indicador verde.

O indicador Telegram usa a API `getMe`, com o token salvo e limite assíncrono de 12 segundos. **TELEGRAM: OK** indica resposta válida da API; não garante que o processo de polling tenha sido reiniciado após uma troca de token. Não consulta tabelas Oracle. Os indicadores atualizam ao entrar no painel, ao salvar a seção correspondente, ao clicar e periodicamente a cada minuto com a página visível.

### 8. Acesso local e rastreamento no terminal

Permissões são verificadas nos JSONs locais antes das consultas; não são permissões do usuário Oracle. O acesso ao bot exige perfil aprovado e as permissões específicas descritas acima, inclusive para o administrador principal. Seu perfil recebe todas as permissões ao ser criado, mas pode ser personalizado no painel, com os mesmos limites de filial e tabela dos demais usuários. Essas escolhas são preservadas ao reiniciar e não alteram o acesso administrativo ao painel. As permissões `ver_margem_produto`, `ver_margem_departamento` e `ver_custos` são independentes.

As linhas `CONSULTA` do terminal registram ID da atualização, ID/nome/username do Telegram, tipo e etapa da operação, código/termo ou filtros, quantidade de registros e duração em milissegundos. Para erros, registram tipo da exceção e códigos `ORA`, `DPI` ou `DPY`. Consultas complementares têm registros próprios; uma busca de produto pode gerar logs de preços e custos/margem do próprio produto. A margem do departamento é consultada separadamente pelos comandos correspondentes. Os logs específicos de consultas não registram token, senha, conteúdo da foto ou valores retornados de custo. Exceções também podem produzir traceback no terminal para diagnóstico.


### Restrições de filial e tabela de preço

Usuários e modelos podem conter `filiais_permitidas` e `tabelas_permitidas`. Ausência ou `null` libera todas; lista vazia bloqueia a categoria. Códigos são validados e enviados como binds. Essas restrições também se aplicam ao administrador e aos perfis de teste.

A consulta por código, foto ou nome restringe `T.NUMREGIAO` e usa `EXISTS` em `PCEST` por produto/filial. A consulta de custos restringe `E.CODFILIAL`. As consultas agregadas de departamento filtram `E.CODFILIAL` e `T.NUMREGIAO` antes de somar. As listas de seleção de filial/região também recebem esses filtros. Restrições são relidas para cada consulta; botões antigos não contornam um bloqueio novo.

Quando as opções de perguntar filial ou região estão habilitadas, cada pergunta só aparece se houver mais de uma alternativa autorizada para o produto. Uma filial única em `PCEST` ou uma região única entre os preços válidos (`PCTABPR.PVENDA > 0` e `PCREGIAO.STATUS = 'A'`) é selecionada automaticamente. O escopo resultante também restringe os custos e as margens exibidos. Filial e região são avaliadas separadamente; o preço continua regional.

A busca por código só exibe registros com `PVENDA > 0`. Sem resultados, uma consulta adicional em `PCPRODUT`, com os mesmos campos de código e restrição de filial, diferencia produto inexistente de produto sem preço nas tabelas permitidas. Esta verificação não revela preços de tabelas não autorizadas. A busca por nome pode apresentar um produto sem preço positivo; ao selecioná-lo, aplica-se a mesma verificação.

### Mensagens personalizadas

`modulos/mensagens.py` define os modelos de texto, os exemplos e as variáveis autorizadas por bloco. A guia **Personalização** usa `GET/PUT /api/message-templates` e `POST /api/message-templates/preview`; todos exigem sessão administrativa, e gravação/prévia também exigem CSRF. A prévia usa exclusivamente exemplos fictícios, sem consultar Oracle ou Telegram.

Os modelos salvos são lidos de `mensagens.json`, na mesma pasta de `dados_bot.json`. A gravação é atômica; salvar um bloco preserva os demais. Enviar `null` para o bloco restaura seu padrão. Sem arquivo, os padrões do código são usados. Se um modelo ou arquivo for inválido durante uma resposta do bot, o bloco volta ao padrão e registra um aviso sem incluir o texto personalizado no log.

Modelos aceitam texto simples, emojis, quebras de linha e variáveis nomeadas como `{descricao}`. Chaves literais devem ser duplicadas: `{{texto}}`. São rejeitados nomes desconhecidos, acesso por atributo/índice, conversões e especificadores de formato. O limite é de 2.500 caracteres por modelo. O preenchimento não executa código e não interpreta novamente os valores recebidos do banco.

Os blocos continuam sendo montados após as verificações de permissão: `programado` exige `ver_preco_programado`; custos, notas, totais de custo e substituição numérica exigem `ver_custos`; lucro do produto exige `ver_margem_produto`; relatório/fórmula de departamento exige `ver_margem_departamento`. Cada bloco recebe somente suas variáveis permitidas. A personalização de texto não altera SQL, escopos de filial/tabela nem a fórmula matemática; a seleção de colunas adicionais é descrita a seguir.

### Campos adicionais de PCPRODUT

Nos blocos de identificação do produto, o administrador digita uma coluna de PCPRODUT entre chaves na mensagem. O sistema normaliza os nomes para minúsculas e valida colunas novas pelo catálogo Oracle: `listar_colunas_produto` executa `SELECT * FROM PCPRODUT WHERE 1=0` e lê somente os metadados. Aceita até 20 colunas adicionais de texto, número ou data; nomes compostos, expressões SQL, binários e LOB são rejeitados.

`POST /api/message-templates/preview` pode receber CODPROD para consultar valores reais. A consulta usa parâmetros vinculados, somente as colunas validadas e `PCPRODUT.DTEXCLUSAO IS NULL`, inclusive para produtos sem preço. Testar não grava os campos. `PUT /api/message-templates` registra automaticamente os campos necessários em `campos_produto.json` e salva o texto em `mensagens.json`. As duas operações exigem sessão administrativa e CSRF.

`consultar_produto` inclui as colunas salvas como `P.COLUNA AS EXTRA_N` e organiza os valores em `campos_personalizados`. O bot respeita a classificação pública ou restrita a custos; colunas sem classificação conhecida começam restritas a custos. A prévia administrativa pode mostrar todos os valores, mas isso não libera acesso ao usuário Telegram. As permissões existentes são preservadas.

As rotas `/api/product-fields` permanecem para compatibilidade; não há subaba de cadastro manual de campos. Os arquivos de mensagens, campos e fórmulas ficam na pasta de dados, fora do Git.
