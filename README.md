# myBotWinthor

![myBotWinthor](assets/Logo%20geom%C3%A9trico%20myBotWinthor%20com%20monograma%20RB.png)

Consulte produtos, preços, custos e margens do WinThor pelo Telegram. Use o painel web para configurar o sistema e controlar o acesso de cada usuário.

Para agentes e desenvolvedores: [resumo da arquitetura, regras e comandos de teste](AGENTS.md).

## Acesso rápido no Windows

Depois da instalação, use os arquivos BAT com dois cliques, sem ativar o ambiente virtual manualmente:

| Arquivo | Função |
|---|---|
| **[configurar.bat](configurar.bat)** | Configurar o Oracle e a porta da API. Ao sair, oferece iniciar a aplicação e abrir o painel. |
| **[iniciar.bat](iniciar.bat)** | Iniciar o bot/API e perguntar se deseja abrir o painel no navegador. |
| **[monitor.bat](monitor.bat)** | Ler um arquivo de log existente; na execução direta, acompanhe as consultas no terminal do bot. |
| **[myBotWinthor.bat](myBotWinthor.bat)** | Mostrar apenas o banner da aplicação; não inicia nem configura o sistema. |

**Primeiro uso:** instale as dependências abaixo → abra `configurar.bat` → inicie a aplicação → configure o Telegram pelo painel.

**Uso diário:** abra `iniciar.bat`. Para mudar a conexão Oracle ou a porta, pare a aplicação e abra `configurar.bat` novamente. O Oracle também pode ser configurado pelo painel web.

## 1. Instalar

Você precisa de **Python para Windows**, acesso ao Oracle do WinThor e um token de bot do Telegram.

Abra o PowerShell na pasta do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

O **`.env` é opcional**: configure o Oracle pelo BAT ou painel e o Telegram pelo painel. Se preferir valores iniciais por arquivo, copie `.env.example` para **`.env`**; se ele já existir, mantenha seu arquivo. As configurações salvas ficam na pasta de dados da instalação.

Se usar o Oracle Instant Client, coloque as DLLs diretamente na pasta **`oracle_client`**, dentro do projeto. A API detecta essa pasta automaticamente; sem ela, tenta conectar no modo Thin.

## 2. Iniciar

**No Windows, abra `iniciar.bat` com dois cliques.** Ele pergunta se deseja abrir o painel no navegador. Responda `S` para abrir ou `N`/Enter para iniciar sem abrir o navegador. O bot/API inicia nos dois casos.

O BAT executa o Python da `.venv` com `bot.py`, mantendo a execução no terminal. Não instala nem inicia serviço Windows. O navegador abre somente quando o painel responde; se a API já estiver ativa, não cria outra instância.

Mantenha o terminal aberto. Para encerrar, pressione **Ctrl+C**; o iniciador aguarda o processo finalizar.

**Instalações antigas:** se houver um serviço `MyBotWinthorBot` instalado, pare-o e desative-o em `services.msc` antes de adotar a execução pelo terminal. Isso evita que ele volte a iniciar com o Windows e duplique o polling Telegram. O novo BAT não altera serviços existentes automaticamente.

### Acompanhar as consultas

Na execução direta, consultas, requisições e erros aparecem no próprio terminal do bot. `monitor.bat` permanece disponível para ler um arquivo de log existente, como `bot-service.log` de uma instalação antiga. A execução direta não redireciona automaticamente a saída para esse arquivo.

### Alternativa pelo terminal

Se preferir iniciar sem o BAT, execute na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe bot.py
```

Esse comando inicia o painel e o bot, sem precisar ativar o ambiente virtual.

- Abra o endereço mostrado no terminal. Na própria máquina, o padrão é **http://127.0.0.1:8765**.
- No primeiro acesso, use **usuário `admin` e senha `admin`**. Troque a senha no painel.
- Para parar a execução manual, pressione **Ctrl+C**.

Para ativar o ambiente no PowerShell, se preferir, use `.\.venv\Scripts\Activate.ps1` e depois `python bot.py`.

## 3. Configurar pelo BAT ou pelo painel

### Configurar pelo arquivo BAT

Com o projeto **parado**, abra **`configurar.bat`** com dois cliques. O menu permite:

- **Configurar banco Oracle:** servidor, porta Oracle, service name, usuário e senha oculta. Enter mantém o valor atual; ao final, você pode salvar e testar a consulta de produtos.
- **Configurar porta da API:** escolha a porta HTTP do painel/API, entre 1 e 65535. A porta padrão é `8765`; a porta do Oracle é uma configuração diferente.

O BAT e o painel usam os mesmos `config_oracle.json` e `config_bot.json` na pasta de dados. O BAT não altera o `.env`. Ao terminar, inicie o projeto para aplicar a porta escolhida. Para acesso pela rede, confira também a liberação da nova porta no firewall. Se a porta já estiver ocupada, escolha outra.

Ao escolher a porta no BAT e ao iniciar a API, o terminal mostra o endereço local e o endereço para outras máquinas da mesma rede, quando disponíveis. Se o painel estiver limitado a `127.0.0.1`/`localhost`, o acesso pela rede não será anunciado.

Se o ambiente virtual ainda não existir, o BAT mostra os comandos de instalação. Você também pode abrir o assistente pelo terminal: `.\.venv\Scripts\python.exe -m modulos.configurar`.

Ao escolher **0 — Sair**, o configurador pergunta se deseja iniciar o bot/API no terminal e abrir o painel. O navegador abre depois de o painel responder. Não é necessário instalar serviço nem executar o BAT como administrador. Mantenha o terminal aberto e use **Ctrl+C** para parar.

### Configuração pelo navegador

| Guia | O que fazer |
|---|---|
| **Bot** | Informe o ID do administrador e o token. Clique em **SALVAR E TESTAR BOT**. |
| **Servidor Oracle** | Informe host, porta, service name, usuário e senha. Clique em **SALVAR E TESTAR ORACLE**. |
| **Perfis e permissões** | Cadastre ou aprove usuários e escolha o que cada um pode consultar. |
| **Modelos de perfil** | Edite Funcionário e Cliente ou cadastre novas predefinições de permissões. |
| **Personalização** | Use as subabas **Mensagens** e **Fórmulas** para configurar os retornos, campos e cálculos, com prévia. |

**Depois de salvar ou alterar o token, pare e inicie o projeto novamente.** Token e senha Oracle vazios mantêm os valores salvos.

O **ID do administrador informado na guia Bot é pré-cadastrado automaticamente com todas as permissões** quando ainda não existe na lista. Depois, personalize seu acesso ao bot em **Perfis e permissões**, usando os mesmos controles dos demais usuários: acesso, permissões individuais, modelos, filiais e tabelas. As escolhas permanecem salvas após reiniciar. Isso não altera o login administrativo do painel. Use o ID numérico retornado por `/meuid`, não o número de telefone.

Se o painel responder, mas o bot não receber mensagens, confirme o token e reinicie depois de salvá-lo. No terminal, cada atualização recebida gera um registro `CONSULTA` com `consulta: telegram` e `etapa: RECEBIDO`. Um conflito de polling indica que outra instância usa o mesmo token: pare a execução antiga, inclusive em outro computador. `TELEGRAM: OK` verifica o acesso à API, não garante que o polling esteja ativo. Ao iniciar pelo BAT, erros mantêm a janela aberta para leitura.

Os indicadores mostram **OK verde** ou **OFF vermelho**. Clique para verificar novamente. O teste Oracle verifica conexão e acesso à consulta de produtos; custos e departamentos dependem de outras tabelas.

Confirmações do painel desaparecem após 2,5 segundos. Erros e resultados detalhados dos testes de conexão ficam visíveis por 10 segundos. Avisos de verificação em andamento permanecem até a conclusão.

O host/IP e o usuário do Oracle ficam ocultos após salvar e ao carregar valores já configurados. Use **Mostrar/Ocultar** ao lado de cada campo para visualizar ou editar os dados.

A execução é pelo terminal, com `iniciar.bat` ou `.\.venv\Scripts\python.exe bot.py`. A opção de instalar serviço foi retirada do painel.

### Personalizar mensagens de retorno

Em **Personalização → Mensagens**, a prévia começa com dados fictícios. Para testar os blocos de identificação do produto com dados reais, informe um **CODPROD** e clique em **Consultar produto**. As variáveis adicionais, como `{volume}`, usam os valores salvos no Oracle; campos vazios aparecem como **Não informado**. A prévia administrativa inclui os campos configurados, e o bot continua respeitando as permissões do usuário. Clique em **Usar exemplo fictício** para voltar ao exemplo.

Em **Personalização → Mensagens**, escolha o tipo de mensagem, edite o texto e clique em **Salvar mensagem**. Clique nas variáveis disponíveis para inseri-las ou digite uma coluna de PCPRODUT nos blocos de identificação do produto. Exemplo para **Produto → Identificação do produto**:

```text
🛒 Minha empresa
Produto: {descricao}
Código: {codprod}
```

Você pode ajustar os blocos de produto, preços, preço programado, custos/nota de entrada, lucro do produto, departamento, fórmula, pesquisa por nome e avisos de consulta. Os mesmos blocos de produto são usados na busca por código, foto ou nome. Os blocos de preço, custo e lucro se repetem conforme as tabelas ou filiais retornadas.

**A personalização altera o texto, não o cálculo nem as permissões.** Custos e preço programado só aparecem para quem tem acesso; suas variáveis não são aceitas nos blocos públicos de preço. Não digite credenciais nem dados confidenciais como texto fixo. Textos são enviados sem formatação Markdown/HTML; emojis e quebras de linha são aceitos. Cada modelo aceita até 2.500 caracteres.

As alterações valem nas próximas consultas, **sem reiniciar o bot**. Para desfazer uma personalização, clique em **Restaurar padrão** e depois em **Salvar mensagem**. Os modelos ficam em `mensagens.json`, criado na pasta de dados no primeiro salvamento. Inclua esse arquivo no backup ou copie-o para outra instalação para reutilizar o mesmo padrão.

### Campos de PCPRODUT direto na mensagem

Em **Personalização → Mensagens**, digite o nome da coluna entre chaves no bloco **Produto → Identificação do produto** ou **Fórmula → Identificação do produto**. Não é necessário cadastrar campos em outra tela.

```text
Produto: {descricao}
Código: {codprod}
Embalagem: {embalagem}
Código de barras: {codauxiliar}
```

1. Digite uma coluna válida de `PCPRODUT`, como `{EMBALAGEM}` ou `{embalagem}`. Maiúsculas e minúsculas são aceitas.
2. Informe o CODPROD e clique em **Consultar produto**. O sistema valida a coluna no Oracle e mostra seu valor real, sem salvar a alteração. Valores nulos aparecem como **Não informado**.
3. Clique em **Salvar mensagem**. As variáveis são normalizadas para minúsculas e os campos necessários ficam registrados automaticamente para as próximas consultas do bot.

A prévia sem CODPROD continua fictícia. Colunas inexistentes, binárias/LOB, expressões SQL e variáveis de produto em outros blocos são rejeitadas. São aceitos até **20 campos adicionais**, de texto, número ou data. As permissões de busca e o filtro de produtos excluídos permanecem iguais.

Campos públicos conhecidos, como EMBALAGEM e CODAUXILIAR, acompanham a permissão de consultar preço. Colunas sem classificação pública começam restritas à permissão de custos; classificações já salvas são preservadas. A prévia administrativa mostra o valor, mas o bot exibe **Sem permissão** quando necessário.

`campos_produto.json` passa a ser um registro interno automático, preservado para compatibilidade com as mensagens existentes. Esse arquivo e `mensagens.json` ficam na pasta de dados da instalação, fora do Git, e devem acompanhar o backup. Alterações salvas valem nas próximas consultas, sem reiniciar.

### Manutenção de fórmulas (exclusiva do painel)

Abra **Personalização → Fórmulas**. Essa seção configura os cálculos apresentados no Telegram; o bot não permite editar regras.

1. Informe um **CODPROD** e clique em **Simular cálculo** para ver os valores reais por filial e tabela.
2. Adicione ajustes para somar/subtrair valores ou percentuais do **custo**, do **preço usado no cálculo** ou do **resultado**. No resultado, valor fixo significa pontos percentuais; percentual significa variação relativa. Exemplo: custo 10 e preço 20 resultam em 100%; somar 2 ao custo resulta em 66,67%.
3. Para usar um parâmetro numérico, clique em **Carregar parâmetros das tabelas** e escolha uma coluna de `PCPRODUT`, `PCEST`, `PCTABPR` ou `PCREGIAO`. Clique em **Confirmar fórmula** para incluir a expressão na prévia; se houver CODPROD informado, a simulação é recalculada sem salvar.
4. Dê um nome, vincule uma lista de CODPRODs e/ou um filtro, como `PCPRODUT.CODEPTO = 108 AND PCEST.CODFILIAL = 1`. Lista e filtro são combinados com AND. Para uma regra geral, marque **Todos os produtos** e deixe os dois vazios.
5. Marque **Ativar nas consultas do bot** e salve. Sem ativar, a fórmula fica guardada para manutenção. Em sobreposição, vence a primeira regra ativa por prioridade crescente; empates seguem o identificador.

A prévia mostra a fórmula atual e a simulada, inclusive quando o produto está fora do filtro. Simular não salva nem modifica o Oracle. Os ajustes alteram somente o cálculo de lucro: não mudam preços, custos cadastrados ou permissões. Custos ajustados nulos ou não positivos tornam o percentual indisponível. No departamento, os resultados por produto são ponderados pelo custo ajustado; não se faz uma média simples de percentuais.

As regras ficam em **`formulas_margem.json` na pasta de dados da instalação**, fora do Git. Inclua o arquivo no backup e na mudança de máquina. Salvar, desativar ou remover uma regra vale nas próximas consultas, sem reiniciar. Sem regra aplicável, permanece `(preço − custo) ÷ custo × 100`.

## 4. Comandos do bot no Telegram

**Os comandos abaixo devem ser enviados na conversa privada com o bot no aplicativo Telegram. Não são comandos do PowerShell, do BAT ou do painel web.** Os recursos disponíveis dependem das permissões do usuário.

### Lista completa de comandos

| Comando do bot | O que faz / exemplo |
|---|---|
| `/start` | Inicia o atendimento e registra seu usuário. |
| `/meuid` | Mostra seu ID para cadastro no painel. |
| `/ajuda` | Mostra instruções de uso. |
| `/comandos` | Lista os comandos e recursos apresentados para o perfil. |
| `/margem` | Inicia a escolha de departamento, filial e região/tabela para análise. Aceita código ou nome: `/margem 108` ou `/margem ORGANNACT`. |
| `/cancelarmargem` | Cancela a seleção de departamento em andamento. Não apaga uma mensagem de resultado já enviada nem interrompe uma consulta SQL já iniciada. |
| `/formula` | Mostra exemplos de uso e a origem dos campos usados no cálculo. |
| `/fomula` | Alias de `/formula`; aceita os mesmos argumentos e permissões. |

### Exemplos do comando `/formula`

| Envie ao bot | Consulta |
|---|---|
| `/formula 1663` | Fórmula do produto pelo CODPROD 1663. |
| `/formula produto 1663` | Mesmo resultado, indicando explicitamente que é um produto. |
| `/formula ORGANNACT` | Fórmula do departamento pesquisado pelo nome. |
| `/formula departamento 108` | Fórmula do departamento de código 108. |
| `/formula depto 108` | Forma abreviada de consultar o departamento pelo código. |
| `/fomula 1663` | Mesmo que `/formula 1663`. |

Um número sem prefixo é sempre tratado como **CODPROD**. Para consultar um departamento por código, escreva `departamento` ou `depto` antes dele. Se o nome corresponder a vários departamentos, o bot lista os códigos para você escolher.

A fórmula de produto exige acesso a preços, busca por CODPROD e margem por produto. A fórmula de departamento exige margem por departamento. Os números de custo e a substituição numérica só aparecem com **Ver custos detalhados**; sem essa permissão, a explicação mostra a fórmula genérica e o percentual. Todas as consultas respeitam as filiais e tabelas autorizadas.

### Consultas sem comando

Estas ações também são feitas na conversa do Telegram, sem digitar `/`:

| Envie ao bot | Resultado |
|---|---|
| Um código, como `6` | Busca por código interno ou de barras, conforme os campos liberados no perfil. |
| Parte do nome, com pelo menos 3 caracteres | Mostra até dez produtos para escolher. |
| Foto de um código de barras | Identifica o código e consulta o produto, se a busca por foto estiver autorizada. |

Se **Perguntar filial** ou **Perguntar região/tabela** estiver ativo, o bot apresenta botões para escolher antes de mostrar o produto. O botão **Cancelar consulta** encerra essa seleção específica.

### Liberar usuários no painel

Para liberar alguém, abra **Perfis e permissões**, atualize a lista e clique no perfil. Marque **Permitir acesso ao bot**, selecione as permissões e salve. Também é possível cadastrar pelo ID.

Para reutilizar permissões, crie ou edite um modelo em **Modelos de perfil**. Depois, abra um usuário, escolha a predefinição, clique em **Aplicar modelo** e em **Salvar perfil**. O usuário fica vinculado: salvar alterações no modelo atualiza automaticamente suas permissões. Usuários bloqueados continuam bloqueados e com todas as permissões desmarcadas.

Marcar qualquer permissão habilita **Permitir acesso ao bot**; desmarcar esse acesso desmarca todas as permissões. Salve para confirmar. Para personalizar um usuário, altere uma permissão individual ou selecione **Sem vínculo (personalizado)** e aplique; ao salvar, ele deixa de receber atualizações do modelo. Excluir um modelo remove os vínculos, preservando as permissões atuais. Os modelos e vínculos ficam em `dados_bot.json` e acompanham seu backup. Modelos aplicados antes desse recurso precisam ser reaplicados e salvos para criar o vínculo.

Os modelos iniciais **Funcionário** e **Cliente** liberam consultas de preço; Funcionário também inclui foto e código interno. Custos, margens e preço programado começam desmarcados nos dois e podem ser personalizados.

**Margem por produto, margem por departamento e visualização de custos são permissões independentes.** A consulta individual mostra apenas o lucro do produto consultado, quando **Ver margem por produto** estiver habilitado. Para consultar o lucro do departamento, use `/margem` com a permissão correspondente; ele não é incluído na resposta de um produto.

O comando **`/formula`** (também aceita **`/fomula`**) apresenta a origem dos campos, a fórmula e o percentual para cada filial/tabela autorizada. Números sem prefixo são tratados como CODPROD; para departamento numérico, use `departamento` antes do código. Se o nome encontrar vários departamentos, o bot lista os códigos para escolher. A substituição com valores de custo exige **Ver custos detalhados**, além da permissão de margem correspondente. Sem essa permissão de custo, mostra apenas a fórmula genérica e o percentual. O custo de entrada é o valor registrado em `PCEST.CUSTOULTENT`; a fórmula calcula o ganho sobre ele, não a composição contábil do custo.

O percentual exibido como **Lucro presumido sobre o custo** é calculado por `(venda − custo) ÷ custo × 100`. Esse é o nome usado pelo projeto para a estimativa bruta de ganho sobre o custo de entrada (markup); não é um cálculo de apuração tributária. No departamento, usa as somas de preços e custos, considerando uma unidade por produto. Não representa lucro realizado nem desconta impostos e despesas adicionais. Custo zero não permite calcular o percentual individual.

**Ver preço programado** também é uma permissão separada. O preço de venda aparece na consulta autorizada; o valor programado (`PTABELA`) só aparece com essa opção habilitada, inclusive para o administrador. Para usuários comuns e perfis de teste, ela começa desmarcada.

### Filiais e tabelas de preço permitidas

As opções **Perguntar filial na consulta** e **Perguntar região/tabela de preço** fazem o bot pedir a escolha por botões quando houver mais de uma opção disponível e autorizada para o produto, seja por código, nome ou foto. Com apenas uma filial ou região disponível, o bot seleciona essa opção automaticamente e mostra o preço sem perguntar por ela. Só aparecem tabelas com preço de venda maior que zero. Ative uma ou ambas no usuário ou modelo e clique em **Salvar perfil**. Elas começam desativadas, inclusive para o administrador.

Se ambas estiverem ativas, o bot pergunta primeiro a filial e depois a região/tabela. Só aparecem opções autorizadas, e as tabelas precisam ter preço válido para o produto. O resultado e os cálculos usam as escolhas feitas. A seleção expira em 15 minutos, pode ser cancelada e não permite contornar restrições alteradas depois da pergunta. Região e tabela de preço são a mesma seleção (`NUMREGIAO`); escolher filial não cria um preço próprio por filial.

Em cada usuário ou modelo, configure **Filiais e tabelas autorizadas** marcando as caixas das filiais e regiões carregadas do Oracle. Marque **Todas** para acesso sem restrição, incluindo opções futuras; para limitar, desmarque e selecione as opções desejadas. Filial usa `CODFILIAL`; tabela usa `NUMREGIAO` e mostra o nome cadastrado. Sem nenhuma opção marcada, nenhum acesso é permitido nessa categoria. Salve para aplicar. Alterar os limites individualmente remove o vínculo com o modelo; modelos vinculados propagam seus limites aos usuários.

Se o Oracle estiver indisponível, o painel mantém os códigos já salvos como caixas de seleção e informa a falha. Use **Atualizar usuários** para recarregar a lista. Filiais vêm dos registros de `PCEST`; regiões vêm de `PCREGIAO`. Regiões inativas são identificadas e continuam excluídas das consultas de preços.

Preços, custos e margens respeitam esses limites, inclusive nas consultas do administrador. Os preços continuam regionais (`PCTABPR`); a restrição de filial verifica o registro do produto em `PCEST`, sem exigir estoque positivo. Perfis antigos continuam com acesso a todas as opções até serem limitados.

Na consulta de produto, aparecem somente tabelas ativas com **`PVENDA > 0`**. Se houver preço em uma só, apenas ela é mostrada. Se o produto existir nas filiais permitidas, mas não houver preço nas tabelas autorizadas, o bot informa que ele não está precificado nessas tabelas. Produto inexistente tem uma mensagem diferente.

**Produtos excluídos não são apresentados.** As consultas exigem `PCPRODUT.DTEXCLUSAO IS NULL`, tanto nas buscas por código, foto e nome quanto nos custos, nas opções de filial/região do departamento e nos cálculos de lucro. Produtos com data de exclusão preenchida não entram nos totais do departamento e são tratados como não encontrados ao consultar seu código.

## 5. Dados e backup — importante

**O Oracle pertence ao cliente.** O projeto consulta esse banco, mas não o cria nem faz backup dele.

Os usuários e as configurações ficam em uma pasta criada automaticamente ao lado do projeto:

```text
myBotWinthor/                 ← projeto e .env
myBotWinthor-dados/           ← dados locais
├── config_bot.json          ← Telegram e opções do painel
├── config_oracle.json       ← conexão Oracle
├── dados_bot.json           ← usuários, permissões e hash da senha do painel
├── mensagens.json           ← respostas personalizadas, criado ao salvar no painel
├── campos_produto.json      ← campos registrados automaticamente pelas mensagens
└── formulas_margem.json     ← regras e ajustes de fórmulas personalizados
```

O nome padrão é o nome da pasta do projeto seguido de `-dados`. Confira o caminho em **Bot → Armazenamento**. `BOT_DATA_DIR` no `.env` permite escolher outro local.

**Mensagens, campos e fórmulas são sempre salvos nessa mesma pasta de dados**, criada na inicialização. Seus arquivos de personalização são criados no primeiro salvamento. Se `BOT_DATA_DIR` estiver configurado, todos usam a pasta indicada. Inclua os três JSONs no backup; são dados de cada instalação e não são enviados ao Git.

### Fazer backup

**Não há backup automático.** Antes de atualizar ou mudar de computador:

1. Pare o bot e o serviço, se estiver ativo.
2. Copie a **pasta de dados inteira** para um local seguro, por exemplo `C:\Backups\myBotWinthor\AAAA-MM-DD\`.
3. Guarde também uma cópia do `.env`.
4. Confira os JSONs na cópia, incluindo `mensagens.json`, `campos_produto.json` e `formulas_margem.json` se houver personalizações, e inicie o projeto novamente.

Os JSONs de configuração contêm token e senha Oracle. Não publique esses arquivos. Essa cópia **não substitui o backup do Oracle**.

### Restaurar ou mudar de local

1. Com o projeto parado, copie a pasta de dados para o novo local.
2. Guarde uma cópia dos dados existentes antes de substituí-los.
3. Ajuste o `.env` para apontar à pasta restaurada:

   ```dotenv
   BOT_DATA_DIR=D:/Sistemas/myBotWinthor-dados
   ```

4. Execute o projeto e confira configurações, usuários e conexões no painel.

Para transferir **somente usuários e permissões**, copie `dados_bot.json`. Ele também leva a senha do painel em hash e os perfis de teste. Configure o ID do administrador, token e Oracle no destino. Substituir o arquivo não mescla os cadastros.

**Preserve a pasta de dados ao atualizar.** Clonar o código não recupera os dados de outra instalação. Ao migrar com o mesmo token, mantenha o bot antigo parado.

## Problemas comuns

| Problema | Verifique |
|---|---|
| Oracle conecta, mas retorna `ORA-00942` ou `ORA-01031` | Confira permissões nas tabelas e sinônimos. Compare com o mesmo usuário e serviço no Navigator. |
| Telegram OFF | Confira token e internet. Reinicie após alterar o token. |
| Painel não abre | Confira se o projeto está executando e use o endereço do terminal. Em outra máquina, confira rede e firewall. |
| Mudança visual não aparece | Reinicie o painel e atualize com **Ctrl+F5**. |
| Consulta falha | Confira as linhas **CONSULTA** no terminal: usuário, busca, resultado, duração e erro. |

## Mais detalhes

### Organização do projeto

```text
bot.py                 ← inicia o bot e o painel
bot_service.py         ← entrada do serviço Windows
service_helper.py      ← entrada do assistente do serviço
modulos/               ← lógica do bot, painel, consultas e persistência
assets/                ← logos e ícones
tests/                 ← testes automatizados
docs/                  ← documentação detalhada
oracle_client/         ← bibliotecas Oracle, quando utilizadas
```

Os arquivos Python da raiz são pontos de entrada; a implementação fica em `modulos/`. O comando de execução continua sendo `python bot.py`. O `.env` permanece na raiz, e a pasta de dados continua separada do código.

- [Consultas e cálculos](docs/consultas.md): tabelas, campos, JOINs, filtros, fórmulas de margem e testes de conexão.
- [Manual de operação](docs/operacao.md): configuração avançada, execução pelo terminal, backup com PowerShell e migração passo a passo.
