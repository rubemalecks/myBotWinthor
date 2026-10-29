"""Manutenção administrativa das regras usadas pelo bot."""
from asyncio import to_thread
from fastapi import Request, HTTPException
from modulos.database import listar_catalogo_formulas, consultar_calculos_formulas_produto
from modulos.regras_margem import (PADRAO, obter_regras, normalizar_regra,
    validar_catalogo, salvar_regra, expressao_regra)
from modulos.permissoes import gravar_regra_margem


def instalar_formulas(app, autenticar, csrf):
    @app.get('/api/formulas')
    def listar(request: Request):
        autenticar(request)
        try:
            return {'padrao': PADRAO, 'regras': obter_regras()}
        except RuntimeError as erro:
            raise HTTPException(503, str(erro)) from erro

    @app.get('/api/formulas/catalog')
    async def catalogo(request: Request):
        autenticar(request)
        try:
            return {'campos': await to_thread(listar_catalogo_formulas)}
        except Exception as erro:
            raise HTTPException(503, 'Não foi possível carregar os campos. Verifique a conexão e as permissões Oracle.') from erro

    @app.post('/api/formulas/preview')
    async def previa(request: Request):
        autenticar(request)
        csrf(request)
        try:
            dados = await request.json()
            if not isinstance(dados, dict) or set(dados) != {'codprod', 'regra'}:
                raise ValueError('Informe o CODPROD e a regra.')
            codigo = str(dados['codprod'])
            if not codigo.isascii() or not codigo.isdecimal() or not 0 < int(codigo) < 10**15:
                raise ValueError('Informe um CODPROD positivo.')
            regra = normalizar_regra(dados['regra'], salvar=False)
            campos = await to_thread(listar_catalogo_formulas)
            validar_catalogo(regra, campos)
            linhas = await to_thread(consultar_calculos_formulas_produto, codigo, rascunho=regra)
            return {'linhas': linhas, 'expressao': expressao_regra(regra)}
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro
        except Exception as erro:
            raise HTTPException(503, 'Não foi possível simular. Verifique a conexão, as tabelas e as regras salvas.') from erro

    @app.post('/api/formulas/draft')
    async def confirmar_rascunho(request: Request):
        autenticar(request)
        csrf(request)
        try:
            regra = normalizar_regra(await request.json(), salvar=False)
            return {'expressao': expressao_regra(regra)}
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro

    @app.put('/api/formulas')
    async def salvar(request: Request):
        autenticar(request)
        csrf(request)
        try:
            dados = await request.json()
            regra = normalizar_regra(dados)
            identificador = dados.get('id')
            campos = await to_thread(listar_catalogo_formulas)
            await to_thread(salvar_regra, regra, campos, identificador)
            return {'regras': obter_regras()}
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro
        except Exception as erro:
            raise HTTPException(503, 'Não foi possível salvar a fórmula. Verifique o Oracle e a pasta de dados.') from erro

    @app.delete('/api/formulas/{identificador}')
    def remover(identificador: str, request: Request):
        autenticar(request)
        csrf(request)
        try:
            gravar_regra_margem('remover', identificador=identificador)
            return {'regras': obter_regras()}
        except ValueError as erro:
            raise HTTPException(400, str(erro)) from erro


HTML_FORMULAS = '''
<style>
  #formula-panel { margin:20px 0 28px; }
  #formula-panel .formula-intro { margin-bottom:20px; }
  #formula-panel .formula-intro p { max-width:75ch; }
  #formula-panel .formula-base { padding:14px 16px; border-left:3px solid var(--accent); background:var(--field); border-radius:8px; margin:16px 0; }
  #formula-panel .formula-base small { display:block; color:var(--muted); margin-bottom:5px; }
  #formula-panel .formula-step { padding:22px; border:1px solid var(--border); border-radius:12px; margin:16px 0; min-width:0; }
  #formula-panel h3 { border:0; padding:0; margin:0 0 6px; color:var(--text); font-size:1rem; }
  #formula-panel .formula-step-heading { display:flex; gap:12px; align-items:center; margin-bottom:16px; }
  #formula-panel .formula-step-number { flex:none; display:grid; place-items:center; width:30px; height:30px; border-radius:50%; background:var(--field); border:1px solid var(--border); color:var(--accent); font-weight:700; }
  #formula-panel .formula-grid { display:grid; grid-template-columns:minmax(0,1fr) 180px; gap:16px; margin-top:16px; }
  #formula-panel label:not(.formula-check), #formula-panel .formula-input-label { display:flex; flex-direction:column; align-items:stretch; gap:6px; margin:0; min-width:0; font-size:.85rem; }
  #formula-panel select, #formula-panel textarea, #formula-panel input:not([type=checkbox]) { display:block; width:100%; min-width:0; min-height:42px; padding:10px 12px; margin:0; border:1px solid var(--border); border-radius:8px; background:var(--field); color:var(--text); font:inherit; box-sizing:border-box; }
  #formula-panel textarea { resize:vertical; line-height:1.6; min-height:90px; }
  #formula-panel select { cursor:pointer; }
  #formula-panel .formula-check { display:flex; align-items:center; gap:10px; padding:13px 0 0; margin:0; }
  #formula-panel .formula-check input { flex:none; margin:0; }
  #formula-panel .formula-help { color:var(--muted); font-size:.82rem; line-height:1.6; margin:6px 0 0; }
  #formula-panel .formula-actions { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-top:16px; }
  #formula-panel .formula-adjustment { border:1px solid var(--border); background:var(--field); border-radius:10px; padding:16px; margin:12px 0; }
  #formula-panel .formula-adjustment-header { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }
  #formula-panel .formula-adjustment-header strong { font-size:.85rem; }
  #formula-panel .formula-adjustment-fields { display:grid; grid-template-columns:1fr .85fr 1.6fr 1.1fr; gap:12px; align-items:start; }
  #formula-panel .formula-remove { color:var(--muted); padding:5px 9px; font-size:.8rem; }
  #formula-panel .formula-empty { border:1px dashed var(--border); border-radius:8px; padding:18px; text-align:center; color:var(--muted); font-size:.85rem; }
  #formula-panel #formula-adjustments:not(:empty) + .formula-empty { display:none; }
  #formula-panel .formula-simulate { display:flex; gap:12px; align-items:end; margin:16px 0; }
  #formula-panel .formula-simulate label { flex:1; max-width:280px; }
  #formula-panel .formula-simulate button { min-height:42px; }
  #formula-panel .formula-preview-card { background:var(--field); border:1px solid var(--border); border-radius:10px; padding:18px; margin-top:14px; }
  #formula-panel .formula-preview-card h4 { margin:0 0 4px; font-size:.95rem; }
  #formula-panel .formula-preview-table { width:100%; border-collapse:collapse; margin:14px 0; font-size:.88rem; }
  #formula-panel .formula-preview-table th, #formula-panel .formula-preview-table td { padding:10px 8px; text-align:right; border-bottom:1px solid var(--border); }
  #formula-panel .formula-preview-table th:first-child, #formula-panel .formula-preview-table td:first-child { text-align:left; }
  #formula-panel .formula-preview-table td:last-child { color:var(--accent); font-weight:600; }
  #formula-panel .formula-expression { overflow-wrap:anywhere; margin:10px 0; font-size:.82rem; }
  #formula-panel .formula-scope { display:grid; gap:16px; margin-top:16px; }
  #formula-panel details { margin-top:18px; } #formula-panel details > summary { font-size:.85rem; color:var(--accent); }
  #formula-panel details[open] > summary { margin-bottom:12px; }
  #formula-panel .formula-footer { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:18px 0; }
  #formula-panel #formula-delete:not(:disabled) { color:#f48c91; }
  #formula-panel #formula-status:not(:empty) { padding:12px 16px; border-left:3px solid var(--accent); background:var(--field); border-radius:8px; }
  @media(max-width:850px) { #formula-panel .formula-adjustment-fields { grid-template-columns:1fr 1fr; } }
  @media(max-width:540px) { #formula-panel .formula-grid, #formula-panel .formula-adjustment-fields { grid-template-columns:1fr; } #formula-panel .formula-step { padding:16px; } #formula-panel .formula-simulate { align-items:stretch; flex-direction:column; } #formula-panel .formula-simulate label { max-width:none; } #formula-panel .formula-preview-card { padding:12px; } }
</style>
<section id="formula-panel" aria-label="Manutenção de fórmulas">
  <div class="formula-intro"><h2>Manutenção de fórmulas</h2>
  <p class="muted">Configure o cálculo de lucro exibido no bot. Monte os ajustes, teste com um produto e escolha onde aplicar.</p>
  <div class="formula-base"><small>Cálculo padrão · ganho sobre o custo</small><strong>(Preço de venda − Custo de entrada) ÷ Custo de entrada × 100</strong></div>
  <p class="formula-help">Manutenção exclusiva do painel. As permissões do bot continuam valendo e os dados do Oracle permanecem preservados.</p></div>
  <label for="formula-saved">Editar uma fórmula salva ou começar uma nova<select id="formula-saved"><option value="">Nova fórmula</option></select></label>
  <form id="formula-form">
    <section class="formula-step"><div class="formula-step-heading"><span class="formula-step-number">1</span><div><h3>Identifique a fórmula</h3><p class="formula-help">Salve um nome fácil de reconhecer.</p></div></div>
    <div class="formula-grid"><label for="formula-name">Nome da fórmula<input type="text" id="formula-name" maxlength="100" placeholder="Ex.: Custo com frete" required></label>
    <label for="formula-priority">Prioridade<input type="number" id="formula-priority" min="0" max="10000" value="100" required><small class="formula-help">Menor número tem preferência.</small></label></div>
    <label class="formula-check"><input type="checkbox" id="formula-active">Ativar nas consultas do bot após salvar</label></section>
    <section class="formula-step"><div class="formula-step-heading"><span class="formula-step-number">2</span><div><h3>Monte os ajustes</h3><p class="formula-help">Ajuste o custo ou preço antes do cálculo, ou o percentual resultante.</p></div></div>
    <div class="formula-base">
      <label for="formula-cost-search">Buscar campo base do custo (origem fixa: PCEST)<input id="formula-cost-search" type="search" placeholder="Ex.: CUSTOREAL, CUSTOFIN"></label>
      <label for="formula-cost-field">Campo usado antes dos ajustes<select id="formula-cost-field"><option value="PCEST.CUSTOULTENT">CUSTOULTENT — padrão</option></select></label>
      <p id="formula-cost-help" class="formula-help">O custo escolhido será usado na subtração e no divisor. Os ajustes de custo serão aplicados sobre ele.</p>
      <p class="formula-help">Somente colunas numéricas de PCEST. A escolha é própria desta fórmula e não altera o campo exibido na mensagem de custos.</p>
    </div>
    <div id="formula-adjustments"></div>
    <div class="formula-empty">Nenhum ajuste adicionado. A fórmula usa o cálculo padrão.</div>
    <div class="formula-actions"><button type="button" id="formula-add" class="secondary">+ Adicionar ajuste</button><button type="button" id="formula-catalog" class="secondary">Atualizar campos disponíveis</button><button type="button" id="formula-confirm">Confirmar fórmula</button></div>
    <p class="formula-help">Confirme os ajustes para atualizar a fórmula abaixo. Se houver um CODPROD informado, a simulação será recalculada. Para aplicar no bot, use Salvar fórmula ao final.</p>
    <p id="formula-catalog-status" class="formula-help" role="status"></p>
    </section>
    <section class="formula-step"><div class="formula-step-heading"><span class="formula-step-number">3</span><div><h3>Teste com um produto</h3><p class="formula-help">Compare dados reais por filial e tabela antes de salvar.</p></div></div>
    <div class="formula-base" aria-live="polite"><small>Fórmula para simulação · prévia antes de salvar</small><div id="formula-confirmed-expression" class="formula-expression">Confirme os ajustes para visualizar a fórmula.</div><p id="formula-confirmation-status" class="formula-help" role="status"></p></div>
    <div class="formula-simulate"><label for="formula-product">Código do produto (CODPROD)<input id="formula-product" type="text" inputmode="numeric" placeholder="Ex.: 6"></label>
    <button type="button" id="formula-preview">Simular cálculo</button></div>
    <div id="formula-result" role="status" aria-live="polite"><p class="formula-help">Informe um produto para visualizar o cálculo atual e a simulação.</p></div>
    </section>
    <section class="formula-step"><div class="formula-step-heading"><span class="formula-step-number">4</span><div><h3>Escolha onde aplicar</h3><p class="formula-help">Use uma lista de produtos, um filtro ou todos os produtos.</p></div></div>
    <label class="formula-check"><input id="formula-all" type="checkbox">Aplicar a todos os produtos</label>
    <div class="formula-scope"><label for="formula-products">Produtos específicos<textarea id="formula-products" rows="3" placeholder="Ex.: 6, 12, 1663"></textarea><small class="formula-help">Separe os CODPRODs por vírgula, espaço ou quebra de linha.</small></label>
    <details id="formula-filter-details"><summary>Filtro avançado (WHERE)</summary><label for="formula-where">Condição para aplicar a regra<textarea id="formula-where" rows="3" placeholder="PCPRODUT.CODEPTO = 108 AND PCEST.CODFILIAL = 1" spellcheck="false"></textarea></label>
    <p class="formula-help">Lista e filtro preenchidos são combinados com AND. Aceita comparações, IN, LIKE, IS NULL, AND, OR e NOT. Em sobreposição, vence a primeira regra ativa por prioridade; empates seguem o identificador.</p></details></div>
    <p id="formula-scope-hint" class="formula-help"></p></section>
    <div class="formula-footer"><button type="submit">Salvar fórmula</button><button type="button" id="formula-delete" class="secondary" disabled>Remover fórmula</button></div>
    <p id="formula-status" role="status"></p>
  </form>
  <hr>
</section>
'''

JS_FORMULAS = r'''
    let formulaRules = [], formulaFields = [];
    const fe = id => document.getElementById('formula-' + id);
    const formulaNotice = text => { fe('status').textContent = text; };
    function formulaOptions(select, options, selected) {
      select.replaceChildren();
      for (const [value, label] of options) { const o = document.createElement('option'); o.value=value; o.textContent=label; select.append(o); }
      select.value = selected;
    }
    // FORMULA_COST_FIELDS_START
    function formulaCostOptions(campos, busca, selecionado) {
      const termo = busca.trim().toUpperCase();
      const opcoes = campos.filter(c => c.numerico && /^PCEST\.[A-Z][A-Z0-9_]*$/.test(c.campo))
        .map(c => [c.campo, c.campo.slice(6)]);
      if (!opcoes.some(c => c[0] === 'PCEST.CUSTOULTENT')) opcoes.unshift(['PCEST.CUSTOULTENT', 'CUSTOULTENT — padrão']);
      return opcoes.filter(c => c[0] === selecionado || c[1].includes(termo));
    }
    // FORMULA_COST_FIELDS_END
    let formulaCostSelected = 'PCEST.CUSTOULTENT';
    function formulaRefreshCost() {
      const opcoes = formulaCostOptions(formulaFields, fe('cost-search').value, formulaCostSelected);
      if (!opcoes.some(c => c[0] === formulaCostSelected)) opcoes.push([formulaCostSelected, formulaCostSelected.slice(6) + ' — verificar disponibilidade']);
      formulaOptions(fe('cost-field'), opcoes, formulaCostSelected);
      fe('cost-help').textContent = `Custo base: ${formulaCostSelected}. Usado antes dos ajustes, na subtração e no divisor.`;
    }
    fe('cost-search').addEventListener('input', formulaRefreshCost);
    fe('cost-field').addEventListener('change', () => { formulaCostSelected = fe('cost-field').value; formulaRefreshCost(); });
    async function formulaCatalogLoad() {
      fe('catalog').disabled=true;
      try {
        fe('catalog-status').textContent='Carregando campos disponíveis…';
        formulaFields=(await request('/api/formulas/catalog')).campos;
        [...fe('adjustments').children].forEach(r=>r.refresh()); formulaRefreshCost();
        fe('catalog-status').textContent=`${formulaFields.filter(f=>f.numerico).length} colunas numéricas disponíveis. A origem do custo base permanece PCEST.`;
      } catch(e) { fe('catalog-status').textContent=e.message; }
      finally { fe('catalog').disabled=false; }
    }
    function formulaAdjustment(data = {alvo:'custo',operacao:'+',tipo:'valor',valor:'0'}) {
      const row=document.createElement('div'); row.className='formula-adjustment';
      const header=document.createElement('div'); header.className='formula-adjustment-header';
      const title=document.createElement('strong'); title.textContent='Ajuste';header.append(title);row.append(header);
      const fields=document.createElement('div');fields.className='formula-adjustment-fields';row.append(fields);
      const make = (label, options, value) => {const wrap=document.createElement('label'); wrap.textContent=label; const s=document.createElement('select'); formulaOptions(s,options,value); wrap.append(s); fields.append(wrap); return s;};
      const target=make('Ajustar', [['custo','Custo'],['preco','Preço'],['resultado','Resultado (%)']],data.alvo);
      const operation=make('Operação',[['+','Somar'],['-','Subtrair']],data.operacao);
      const type=make('Tipo',[['valor','Valor fixo / pontos percentuais'],['percentual','Percentual relativo'],['campo','Valor de uma coluna'],['campo_percentual','Percentual de uma coluna']],data.tipo);
      const valueWrap=document.createElement('label'); const valueTitle=document.createElement('span');valueWrap.append(valueTitle);
      const value=document.createElement('input'); value.type='text';value.inputMode='decimal'; value.value=data.valor || '0'; value.placeholder='Ex.: 2,50';valueWrap.append(value);fields.append(valueWrap);
      const fieldWrap=document.createElement('label');fieldWrap.textContent='Buscar e escolher campo numérico';
      const fieldSearch=document.createElement('input');fieldSearch.type='search';fieldSearch.placeholder='Ex.: custo, frete';fieldWrap.append(fieldSearch);
      const field=document.createElement('select');fieldWrap.append(field);fields.append(fieldWrap);
      const fill=()=> {const selected=field.value || data.campo || ''; const termo=fieldSearch.value.trim().toUpperCase(); const opts=formulaFields.filter(f=>f.numerico && (f.campo.includes(termo) || f.campo===selected)).map(f=>[f.campo,f.campo]); if(selected&&!opts.some(o=>o[0]===selected))opts.push([selected,selected]); formulaOptions(field,[['','Selecione uma coluna'],...opts],selected);}; fill(); fieldSearch.addEventListener('input', fill);
      const help=document.createElement('p');help.className='formula-help';row.append(help);
      const visibility=()=> {
        const column=type.value.startsWith('campo');valueWrap.hidden=column;fieldWrap.hidden=!column;
        valueTitle.textContent=type.value==='percentual'?'Percentual (%)':target.value==='resultado'?'Pontos percentuais':'Valor (R$)';
        help.textContent=column?'Busque e selecione uma coluna numérica do catálogo validado. As origens são definidas pela aplicação.':type.value==='percentual'?'Variação relativa: um resultado de 40% com +10% passa a 44%.':target.value==='resultado'?'Pontos percentuais: um resultado de 40% com +5 pontos passa a 45%.':'O valor é somado ou subtraído antes de calcular o percentual de lucro.';
      }; type.addEventListener('change',visibility);target.addEventListener('change',visibility); visibility();
      const remove=document.createElement('button'); remove.type='button';remove.className='secondary formula-remove';remove.textContent='Remover';remove.setAttribute('aria-label','Remover este ajuste');remove.onclick=()=>row.remove();header.append(remove);
      row.read=()=>({alvo:target.value,operacao:operation.value,tipo:type.value,...(type.value.startsWith('campo')?{campo:field.value}:{valor:value.value})}); row.refresh=fill;
      fe('adjustments').append(row);
    }
    function formulaRead() {
      const data={nome:fe('name').value,ativa:fe('active').checked,prioridade:Number(fe('priority').value),todos_produtos:fe('all').checked,
        produtos:fe('all').checked?[]:fe('products').value.split(/[\s,;]+/).filter(Boolean),where:fe('all').checked?'':fe('where').value,ajustes:[...fe('adjustments').children].map(r=>r.read())};
      if(formulaCostSelected !== 'PCEST.CUSTOULTENT') data.campo_custo=formulaCostSelected;
      if(fe('saved').value)data.id=fe('saved').value;return data;
    }
    function formulaEdit() {
      const rule=formulaRules.find(r=>r.id===fe('saved').value)||{nome:'',ativa:false,prioridade:100,produtos:[],where:'',ajustes:[]};
      formulaCostSelected=rule.campo_custo || 'PCEST.CUSTOULTENT'; fe('cost-search').value=''; formulaRefreshCost();
      fe('name').value=rule.nome;fe('active').checked=rule.ativa;fe('priority').value=rule.prioridade;fe('all').checked=!!rule.todos_produtos;
      fe('products').value=rule.produtos.join(', ');fe('where').value=rule.where;fe('adjustments').replaceChildren();rule.ajustes.forEach(formulaAdjustment);
      fe('delete').disabled=!rule.id;fe('result').textContent='Informe um produto e clique em Simular cálculo para comparar.';formulaNotice('');
      fe('confirmed-expression').textContent='Confirme os ajustes para visualizar a fórmula.';fe('confirmation-status').textContent='';
      fe('filter-details').open=!!rule.where;formulaScope();
    }
    async function formulaLoad(selected='') {
      const data=await request('/api/formulas');formulaRules=data.regras;
      formulaOptions(fe('saved'),[['','Nova fórmula'],...formulaRules.map(r=>[r.id,`${r.ativa?'Ativa':'Inativa'} · ${r.prioridade} · ${r.nome}`])],selected);formulaEdit();
    }
    let formulaLoaded=false;
    async function carregarManutencaoFormulas() {
      if (formulaLoaded) return;
      try { await formulaLoad(); formulaLoaded=true; await formulaCatalogLoad(); }
      catch (error) { formulaNotice(error.message); }
    }
    function formulaScope() {
      const all=fe('all').checked;
      fe('products').disabled=all;fe('where').disabled=all;
      fe('scope-hint').textContent=all?'Esta regra será aplicada a todos os produtos. A lista e o filtro ficam fora da aplicação.':'Preencha a lista de produtos ou o filtro avançado para salvar a regra.';
    }
    fe('all').onchange=formulaScope;
    fe('saved').onchange=formulaEdit;
    fe('add').onclick=()=>{if(fe('adjustments').children.length<20)formulaAdjustment();else formulaNotice('Limite de 20 ajustes.');};
    fe('catalog').onclick=formulaCatalogLoad;
    function formulaInvalidate() {
      fe('confirmation-status').textContent='Há alterações. Confirme a fórmula para atualizar a prévia.';
      fe('result').textContent='Aguardando confirmação dos ajustes para atualizar a simulação.';
    }
    fe('form').addEventListener('input', formulaInvalidate);
    fe('form').addEventListener('change', formulaInvalidate);
    fe('adjustments').addEventListener('click', event => { if(event.target.closest('.formula-remove')) formulaInvalidate(); });
    fe('add').addEventListener('click', formulaInvalidate);
    async function confirmarFormula() {
      fe('preview').disabled=true;fe('confirm').disabled=true;
      fe('confirmation-status').textContent='Confirmando ajustes…';
      const regra=formulaRead();const codigo=fe('product').value.trim();
      const signature=JSON.stringify({regra,codigo});
      const unchanged=()=>signature===JSON.stringify({regra:formulaRead(),codigo:fe('product').value.trim()});
      try{
        const draft=await request('/api/formulas/draft',{method:'POST',body:JSON.stringify(regra)});
        if(!unchanged())return;
        fe('confirmed-expression').textContent=draft.expressao;
        fe('confirmation-status').textContent='Fórmula confirmada para prévia. Ainda não salva.';
        if(!codigo){fe('result').textContent='Fórmula incluída na prévia. Informe um CODPROD e clique em Simular cálculo para ver o resultado.';fe('product').focus();return;}
        fe('result').textContent='Recalculando a simulação com a fórmula confirmada…';
        const data=await request('/api/formulas/preview',{method:'POST',body:JSON.stringify({codprod:codigo,regra})});
        if(!unchanged())return;
        const fmt=(v,suffix='')=>v===null||v===undefined?'Indisponível':Number(v).toLocaleString('pt-BR',{maximumFractionDigits:5})+suffix;
        fe('result').replaceChildren();
        if(!data.linhas.length)fe('result').textContent='Produto sem preço ativo ou sem registro de custo/filial disponível.';
        const node=(tag,text,className='')=>{const n=document.createElement(tag);n.textContent=text;n.className=className;return n;};
        for(const l of data.linhas){
          const card=node('section','','formula-preview-card');
          card.append(node('h4',`${l.codprod} · ${l.descricao}`),node('p',`Filial ${l.codfilial} · Tabela ${l.numregiao} — ${l.nome_tabela}`,'formula-help'));
          const table=node('table','','formula-preview-table');const head=node('thead','');const tr=node('tr','');
          ['Cálculo','Atual','Simulação'].forEach(text=>{const th=node('th',text);th.scope='col';tr.append(th);});head.append(tr);table.append(head);
          const body=node('tbody','');
          for(const [label,a,b,suffix] of [['Preço usado (R$)',l.atual.preco,l.simulacao.preco,''],['Custo usado (R$)',l.atual.custo,l.simulacao.custo,''],['Ganho sobre custo',l.atual.percentual,l.simulacao.percentual,'%']]){
            const row=node('tr','');const th=node('th',label);th.scope='row';row.append(th,node('td',fmt(a,suffix)),node('td',fmt(b,suffix)));body.append(row);
          }table.append(body);card.append(table);
          card.append(node('p',!l.simulacao.escopo_definido?'Defina os produtos ou filtro antes de salvar.':l.simulacao.aplicavel?'Este produto atende ao filtro da regra.':'Fora do filtro: a regra não será aplicada a este produto/filial/tabela.','formula-help'));
          const details=node('details','');details.append(node('summary','Ver fórmulas e parâmetros'));
          details.append(node('p',`Atual (${l.atual.nome}): ${l.atual.expressao}`,'formula-expression'),node('p',`Simulação: ${data.expressao}`,'formula-expression'));
          details.append(node('p','Parâmetros: '+(Object.entries(l.parametros).map(([k,v])=>k+' = '+fmt(v)).join('; ')||'Nenhum'),'formula-expression'));
          card.append(details);fe('result').append(card);
        }
      }catch(e){if(unchanged()){fe('confirmation-status').textContent='Não foi possível concluir a prévia.';fe('result').textContent=e.message;}}finally{fe('preview').disabled=false;fe('confirm').disabled=false;}
    }
    fe('confirm').onclick=confirmarFormula;
    fe('preview').onclick=confirmarFormula;
    fe('form').onsubmit=async event=>{event.preventDefault();const btn=event.submitter;if(btn)btn.disabled=true;try{const data=formulaRead();const saved=await request('/api/formulas',{method:'PUT',body:JSON.stringify(data)});const selected=saved.regras.find(r=>r.id===data.id||r.nome===data.nome.trim());await formulaLoad(selected?.id||'');formulaNotice('Fórmula salva. As regras ativas valem nas próximas consultas do bot.');setTimeout(()=>formulaNotice(''),2500);}catch(e){formulaNotice(e.message);}finally{if(btn)btn.disabled=false;}};
    fe('delete').onclick=async()=>{if(!fe('saved').value||!confirm('Remover esta fórmula?'))return;try{await request('/api/formulas/'+fe('saved').value,{method:'DELETE'});await formulaLoad();formulaNotice('Fórmula removida.');setTimeout(()=>formulaNotice(''),2500);}catch(e){formulaNotice(e.message);}};
'''
