# myBotWinthor

Bot Telegram para consultar produtos, preços, custos e margens do WinThor/Oracle, com painel administrativo e gerenciador Windows.

## Entrega ao cliente

Os pacotes são gerados localmente e não acompanham o `git clone`. Gere-os com `gerar_distribuicao.bat`; para entrega pelo GitHub, publique os ZIPs separadamente em [Releases](https://github.com/rubemalecks/myBotWinthor/releases).

Use **`distribuicao/myBotWinthor-cliente.zip`**. Ele contém o instalador, as instruções e os hashes de integridade. Também é possível enviar a pasta `distribuicao/cliente/` inteira. Para execução sem instalação, use `distribuicao/myBotWinthor-portatil.zip` ou a pasta `portatil/` inteira, mantendo `_internal` junto do EXE.

O cliente não precisa de Python. O gerenciador Windows mostra o estado do processo, oferece configuração, logs com acompanhamento opcional das últimas linhas, acesso à pasta de dados e controles de iniciar/parar/reiniciar. Pare a aplicação antes de editar Configurações. Não instala serviço Windows. A inicialização com o Windows é opcional e ocorre na bandeja após o login.

Programa instalado em `%LOCALAPPDATA%/Programs/myBotWinthor/versoes/`. Dados novos em **`%LOCALAPPDATA%/myBotWinthor/dados`**. Em uma atualização, selecione a pasta antiga que contém `dados_bot.json`; ela continuará sendo usada sem mover ou sobrescrever os cadastros. Pare a versão antiga, desative serviços legados e faça backup antes. O caminho efetivo aparece no gerenciador. O `.env` antigo não é importado automaticamente: confira as conexões em Configurações.

Primeiro acesso local ao painel: `admin/admin`; troque a senha antes de liberar a rede. Instalações novas começam apenas em `127.0.0.1`. Oracle Client, se necessário, é configurado em pasta local confiável. Os executáveis ainda não são assinados digitalmente.

## Desenvolvimento

O ambiente validado é Windows x64 com Python 3.14. Na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\iniciar.bat
```

Para executar diretamente sem o BAT, use `.\.venv\Scripts\python.exe bot.py`. O `.env` é opcional; os dados desse modo ficam por padrão na pasta vizinha `myBotWinthor-dados`, ou no caminho de `BOT_DATA_DIR`. Não confunda esse padrão com o do instalador.

Para gerar EXEs, instale as dependências de build e execute:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\gerar_distribuicao.bat
```

Para verificar o código sem conectar ao Oracle/Telegram reais:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

O build monta a distribuição nova antes de publicá-la, preserva a anterior em `.build/distribuicao/anterior-*` e rejeita dados privados no runtime. Veja [Desenvolvimento e distribuição](docs/desenvolvimento.md).

## Organização

```text
modulos/                 implementação do bot, painel, Oracle e permissões
desktop/                 gerenciador, instalador e build Windows
assets/                  identidade visual pública
tests/                   testes sem Oracle/Telegram reais
docs/                    documentação técnica e operacional
distribuicao/            pacotes gerados para clientes (fora do Git)
.build/                  intermediários e distribuições anteriores (fora do Git)
requirements.txt         dependências da aplicação
requirements-build.txt   dependências para gerar os executáveis
bot.py e arquivos BAT    pontos de entrada compatíveis com o uso pelo código
```

`.env`, `.venv`, `oracle_client`, logs e dados são exclusivos de cada ambiente e não são enviados aos clientes nem versionados. Não distribua a pasta do projeto inteira.

## Documentação

- [Instalação e migração do cliente](docs/instalacao.md)
- [Uso do painel e do bot](docs/uso_painel_bot.md)
- [Desenvolvimento e geração de pacotes](docs/desenvolvimento.md)
- [Operação pelo código e backup](docs/operacao.md)
- [Consultas e cálculos](docs/consultas.md)
- [Segurança e limites](docs/seguranca.md)
- [Instruções para agentes](AGENTS.md)


### Bandeja, início automático e desinstalação

O instalador permite iniciar com o Windows, minimizado no ícone ao lado do relógio, após entrar na conta. O menu do ícone abre o painel/gerenciador e controla iniciar, parar, reiniciar e sair. Fechar a janela apenas a oculta; para encerrar completamente, use **Sair e parar a aplicação**. A preferência pode ser alterada no gerenciador.

A instalação registra **Desinstalar-myBotWinthor.exe** na pasta do programa e em Aplicativos instalados do Windows. A remoção encerra os processos e remove atalhos e início automático. Para apagar também login, senhas, tokens, usuários, fórmulas e logs, marque a opção de exclusão dos dados e confirme. A opção começa desmarcada. Backups externos, arquivos desconhecidos e o Oracle são preservados. A remoção opcional do serviço legado MyBotWinthorBot exige UAC; instalações novas não criam serviço Windows.
