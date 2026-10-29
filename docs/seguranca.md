# Revisão de segurança — 29/10/2026

## Escopo

Revisão do código Python e JavaScript, autenticação/sessões, CSRF, todas as rotas HTTP, permissões e callbacks Telegram, SQL dinâmico, fórmulas, imagens e dependências Python instaladas. Testes usam pastas temporárias, mocks e SQLite; não foram feitos testes de carga, consultas reais ao WinThor, análise de plano de execução, mudanças de privilégios ou alterações de firewall.

## Correções

- Guarda global de sessão em `/api/` (exceto login) e CSRF em todas as mutações, preservando as verificações locais das rotas. Sessões anteriores à revisão exigem novo login.
- OpenAPI público desabilitado; validação de Host e Origin, sem confiar em X-Forwarded-For. Uvicorn com `proxy_headers=False` e limite de 32 conexões/tarefas concorrentes.
- Senha padrão `admin` somente em acesso de loopback, sem cabeçalhos de proxy. Troque-a localmente antes da publicação. Um proxy que oculta a origem pode parecer local: nunca publique com a senha padrão.
- Limites de login (10/min/IP, além de bloqueio de 5 minutos após 5 falhas), requisições API (600/min/IP), operações de consulta (60/min/sessão e até 8 simultâneas no HTTP). Estruturas de taxa limitadas a 4.096 chaves por processo. Falhas de login concorrentes contabilizadas após a verificação da senha.
- Corpo de requisição limitado a 64 KiB, inclusive sem Content-Length; prazo de 10 segundos para recebimento. Respostas administrativas sem cache e cabeçalhos contra enquadramento e interpretação de MIME.
- Oracle compartilhado pelo painel e bot: até 4 conexões por processo, conexão com timeout de 5 s, call_timeout de 8 s por viagem ao banco, tentativa de cancelamento em 20 s por sessão e até 5.000 linhas. Sessões em transação de leitura. SQL interno limitado a 256.000 caracteres e validação defensiva contra escrita, comentários e múltiplas instruções no executor comum.
- Bot: até 30 atualizações/min/usuário e 180/min globais, com interrupção antes dos handlers ao exceder. Revalidação de autorização na execução da margem e rejeição de índices negativos/inválidos nos callbacks.
- Parâmetros `PCTABPR.PTABELA` das explicações exigem `ver_preco_programado`, além da permissão para mostrar valores de custo.
- Validação das colunas de custo usa um catálogo por operação, evitando consultas repetidas para cada variável. Busca por produto escapa curingas `%`, `_` e barra invertida, mantendo os valores em binds.
- Oracle Client não pode ser carregado de URL, UNC ou unidade de rede. Navegador de diretórios rejeita UNC explícito. Não há upload de DLL ou executável pela API.
- Imagens limitadas a 5 MiB e 16 megapixels antes de OpenCV. Dependências atualizadas: certifi 2026.10.19 e Pillow 13.0.0.
- Validação de sessão passou a gravar o arquivo de usuários somente quando cria o hash/versão, reduzindo escrita a cada requisição.
- O exemplo manual `consulta_produto.py` deixou de abrir conexão no import e usa o executor protegido.

## Code injection: conclusões e testes

Não foi identificado caminho de execução de Python, JavaScript ou comandos do sistema a partir das entradas avaliadas. Os filtros de fórmula são convertidos em AST com lista restrita de nós; não usam eval/exec. Tabelas e aliases são definidos no código; colunas são validadas e valores são enviados como binds. As escolhas de custo base são restritas a PCEST. Os SELECTs preservam as restrições de filial/região e os filtros de exclusão.

Mensagens usam Formatter com nomes de variáveis permitidos, sem acesso a atributos, índices, conversões ou especificadores de formato. Valores interpolados não são reinterpretados. O painel usa textContent/criação de elementos, sem innerHTML para dados recebidos. A CSP mantém unsafe-inline por causa dos scripts e estilos embutidos; isto é defesa adicional limitada, não uma garantia contra XSS futuro.

Telegram usa polling pelo SDK com o token configurado; não há rota webhook pública nem endpoint para enviar SQL ou código. As mensagens recebidas não são comandos do sistema. Botões revalidam permissões e escopo. Os subprocessos legados usam lista de argumentos ou list2cmdline, ações fixas e sem shell=True; estas rotas continuam exclusivas do administrador com CSRF.

Testes adicionais cobrem payloads de SQL/expressões na API e no Telegram, variáveis com atributos/conversões, subconsultas e múltiplas instruções, carregamento remoto de DLL, Host/Origin forjados, bloqueio de tabelas e rotas sem sessão/CSRF.

## O que precisa de configuração/validação operacional

- Trocar a senha padrão; usar HTTPS em redes não confiáveis e marcar WEB_HTTPS_ONLY=true. Reiniciar para aplicar cookies seguros. Não enviar credenciais por HTTP em rede pública.
- Configurar WEB_ADMIN_URL ao usar nome DNS. Não confiar em cabeçalhos de proxy de origens arbitrárias.
- Conta Oracle dedicada com SELECT mínimo, sem privilégios administrativos, DDL, DML, execução desnecessária de pacotes ou acessos por database link. O aplicativo não alterou nem verificou grants reais.
- Um SELECT comum não bloqueia linhas como FOR UPDATE, mas pode consumir CPU, I/O, memória, UNDO e recursos de otimização. O limite de linhas limita o retorno, não a quantidade de dados processados. Consultas de departamento e buscas por parte do nome exigem avaliação de índices e planos pelo DBA.
- call_timeout vale por round-trip; o cancelamento em 20 s é uma tentativa do driver, não um limite absoluto garantido pelo servidor. Usar Oracle Resource Manager/perfis e controles do servidor para limites fortes.
- Contadores e semáforos são por processo, não distribuídos. Reinícios zeram taxas. Não usar vários workers/instâncias sem limites compartilhados. Ataques distribuídos e saturação de rede precisam de proxy/firewall.
- Restringir por ACL as pastas de código e dados: os JSONs guardam credenciais e o segredo que assina sessões. Quem pode alterar esses arquivos é confiável para a aplicação. Acesso administrativo do painel permite configurar destinos de Oracle/Telegram e administrar permissões; não é um perfil de consulta comum.
- A auditoria de dependências Python não cobre Windows, Oracle Client, firmware, privilégios do serviço nem falhas ainda não publicadas. Sem teste de carga real, não há garantia de ausência de impacto no banco.

## Fontes técnicas

- https://python-oracledb.readthedocs.io/en/latest/api_manual/connection.html (call_timeout/cancel).
- https://docs.oracle.com/en/database/oracle/oracle-database/19/cncpt/data-concurrency-and-consistency.html (consistência de leitura e locks).
