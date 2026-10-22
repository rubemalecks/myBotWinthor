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

**Depois de salvar ou alterar o token, pare e inicie o projeto novamente.** Token e senha Oracle vazios mantêm os valores salvos.

Os indicadores mostram **OK verde** ou **OFF vermelho**. Clique para verificar novamente. O teste Oracle verifica conexão e acesso à consulta de produtos; custos e departamentos dependem de outras tabelas.

Para iniciar com o Windows, use **Inicialização automática do Windows**, na guia Bot. Não execute outra instância manual enquanto o serviço estiver ativo.

## 4. Usar no Telegram

Abra uma conversa privada com o bot. Os recursos dependem das permissões do perfil.

| Envie | Resultado |
|---|---|
| `/start` | Inicia o atendimento e registra seu usuário. |
| `/meuid` | Mostra seu ID para cadastro no painel. |
| Um código, como `6` | Busca por código interno ou de barras. |
| Parte do nome, com pelo menos 3 caracteres | Mostra até dez produtos para escolher. |
| Foto de um código de barras | Identifica o código e consulta o produto. |
| `/margem` ou `/margem 113` | Inicia a análise por departamento. |
| `/cancelarmargem` | Cancela a análise por departamento. |
| `/ajuda` ou `/comandos` | Mostra a ajuda e os recursos disponíveis. |

Para liberar alguém, abra **Perfis e permissões**, atualize a lista e clique no perfil. Marque **Permitir acesso ao bot**, selecione as permissões e salve. Também é possível cadastrar pelo ID.

Para reutilizar permissões, crie ou edite um modelo em **Modelos de perfil**. Depois, abra um usuário, escolha a predefinição, clique em **Aplicar modelo** e em **Salvar perfil**. O usuário fica vinculado: salvar alterações no modelo atualiza automaticamente suas permissões. Usuários bloqueados continuam bloqueados e com todas as permissões desmarcadas.

Marcar qualquer permissão habilita **Permitir acesso ao bot**; desmarcar esse acesso desmarca todas as permissões. Salve para confirmar. Para personalizar um usuário, altere uma permissão individual ou selecione **Sem vínculo (personalizado)** e aplique; ao salvar, ele deixa de receber atualizações do modelo. Excluir um modelo remove os vínculos, preservando as permissões atuais. Os modelos e vínculos ficam em `dados_bot.json` e acompanham seu backup. Modelos aplicados antes desse recurso precisam ser reaplicados e salvos para criar o vínculo.

Os modelos iniciais **Funcionário** e **Cliente** liberam consultas de preço; Funcionário também inclui foto e código interno. Custos, margens e preço programado começam desmarcados nos dois e podem ser personalizados.

**Margem por produto, margem por departamento e visualização de custos são permissões independentes.** A margem do departamento também pode aparecer na consulta do produto, quando autorizada.

**Ver preço programado** também é uma permissão separada. O preço de venda aparece na consulta autorizada; o valor programado (`PTABELA`) só aparece com essa opção habilitada. Para usuários comuns e perfis de teste, ela começa desmarcada; o administrador principal mantém acesso total.

## 5. Dados e backup — importante

**O Oracle pertence ao cliente.** O projeto consulta esse banco, mas não o cria nem faz backup dele.

Os usuários e as configurações ficam em uma pasta criada automaticamente ao lado do projeto:

```text
myBotWinthor/                 ← projeto e .env
myBotWinthor-dados/           ← dados locais
├── config_bot.json          ← Telegram e opções do painel
├── config_oracle.json       ← conexão Oracle
└── dados_bot.json           ← usuários, permissões e hash da senha do painel
```

O nome padrão é o nome da pasta do projeto seguido de `-dados`. Confira o caminho em **Bot → Armazenamento**. `BOT_DATA_DIR` no `.env` permite escolher outro local.

### Fazer backup

**Não há backup automático.** Antes de atualizar ou mudar de computador:

1. Pare o bot e o serviço, se estiver ativo.
2. Copie a **pasta de dados inteira** para um local seguro, por exemplo `C:\Backups\myBotWinthor\AAAA-MM-DD\`.
3. Guarde também uma cópia do `.env`.
4. Confira os três JSONs na cópia e inicie o projeto novamente.

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
