# Instalação e atualização no Windows

## Pacotes

Use `myBotWinthor-cliente.zip`: extraia e execute `Instalar-myBotWinthor.exe`. O cliente não precisa de Python nem do código-fonte. O instalador funciona por usuário, sem exigir administrador no fluxo normal.

Para execução portátil, extraia `myBotWinthor-portatil.zip` inteiro e mantenha `_internal` junto de `myBotWinthor.exe`. Nunca misture arquivos de versões diferentes. Os pacotes não incluem dados de clientes, credenciais, `.env` ou Oracle Client.

## Onde ficam os arquivos

| Conteúdo | Caminho padrão |
|---|---|
| Programa instalado | `%LOCALAPPDATA%\Programs\myBotWinthor\versoes\<versao>` |
| Dados de instalações novas | `%LOCALAPPDATA%\myBotWinthor\dados` |
| Logs | `<pasta-de-dados>\logs\aplicacao.log` |

O gerenciador mostra a pasta de dados efetiva e oferece **Pasta de dados** para abri-la. Esse caminho pode ser diferente se você escolheu dados antigos durante a instalação. No uso pelo código, o padrão continua sendo a pasta vizinha `myBotWinthor-dados`, ou `BOT_DATA_DIR`.

## Atualizar sem perder cadastros

1. Pare a aplicação antiga e saia do gerenciador. Se houver serviço legado, pare e desative esse serviço. Faça backup externo da pasta de dados e do `.env` antigo.
2. Execute o novo instalador. Selecione a pasta que contém `dados_bot.json`, normalmente `myBotWinthor-dados` na migração do código, ou a pasta já usada pela instalação anterior. Não selecione a pasta do código/Python.
3. A pasta selecionada continua sendo usada diretamente, sem mover nem mesclar os JSONs. Não a apague ao remover arquivos antigos. Atualizações seguintes lembram o caminho selecionado.
4. Confira a pasta exibida no gerenciador e as conexões em **Configurações**. O `.env` antigo não é importado automaticamente; se era sua única configuração, informe novamente os dados.

Nunca substitua os dados por uma pasta vazia. Não execute duas versões simultaneamente nem use o mesmo token em duas máquinas.

## Configurar e executar

Abra o atalho **myBotWinthor** e clique em **Configurações** para preencher Oracle, Telegram e a porta do painel. Senhas e token vazios mantêm os valores anteriores. Pare a aplicação antes de editar as configurações.

Clique em **Iniciar** e depois em **Abrir painel**. O primeiro acesso local é `admin/admin`; troque a senha imediatamente. Instalações novas começam em `127.0.0.1`. O painel permite configurar o acesso em rede. Oracle Client, quando necessário, deve estar em uma pasta local confiável e compatível com Windows x64.

O cartão do gerenciador mostra o estado do processo local. Confira a conexão Oracle e Telegram no painel. **Parar** encerra o processo; **Reiniciar** o inicia novamente após a parada. Os botões acompanham o estado atual. **Acompanhar últimas linhas** controla a rolagem automática dos logs. Arquivos de log acima de 10 MiB são rotacionados na inicialização.

## Bandeja e início com o Windows

A opção **Iniciar com o Windows** inicia o bot/API na bandeja após entrar na conta. É opcional e pode ser alterada no gerenciador instalado. Não instala serviço Windows.

Fechar ou minimizar a janela mantém a aplicação em execução. Para encerrar completamente, use **Sair** no gerenciador ou **Sair e parar a aplicação** no menu do ícone ao lado do relógio. Se a bandeja estiver indisponível, use a janela do gerenciador.

O portátil não registra a instalação automaticamente. Para reutilizar dados pelo assistente, configurar início automático ou usar o desinstalador registrado, utilize o instalador.

## Oracle OFF após atualizar

O painel exibe códigos Oracle/DPY sanitizados. Confira a pasta de dados ativa e os dados da conexão antes de modificá-los.

| Código | Orientação |
|---|---|
| `DPY-3016` | Pode indicar dependências criptográficas ausentes. Instale a distribuição completa mais recente e reinicie. |
| `DPY-3010` / `DPY-3015` | A conexão exige Oracle Client. Configure uma pasta local compatível e reinicie. |
| `DPI-1047` | Confira o caminho e a versão x64 do Oracle Client. |
| `DPY-2019` | Reinicie a aplicação para aplicar a troca de modo Oracle. |

Não compartilhe `config_oracle.json`, tokens ou senhas ao pedir suporte. O diagnóstico técnico local do executável está em [Desenvolvimento](desenvolvimento.md#diagnóstico-oracle-do-executável).

## Remover ou voltar à versão anterior

Com a aplicação parada, as versões anteriores ficam em `versoes`; cada versão guarda seu `desktop.json` apontando para os dados. Guarde backups fora da pasta do programa e não inicie versões simultaneamente.

Para remover, use **Desinstalar-myBotWinthor.exe** na pasta do programa ou **Aplicativos instalados** do Windows. O desinstalador encerra a aplicação e remove inicialização automática, atalhos e arquivos reconhecidos.

A opção **Apagar também cadastros, login, senhas, tokens, fórmulas e logs** começa desmarcada. Marque e confirme somente se deseja apagar esses dados permanentemente. Arquivos desconhecidos e backups externos são preservados; o Oracle nunca é apagado. Remover o serviço legado `MyBotWinthorBot`, se existir, solicita autorização administrativa (UAC).

## Validação dos pacotes

Os executáveis são Windows x64 e ainda não têm assinatura digital; o Windows/SmartScreen pode pedir confirmação. Os hashes dos pacotes permitem conferir integridade.

Foram validados o pacote, as dependências gráficas, o ciclo local de iniciar/parar sem token e uma conexão Oracle Thin pelo executável instalado. O diagnóstico executou apenas `SELECT 1 FROM DUAL`; não valida tabelas WinThor nem o polling Telegram. Não houve validação em Windows limpo, e a apresentação do ícone da bandeja precisa ser conferida numa sessão Windows que permita criar o ícone.
