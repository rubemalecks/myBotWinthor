# Desenvolvimento e distribuição

## Áreas do projeto

`modulos/` é a implementação compartilhada pelo executável e pelo código. `desktop/` contém `launcher.py` (controle gráfico e worker), `installer.py` (instalação por usuário), `common.py` (caminhos/validação), `build_windows.py` (publicação) e a especificação PyInstaller. Os arquivos Python da raiz são pequenos pontos de entrada. Os módulos de serviço Windows são compatibilidade legada; não são usados na instalação normal.

A estrutura existente de módulos/imports foi preservada. Não é necessário copiar código para dentro do pacote do cliente. Configuração, persistência, regras de permissão e SQL são únicos para os dois modos de execução.

## Preparar o ambiente

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

Para rodar sem gerar executáveis, basta `requirements.txt`. O PyInstaller é ferramenta de desenvolvimento, não requisito do cliente. As dependências de teste usadas hoje estão no conjunto da aplicação. Para os testes, use uma pasta temporária gravável e `python -m unittest discover -s tests`.

## Gerar uma distribuição

Execute `gerar_distribuicao.bat` na raiz ou:

```powershell
.\.venv\Scripts\python.exe -m desktop.build_windows
```

O build usa `.build/windows` para análise/binários intermediários e publica em `distribuicao`. O pacote contém:

```text
distribuicao/
  cliente/                       instalador + guia + pacote.json + SHA256.txt
  portatil/                      gerenciador + _internal + guia + manifesto/hashes
  myBotWinthor-cliente.zip        cliente inteiro, pronto para enviar
  myBotWinthor-portatil.zip       portátil inteiro, pronto para enviar
  LEIA-ME.txt                     orientação para quem distribui
  SHA256.txt                      hashes de toda a distribuição
```

A geração valida os arquivos privados, o ZIP intermediário e sua correspondência byte a byte com o runtime. Monta uma área nova, sem mesclar arquivos antigos. Ao publicar, move a distribuição anterior para `.build/distribuicao/anterior-*`. Se o Windows impedir renomear a pasta raiz, o build preserva essa pasta e troca seu conteúdo, arquivando os arquivos anteriores em `.build/distribuicao/anterior-conteudo-*`. Não mescla runtimes. Se a troca final falhar, tenta restaurar a anterior. Não há remoção automática dos backups; após conferir a versão e guardar as releases necessárias, eles podem ser limpos pelo desenvolvedor. Builds devem ser executados um por vez.

`--output` e `--work` aceitam outros destinos, mantendo as pastas separadas. Não use o diretório do código ou uma pasta de dados como saída. O conteúdo da saída é dedicado ao build e pode ser substituído integralmente.

## O que enviar

Para o cliente comum, envie somente `myBotWinthor-cliente.zip`. Se ele preferir sem instalação, envie `myBotWinthor-portatil.zip`. Não envie `.env`, `.venv`, dados, backups, código-fonte, Oracle Client ou diretórios de build. Os hashes detectam corrupção; não substituem uma assinatura digital ou um canal de distribuição confiável.

Binários são ignorados pelo Git; publique os ZIPs em Releases ou outro canal de distribuição. Scripts, requisitos, documentação e testes são versionáveis. Não existe publicação automática neste projeto.

## Dados e atualização

No código, o padrão é `<projeto>-dados`, ao lado do projeto; no gerenciador instalado/portátil, é `%LOCALAPPDATA%/myBotWinthor/dados`, salvo quando `desktop.json` aponta à pasta antiga escolhida na instalação. `desktop.json` é criado na instalação e nunca é incluído no runtime distribuído. `instalacao.json` fica na raiz do programa instalado para lembrar o caminho no próximo upgrade.

O instalador cria executáveis em diretórios versionados e não substitui cadastros. Uma pasta de dados existente é reutilizada diretamente, sem copiar/mesclar. Guarde backups fora da pasta do programa e não execute versões simultaneamente.

## Verificações antes de entregar

Rode os testes, compile as fontes e valide o executável com `--self-test CAMINHO_JSON` em ambiente temporário. O self-test não inicia polling Telegram nem consultas Oracle. Confira hashes e pacotes com um extrator. Faça validação adicional em Windows limpo e no ambiente do cliente antes de liberar para produção; o teste local não certifica todos os ambientes. Os binários atuais são Windows x64, sem assinatura digital. Há desinstalador com remoção opcional dos dados e inicialização automática opcional após o login na conta Windows.


### Bandeja, início automático e desinstalação

O instalador permite iniciar com o Windows, minimizado no ícone ao lado do relógio, após entrar na conta. O menu do ícone abre o painel/gerenciador e controla iniciar, parar, reiniciar e sair. Fechar a janela apenas a oculta; para encerrar completamente, use **Sair e parar a aplicação**. A preferência pode ser alterada no gerenciador.

A instalação registra **Desinstalar-myBotWinthor.exe** na pasta do programa e em Aplicativos instalados do Windows. A remoção encerra os processos e remove atalhos e início automático. Para apagar também login, senhas, tokens, usuários, fórmulas e logs, marque a opção de exclusão dos dados e confirme. A opção começa desmarcada. Backups externos, arquivos desconhecidos e o Oracle são preservados. A remoção opcional do serviço legado MyBotWinthorBot exige UAC; instalações novas não criam serviço Windows.


## Diagnóstico Oracle do executável

O build inclui explicitamente as primitivas criptográficas usadas pelo modo Thin, que são importadas dinamicamente pelo driver nativo. O self-test valida PBKDF2; apenas importar oracledb não verifica a autenticação. Para diagnóstico local autorizado, use `myBotWinthor.exe --oracle-diagnostic CAMINHO_CONFIG_ORACLE_JSON CAMINHO_RESULTADO_JSON`. Esse comando abre uma única conexão com timeout, inicia transação de leitura e executa apenas SELECT 1 FROM DUAL. O resultado contém sucesso/modo ou classe/códigos de erro, sem credenciais. Não há endpoint público para essa operação. O painel também exibe códigos Oracle/DPY sanitizados quando a conexão falha.

## Verificação da atualização de 30/10/2026

Foram aprovados 223 testes automatizados, compilação das fontes, validação do JavaScript renderizado e conferência de integridade dos pacotes. O executável instalado passou no self-test e no diagnóstico Oracle Thin com SELECT 1 FROM DUAL. Essa verificação não certifica as tabelas WinThor, o polling Telegram, Windows limpo ou a apresentação do ícone da bandeja fora do ambiente testado. O layout do gerenciador foi conferido visualmente.

O guia principal de instalação em Markdown está em `docs/instalacao.md`; `desktop/INSTALACAO.txt` é a versão de texto incluída nos próximos pacotes gerados. Mantenha os dois alinhados ao alterar o fluxo do cliente.
