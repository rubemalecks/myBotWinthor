"""Verifica as operações do construtor no JavaScript efetivamente servido."""
import ast
from pathlib import Path
import re
import shutil
import subprocess
import unittest


class EditorCustosTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node necessário para validar JavaScript')
    def test_substituicao_inclusao_e_rejeicao_de_destino_obsoleto(self):
        fonte = Path(__file__).resolve().parents[1] / 'modulos' / 'painel_admin.py'
        arvore = ast.parse(fonte.read_text(encoding='utf-8'))
        html = next(ast.literal_eval(n.value) for n in arvore.body
                    if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PAGINA' for t in n.targets))
        codigo = html.split('// COST_BUILDER_START', 1)[1].split('// COST_BUILDER_END', 1)[0]
        testes = r'''
const assert = require('node:assert/strict');
const texto = 'Custo: {custo}\nData: {data_entrada}\n';
const alvo = String(camposCustoNoTexto(texto)[0].inicio);
assert.equal(aplicarCampoCusto(texto, alvo, 'pcest_custoreal', ''), 'Custo: {pcest_custoreal}\nData: {data_entrada}\n');
assert.equal(aplicarCampoCusto('Data: {data_entrada}', 'add', 'pcest_custofin', 'Financeiro'), 'Data: {data_entrada}\nFinanceiro: {pcest_custofin}\n');
assert.equal(camposCustoNoTexto('{{custo}} {custo} {PCEST_CUSTOREAL}').length, 2);
assert.throws(() => aplicarCampoCusto('Mensagem alterada', alvo, 'pcest_custoreal', ''));
for (const campo of ['PCNFENT.CUSTOREAL', 'pcest_custo;DELETE', 'pcest_custo.real']) {
  assert.throws(() => aplicarCampoCusto(texto, alvo, campo, ''));
}
assert.throws(() => aplicarCampoCusto(texto, 'add', 'pcest_custoreal', '{custo}'));
assert.throws(() => aplicarCampoCusto(texto, 'add', 'pcest_custoreal', ''));
'''
        resultado = subprocess.run([shutil.which('node'), '-e', codigo + testes], capture_output=True, text=True, timeout=15)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertNotIn('id="message-cost-table"', html)
        self.assertIn('Origem fixa: PCEST', html)

    @unittest.skipUnless(shutil.which('node'), 'Node necessário para validar JavaScript')
    def test_selecao_formula_so_oferece_campos_numericos_de_pcest(self):
        fonte = Path(__file__).resolve().parents[1] / 'modulos' / 'painel_formulas.py'
        arvore = ast.parse(fonte.read_text(encoding='utf-8'))
        js = next(ast.literal_eval(n.value) for n in arvore.body
                  if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'JS_FORMULAS' for t in n.targets))
        codigo = js.split('// FORMULA_COST_FIELDS_START', 1)[1].split('// FORMULA_COST_FIELDS_END', 1)[0]
        testes = r'''
const assert = require('node:assert/strict');
const campos = [{campo:'PCEST.CUSTOREAL',numerico:true},{campo:'PCEST.TEXTO',numerico:false},{campo:'PCTABPR.PVENDA',numerico:true}];
assert.deepEqual(formulaCostOptions(campos, '', 'PCEST.CUSTOULTENT').map(c=>c[0]), ['PCEST.CUSTOULTENT','PCEST.CUSTOREAL']);
assert.deepEqual(formulaCostOptions(campos, 'real', '').map(c=>c[0]), ['PCEST.CUSTOREAL']);
assert.deepEqual(formulaCostOptions(campos, 'inexistente', 'PCEST.CUSTOREAL').map(c=>c[0]), ['PCEST.CUSTOREAL']);
'''
        resultado = subprocess.run([shutil.which('node'), '-e', codigo + testes], capture_output=True, text=True, timeout=15)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
