# myBotWinthor

![myBotWinthor](assets/Logo%20geom%C3%A9trico%20myBotWinthor%20com%20monograma%20RB.png)

Consulte produtos, preços, custos e margens do WinThor pelo Telegram. Use o painel web para configurar o sistema e controlar o acesso de cada usuário.

## Acesso rápido no Windows

Depois da instalação, use os arquivos BAT com dois cliques, sem ativar o ambiente virtual manualmente:

| Arquivo | Função |
|---|---|
| **[configurar.bat](configurar.bat)** | Configurar o Oracle e a porta da API. Ao sair, oferece iniciar a aplicação e abrir o painel. |
| **[iniciar.bat](iniciar.bat)** | Iniciar o bot/API e perguntar se deseja abrir o painel no navegador. |
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

Copie `.env.example` e renomeie a cópia para **`.env`**. Se já existir, mantenha seu arquivo.

Se usar o Oracle Instant Client, coloque as DLLs diretamente na pasta **`oracle_client`**, dentro do projeto. A API detecta essa pasta automaticamente; sem ela, tenta conectar no modo Thin.

## 2. Iniciar

**No Windows, abra `iniciar.bat` com dois cliques.** Ele pergunta se deseja abrir o painel no navegador. Responda `S` para abrir ou `N`/Enter para iniciar sem abrir o navegador. O bot/API inicia nos dois casos.

Se o serviço Windows estiver instalado, ele será utilizado; caso contrário, a execução permanece no terminal, que deve ficar aberto. O navegador só abre depois de o painel responder. Se a API já estiver ativa, nenhuma nova instância será criada.

O `iniciar.bat` abre um terminal próprio para a execução. Na execução manual, **Ctrl+C** solicita o encerramento e mostra uma mensagem de finalização, sem traceback de `KeyboardInterrupt`. O iniciador aguarda o processo terminar antes de fechar. Se a API estiver rodando como serviço Windows, pare-a pelo gerenciamento de serviços; fechar o iniciador não para o serviço.

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

Com o projeto e o serviço Windows **parados**, abra **`configurar.bat`** com dois cliques. O menu permite:

- **Configurar banco Oracle:** servidor, porta Oracle, service name, usuário e senha oculta. Enter mantém o valor atual; ao final, você pode salvar e testar a consulta de produtos.
- **Configurar porta da API:** escolha a porta HTTP do painel/API, entre 1 e 65535. A porta padrão é `8765`; a porta do Oracle é uma configuração diferente.

O BAT e o painel usam os mesmos `config_oracle.json` e `config_bot.json` na pasta de dados. O BAT não altera o `.env`. Ao terminar, inicie o projeto para aplicar a porta escolhida. Para acesso pela rede, confira também a liberação da nova porta no firewall. Se a porta já estiver ocupada, escolha outra.

Ao escolher a porta no BAT e ao iniciar a API, o terminal mostra o endereço local e o endereço para outras máquinas da mesma rede, quando disponíveis. Se o painel estiver limitado a `127.0.0.1`/`localhost`, o acesso pela rede não será anunciado.

Se o ambiente virtual ainda não existir, o BAT mostra os comandos de instalação. Você também pode abrir o assistente pelo terminal: `.\.venv\Scripts\python.exe -m modulos.configurar`.

Ao escolher **0 — Sair**, o configurador pergunta se deseja iniciar o serviço/bot e abrir o painel no navegador. Se o serviço Windows estiver instalado, tenta iniciá-lo; caso contrário, executa o bot/API no terminal. O navegador abre apenas depois de o painel responder. Uma instância já em execução é reutilizada. Na execução manual, mantenha o terminal aberto; para parar, use **Ctrl+C**. O serviço Windows pode exigir que o BAT seja executado como administrador.

### Configuração pelo navegador

| Guia | O que fazer |
|---|---|
| **Bot** | Informe o ID do administrador e o token. Clique em **SALVAR E TESTAR BOT**. |
| **Servidor Oracle** | Informe host, porta, service name, usuário e senha. Clique em **SALVAR E TESTAR ORACLE**. |
| **Perfis e permissões** | Cadastre ou aprove usuários e escolha o que cada um pode consultar. |
| **Modelos de perfil** | Edite Funcionário e Cliente ou cadastre novas predefinições de permissões. |
| **Personalização** | Configure o texto das respostas do bot, com variáveis e prévia da mensagem. |

**Depois de salvar ou alterar o token, pare e inicie o projeto novamente.** Token e senha Oracle vazios mantêm os valores salvos.

O **ID do administrador informado na guia Bot é pré-cadastrado automaticamente com todas as permissões** quando ainda não existe na lista. Depois, personalize seu acesso ao bot em **Perfis e permissões**, usando os mesmos controles dos demais usuários: acesso, permissões individuais, modelos, filiais e tabelas. As escolhas permanecem salvas após reiniciar. Isso não altera o login administrativo do painel. Use o ID numérico retornado por `/meuid`, não o número de telefone.

Se o painel responder, mas o bot não receber mensagens, confirme o token e reinicie depois de salvá-lo. No terminal, cada atualização recebida gera um registro `CONSULTA` com `consulta: telegram` e `etapa: RECEBIDO`. Um conflito de polling indica que outra instância usa o mesmo token: pare a execução antiga, inclusive em outro computador. `TELEGRAM: OK` verifica o acesso à API, não garante que o polling esteja ativo. Ao iniciar pelo BAT, erros mantêm a janela aberta para leitura.

Os indicadores mostram **OK verde** ou **OFF vermelho**. Clique para verificar novamente. O teste Oracle verifica conexão e acesso à consulta de produtos; custos e departamentos dependem de outras tabelas.

Confirmações do painel desaparecem após 2,5 segundos. Erros e resultados detalhados dos testes de conexão ficam visíveis por 10 segundos. Avisos de verificação em andamento permanecem até a conclusão.

O host/IP e o usuário do Oracle ficam ocultos após salvar e ao carregar valores já configurados. Use **Mostrar/Ocultar** ao lado de cada campo para visualizar ou editar os dados.

Para iniciar com o Windows, use **Inicialização automática do Windows**, na guia Bot. Não execute outra instância manual enquanto o serviço estiver ativo.

### Personalizar mensagens de retorno

Na guia **Personalização**, escolha o tipo de mensagem, edite o texto e clique em **Salvar mensagem**. A prévia usa dados fictícios. Clique nas variáveis disponíveis para inseri-las, mantendo as chaves. Exemplo para **Produto → Identificação do produto**:

```text
🛒 Minha empresa
Produto: {descricao}
Código: {codprod}
```

Você pode ajustar os blocos de produto, preços, preço programado, custos/nota de entrada, lucro do produto, departamento, fórmula, pesquisa por nome e avisos de consulta. Os mesmos blocos de produto são usados na busca por código, foto ou nome. Os blocos de preço, custo e lucro se repetem conforme as tabelas ou filiais retornadas.

**A personalização altera o texto, não o cálculo nem as permissões.** Custos e preço programado só aparecem para quem tem acesso; suas variáveis não são aceitas nos blocos públicos de preço. Não digite credenciais nem dados confidenciais como texto fixo. Textos são enviados sem formatação Markdown/HTML; emojis e quebras de linha são aceitos. Cada modelo aceita até 2.500 caracteres.

As alterações valem nas próximas consultas, **sem reiniciar o bot**. Para desfazer uma personalização, clique em **Restaurar padrão** e depois em **Salvar mensagem**. Os modelos ficam em `mensagens.json`, criado na pasta de dados no primeiro salvamento. Inclua esse arquivo no backup ou copie-o para outra instalação para reutilizar o mesmo padrão.

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

## 5. Dados e backup — importante

**O Oracle pertence ao cliente.** O projeto consulta esse banco, mas não o cria nem faz backup dele.

Os usuários e as configurações ficam em uma pasta criada automaticamente ao lado do projeto:

```text
myBotWinthor/                 ← projeto e .env
myBotWinthor-dados/           ← dados locais
├── config_bot.json          ← Telegram e opções do painel
├── config_oracle.json       ← conexão Oracle
├── dados_bot.json           ← usuários, permissões e hash da senha do painel
└── mensagens.json           ← respostas personalizadas, criado ao salvar no painel
```

O nome padrão é o nome da pasta do projeto seguido de `-dados`. Confira o caminho em **Bot → Armazenamento**. `BOT_DATA_DIR` no `.env` permite escolher outro local.

### Fazer backup

**Não há backup automático.** Antes de atualizar ou mudar de computador:

1. Pare o bot e o serviço, se estiver ativo.
2. Copie a **pasta de dados inteira** para um local seguro, por exemplo `C:\Backups\myBotWinthor\AAAA-MM-DD\`.
3. Guarde também uma cópia do `.env`.
4. Confira os JSONs na cópia, incluindo `mensagens.json` se houver personalizações, e inicie o projeto novamente.

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
- [Manual de operação](docs/operacao.md): configuração avançada, serviço Windows, backup com PowerShell e migração passo a passo.
