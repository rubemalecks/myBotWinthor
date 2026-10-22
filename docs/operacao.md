# Manual detalhado de operação

## IMPORTANTE — banco de dados, pasta de dados e backup

> **O Oracle do WinThor e os arquivos locais do bot são armazenamentos separados. O backup de um não substitui o do outro. O projeto não cria backups automáticos nem uma pasta de backup por conta própria.**

### Como os dados são armazenados

| Armazenamento | O que contém | Como funciona |
|---|---|---|
| **Oracle do cliente** | Produtos, preços, regiões, departamentos, custos, notas e fornecedores do WinThor. | A API conecta ao host/porta/service name configurados e executa SELECTs. Os fluxos de consulta não criam tabelas nem alteram os dados do WinThor. O backup Oracle deve ser feito pelo responsável pelo banco. |
| **JSONs locais do bot** | Configurações, usuários, perfis, permissões e autenticação do painel. | São criados automaticamente na primeira execução, independentemente de o Oracle estar disponível. Não exigem instalar um segundo servidor de banco. |
| **`.env` do projeto** | Opções iniciais, caminho dos dados e parâmetros de inicialização. | É lido ao iniciar; não é o destino das configurações salvas pelo painel. Valores já persistidos nos JSONs prevalecem sobre os valores iniciais correspondentes. |

**A pasta padrão fica ao lado do projeto, não dentro dele.** Seu nome é o nome da pasta do projeto acrescido de `-dados`. Exemplo de instalação:

```text
C:\Sistemas\
├── myBotWinthor\                  ← código, .env, assets e oracle_client
└── myBotWinthor-dados\            ← dados persistentes; copiar no backup
    ├── config_bot.json           ← Telegram e opções do painel
    ├── config_oracle.json        ← servidor e credenciais Oracle
    └── dados_bot.json            ← usuários, perfis, permissões e hash da senha
```

Se `BOT_DATA_DIR` estiver preenchido no `.env`, **esse caminho substitui a pasta padrão**. Caminhos relativos são resolvidos a partir da pasta do projeto. Para consultar o caminho efetivo, abra **Bot → Armazenamento** no painel. Renomear ou mover a pasta do projeto pode mudar o caminho padrão; configure `BOT_DATA_DIR` para manter um local fixo.

Os JSONs são lidos nas operações do sistema e gravados por arquivo temporário seguido de substituição do arquivo de destino. Isso protege cada gravação individual, mas **não cria histórico, cópia de segurança ou uma transação conjunta dos três arquivos**. A senha do painel é armazenada como hash; token do Telegram e senha Oracle permanecem como texto nos arquivos de configuração. Restrinja o acesso à pasta e não publique seus arquivos no Git.

### Onde guardar o backup

**Pasta sugerida, criada por você:** `C:\Backups\myBotWinthor\AAAA-MM-DD_HH-mm-ss\`. Esse caminho é apenas uma sugestão, não um destino configurado ou usado automaticamente pela API. Mantenha também uma cópia em outro disco ou local protegido para cobrir falha do computador.

O backup deve conter **a pasta de dados inteira, com os três JSONs da mesma parada do sistema**. Preserve também uma cópia do `.env` em local protegido para recuperar `BOT_DATA_DIR` e as opções de inicialização. A pasta `oracle_client` contém bibliotecas de execução, não o banco Oracle.

### Como fazer o backup manual

1. Pare o bot/painel com **Ctrl+C** ou pare o serviço do Windows, se a execução for por serviço. Confirme que não há outra instância gravando.
2. Confira o caminho efetivo da pasta de dados.
3. Copie a pasta inteira para uma nova pasta de backup identificada por data e hora.
4. Confira se `config_bot.json`, `config_oracle.json` e `dados_bot.json` estão na cópia.
5. Inicie o projeto novamente. Faça isso antes de atualizações, migrações e alterações manuais nos JSONs.

Exemplo de cópia no PowerShell, **com o projeto parado**. Ajuste a origem para o caminho real da sua instalação:

```powershell
$origemDados = 'C:\Sistemas\myBotWinthor-dados'
$raizBackup = 'C:\Backups\myBotWinthor'
$destinoBackup = Join-Path $raizBackup (Get-Date -Format 'yyyy-MM-dd_HH-mm-ss')
New-Item -ItemType Directory -Path $raizBackup -Force | Out-Null
Copy-Item -LiteralPath $origemDados -Destination $destinoBackup -Recurse -ErrorAction Stop
Get-ChildItem -LiteralPath $destinoBackup
```

Os comandos acima copiam os dados locais; **não fazem backup do banco Oracle**. A execução manual é responsabilidade de quem administra a instalação.

### Como restaurar ou migrar para outro computador

1. Pare o bot e o serviço antes de restaurar. Guarde uma cópia dos dados atuais para permitir retorno.
2. Copie o backup completo para uma pasta de dados no computador de destino, mantendo os três JSONs juntos.
3. No `.env`, aponte `BOT_DATA_DIR` para essa pasta. Exemplo:

   ```dotenv
   BOT_DATA_DIR=C:/Sistemas/myBotWinthor-dados
   ```

4. Prepare o ambiente Python e o Oracle Client no novo computador, se necessário, e confirme a conectividade ao Oracle e ao Telegram.
5. Execute `python bot.py`, entre no painel e confira configurações, usuários e indicadores.

> **Não apague a pasta de dados ao atualizar o código.** Clonar o repositório sem restaurar os dados cria uma instalação nova: seus usuários e configurações anteriores não são recuperados pelo Git. JSON inválido gera erro para correção ou restauração; o projeto não o substitui silenciosamente por um cadastro vazio.

### Tutorial — transferir usuários e permissões para outro local

Para transferir os cadastros, copie **`dados_bot.json`**. Esse arquivo contém usuários, permissões, perfis de teste e a senha do painel em hash; não contém as configurações Oracle e Telegram.

1. **Pare o projeto na origem e no destino**, usando **Ctrl+C** ou parando o serviço do Windows. Não faça a transferência com uma instância gravando os arquivos.
2. Localize a pasta de dados atual em **Bot → Armazenamento**, antes de parar o painel, ou confira `BOT_DATA_DIR` no `.env`. Se estiver vazio, a pasta padrão fica ao lado do projeto, com o sufixo `-dados`.
3. Copie `dados_bot.json` para um local seguro. Exemplo de origem:

   ```text
   C:\Sistemas\myBotWinthor-dados\dados_bot.json
   ```

4. Crie a pasta de dados no novo local e coloque nela o arquivo copiado. Exemplo:

   ```text
   D:\Sistemas\myBotWinthor-dados\dados_bot.json
   ```

   Se já existir um `dados_bot.json` no destino, guarde uma cópia antes de substituí-lo. **A substituição não mescla usuários:** os cadastros anteriores do destino serão substituídos pelos da origem.

5. No `.env` da instalação de destino, configure a pasta, sem incluir o nome do arquivo:

   ```dotenv
   BOT_DATA_DIR=D:/Sistemas/myBotWinthor-dados
   ```

6. Para manter também o token, o ID do administrador, as opções do painel e a conexão Oracle, copie **a pasta de dados inteira**, com `config_bot.json`, `config_oracle.json` e `dados_bot.json`. Se copiar somente os usuários, as configurações da origem não serão transferidas; configure Telegram e Oracle no destino e confirme qual ID deve ser o administrador principal.
7. Na pasta do projeto de destino, execute:

   ```powershell
   .\.venv\Scripts\python.exe bot.py
   ```

8. Entre com a senha do painel da origem, se ela já havia sido alterada, pois seu hash acompanha o arquivo. Confira os usuários na guia **Perfis e permissões** e teste as conexões Oracle e Telegram.

**Para mover apenas a pasta de dados na mesma máquina**, prefira copiar a pasta inteira, ajustar `BOT_DATA_DIR` e reiniciar. Preserve a pasta antiga até confirmar que a nova instalação está funcionando. Ao migrar para outro computador com o mesmo token do Telegram, mantenha a instância antiga parada.

## Configuração

Instale Python para Windows e abra um terminal na pasta do projeto. Na primeira instalação, crie o ambiente virtual:

```powershell
python -m venv .venv
```

1. Crie `.env` a partir de `.env.example`. Deixe `TELEGRAM_BOT_TOKEN` vazio: o token real é configurado pelo navegador, no painel, depois de iniciar a API. A conexão Oracle também pode ser configurada pelo painel.
2. O primeiro acesso ao painel é `admin` / `admin`. Altere a senha imediatamente no próprio painel; a nova senha deve ter entre 12 e 128 caracteres. Ela é armazenada como hash no banco local e permanece alterada após reiniciar o bot.
3. `WEB_SESSION_SECRET` é um segredo aleatório criado pelo serviço para assinar o cookie de sessão do painel. Ele protege a autenticação do painel contra alterações no cookie; não é uma senha do Telegram nem do Oracle. Se preferir fornecer o seu próprio, gere-o localmente com:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

   Se gerar o seu, copie o resultado para `WEB_SESSION_SECRET` no `.env`. Se deixar em branco, o serviço gera e mantém o segredo na pasta persistente de dados; ele sobrevive a reinicializações. Não compartilhe nem publique esse valor.

4. Instale as dependências e inicie a API:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe bot.py
   ```

O painel/API inicia e permanece acessível mesmo se o Telegram estiver sem token ou indisponível e mesmo se o Oracle não estiver configurado ou acessível. Acesse o endereço anunciado no log, entre com `admin` / `admin`, altere a senha e preencha as configurações no navegador. Ao salvar, a API testa a conexão com o Telegram (`getMe`) e executa uma consulta simples no Oracle; o painel mostra o resultado de cada teste, sem descartar as configurações em caso de falha. A conexão Oracle é necessária apenas para consultas. Depois de salvar um token válido, reinicie `bot.py` para iniciar o polling do bot; token inválido ou falha de rede do Telegram não derruba o painel. Reinicie também para aplicar opções de rede, HTTPS e caminho do Instant Client.

O processo `bot.py` inicia o painel e o bot Telegram na própria máquina que hospeda a API. Na tela de configurações, a seção **Inicialização automática do Windows** pode instalar o serviço para iniciar no próximo boot, desativá-lo ou removê-lo. O Windows pedirá confirmação administrativa na máquina hospedeira; a ativação não inicia uma segunda instância enquanto `bot.py` estiver rodando manualmente. O serviço executa como `LocalSystem`, usa o mesmo `.venv` e os mesmos arquivos de dados, e grava o log de serviço em `bot-service.log` na pasta do projeto.

Distribua o Oracle Instant Client na pasta `oracle_client`, na raiz do projeto, ao lado de `bot.py` e dos demais arquivos da API. Com `ORACLE_CLIENT_DIR` vazio, a API detecta essa pasta automaticamente e inicializa o cliente Oracle. Coloque as bibliotecas diretamente nessa pasta, sem uma subpasta intermediária. Se a pasta não existir, a API usa o modo Thin. Para uma instalação diferente, configure `ORACLE_CLIENT_DIR` com um caminho absoluto ou relativo à pasta da API. Reinicie o bot para aplicar mudanças no cliente. O caminho da pasta JSON aparece na tela de configurações; `BOT_DATA_DIR` define essa pasta antes da primeira inicialização.

## Execução diária

No PowerShell, na pasta do projeto:

```powershell
.\.venv\Scripts\Activate.ps1
python bot.py
```

No Prompt de Comando, ative com `.venv\Scripts\activate.bat` e execute `python bot.py`. Se a ativação do PowerShell estiver bloqueada, execute diretamente, sem ativar o ambiente:

```powershell
.\.venv\Scripts\python.exe bot.py
```

O terminal informa o endereço do painel; na própria máquina, o padrão é `http://127.0.0.1:8765`. Para parar a execução manual, pressione **Ctrl+C**. Para reiniciar, execute o comando novamente. Evite executar uma instância manual enquanto o serviço do Windows estiver ativo.

## Comandos e consultas no Telegram

Use uma conversa privada com o bot. Os recursos disponíveis dependem das permissões do perfil.

| Comando ou mensagem | Ação |
|---|---|
| `/start` | Iniciar e registrar o usuário para aprovação. |
| `/meuid` | Mostrar o ID do Telegram para cadastro no painel. |
| `/ajuda` | Consultar a ajuda. |
| `/comandos` | Listar os recursos disponíveis ao perfil. |
| Código numérico, como `6` | Consultar por CODPROD, CODAUXILIAR e/ou CODAUXILIAR2, conforme as permissões. |
| Parte do nome, com pelo menos 3 caracteres | Pesquisar produtos e apresentar até dez opções para seleção. |
| Foto do código de barras | Identificar o código e consultar o produto; envie o código inteiro, nítido e iluminado. |
| `/margem` | Iniciar a seleção de departamento, filial e tabela para análise. |
| `/margem 113` | Iniciar a análise pelo departamento 113. |
| `/cancelarmargem` | Cancelar o fluxo de análise por departamento. |

## Diagnóstico rápido

| Situação | O que verificar |
|---|---|
| Oracle OFF ou `ORA-00942` / `ORA-01031` | Confira o usuário e service name na guia Servidor Oracle. O usuário precisa de SELECT e resolução dos nomes das tabelas, inclusive por sinônimos. Use a mesma conexão no Navigator para comparar. |
| Telegram OFF | Confira o token na guia Bot e o acesso à internet. Depois de salvar um token novo, reinicie o processo. |
| Painel não abre | Confirme que `bot.py` está ativo e use o endereço exibido no terminal. Para outra máquina, confira IP, rede e firewall. |
| Alteração visual não aparece | Reinicie o painel e atualize o navegador com **Ctrl+F5**. |
| Consulta falha | Procure as linhas `CONSULTA` e o traceback no terminal: eles identificam usuário, busca, etapa, duração e código do erro. |

Os indicadores no topo podem ser clicados para atualizar a verificação. **OK verde** significa teste bem-sucedido; **OFF vermelho**, configuração ausente ou falha. O teste de preços não garante acesso às tabelas adicionais de custos e departamentos; os detalhes estão na seção de lógica das consultas.

## Aprovação e perfis

As guias **Bot** e **Servidor Oracle** possuem salvamento e testes independentes. Na pasta persistente (`myBotWinthor-dados`, ao lado do projeto, ou a pasta definida por `BOT_DATA_DIR`), os arquivos são:

- `config_bot.json`: Telegram e opções do painel.
- `config_oracle.json`: servidor, usuário, senha e demais opções Oracle.
- `dados_bot.json`: usuários, perfis, permissões e hash da senha do painel.

Na primeira inicialização após atualizar, as configurações do antigo JSON único são transferidas automaticamente para os novos arquivos. Faça backup dos três arquivos; as credenciais continuam armazenadas nos JSONs de configuração. Alterações manuais devem ser feitas com o bot parado.

Quando uma pessoa envia `/start`, seu ID do Telegram é registrado como pendente. O administrador entra no painel pelo endereço IP anunciado no log do bot (porta padrão `8765`), faz login e salva a aprovação e as permissões daquele usuário. Por padrão, o painel escuta nas interfaces de rede do computador que executa o bot (`WEB_ADMIN_HOST=0.0.0.0`).

`WEB_ADMIN_HOST` aceita `127.0.0.1` para acesso somente local ou `0.0.0.0` para aceitar conexões de rede. Na rede privada, limite a porta `WEB_ADMIN_PORT` no firewall aos dispositivos administrativos confiáveis. Não exponha o painel diretamente à internet. Se usar um proxy HTTPS, configure `WEB_HTTPS_ONLY=true` para que o cookie de sessão seja enviado apenas em HTTPS.

O controle de cada perfil inclui:

- `consulta_preco`: permissão-base para consultar preços.
- `buscar_por_foto`: localizar produto pela leitura de código de barras em imagem.
- `buscar_codprod`, `buscar_codauxiliar` e `buscar_codauxiliar2`: campos de busca numérica habilitados individualmente.
- `ver_margem_produto`: exibir a margem na consulta de um produto.
- `ver_margem_departamento`: usar `/margem` para análise por departamento.

A antiga permissão `ver_margem` é migrada para as duas permissões, preservando o acesso existente. Depois, cada opção pode ser alterada independentemente no painel.
- `ver_custos`: exibir custos e dados da última entrada.

Os acessos a preço, foto e margem/custos exigem que o perfil esteja aprovado. A permissão de margem não revela o valor do custo; isso é controlado separadamente por `ver_custos`. O administrador definido em `TELEGRAM_ADMIN_ID` mantém acesso total.

## Persistência e migração

Usuários, permissões e senha com hash ficam em `dados_bot.json`; as configurações ficam em `config_bot.json` e `config_oracle.json`, dentro da mesma pasta de dados separada do código. Por padrão, essa pasta é criada ao lado do projeto com o nome da pasta do projeto seguido de `-dados` (por exemplo, `myBotWinthor-dados`). Defina `BOT_DATA_DIR` no `.env` para usar outro caminho persistente. Cada arquivo é atualizado atomicamente e não deve ser editado enquanto a API estiver rodando.

Para reinstalar a API ou migrar para outro computador/versão, pare o serviço, copie a pasta de dados inteira e configure `BOT_DATA_DIR` para apontar para a cópia no novo computador. Ela inclui configurações confidenciais, como token do Telegram e senha do Oracle; proteja o acesso à pasta e não a envie ao Git. A senha do painel é armazenada como hash; uma troca encerra as outras sessões ativas.

Se o arquivo JSON ainda não existir e houver um `permissoes.db` da versão anterior ao lado do código, os perfis, as permissões, configurações e hash da senha são migrados automaticamente para o JSON. O banco antigo não é apagado. Novos usuários ficam sem permissões até o administrador aprovar e salvar o perfil no painel.
