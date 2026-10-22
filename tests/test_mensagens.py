import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from modulos import bot, mensagens, permissoes
from modulos.formulas import explicar_formula
from modulos.margem_departamento import formatar_relatorio


class MensagensTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'dados_bot.json'
        self.patch = patch.object(permissoes, 'ARQUIVO_DADOS', self.path)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_todos_os_padroes_e_exemplos_sao_validos_sem_criar_arquivos(self):
        for chave, modelo in mensagens.MODELOS.items():
            with self.subTest(chave=chave):
                texto = mensagens.previa_modelo(chave, modelo['padrao'])
                self.assertTrue(texto.strip())
                self.assertEqual(mensagens.renderizar_mensagem(chave, **modelo['exemplo']), texto)
        self.assertFalse(self.path.with_name('mensagens.json').exists())

    def test_persistencia_e_restauracao_independente_por_bloco(self):
        mensagens.salvar_modelos({'produto': 'Minha empresa\n{codprod} - {descricao}',
                                 'preco': '{tabela}: {preco}'})
        arquivo = self.path.with_name('mensagens.json')
        self.assertEqual(json.loads(arquivo.read_text(encoding='utf-8'))['preco'], '{tabela}: {preco}')
        self.assertEqual(mensagens.renderizar_mensagem('produto', codprod=6, descricao='Teste'), 'Minha empresa\n6 - Teste')
        mensagens.salvar_modelos({'produto': None})
        modelos = {modelo['id']: modelo for modelo in mensagens.listar_modelos()}
        self.assertFalse(modelos['produto']['personalizado'])
        self.assertTrue(modelos['preco']['personalizado'])
        self.assertFalse(self.path.exists())

    def test_validacao_impede_variaveis_restritas_e_expressoes(self):
        for texto in ('{custo}', '{programado}', '{descricao.__class__}',
                      '{descricao[0]}', '{preco!r}', '{preco:10}', '{}', '{', '', ' ' * 3, 'x' * 2501):
            with self.subTest(texto=texto[:40]), self.assertRaises(ValueError):
                mensagens.salvar_modelos({'preco': texto})
        self.assertFalse(self.path.with_name('mensagens.json').exists())
        with self.assertRaises(ValueError):
            mensagens.salvar_modelos({'desconhecido': 'abc'})

    def test_alteracao_invalida_nao_salva_parte_do_pedido(self):
        with self.assertRaises(ValueError):
            mensagens.salvar_modelos({'produto': 'Empresa: {descricao}', 'preco': '{custo}'})
        self.assertFalse(self.path.with_name('mensagens.json').exists())

    def test_chaves_literais_e_dados_nao_sao_reinterpretados(self):
        self.assertEqual(mensagens.previa_modelo('produto', '{{produto}}: {codprod}'), '{produto}: 1663')
        mensagens.salvar_modelos({'produto': '{descricao}'})
        self.assertEqual(mensagens.renderizar_mensagem('produto', descricao='{custo}'), '{custo}')

    def test_salvamentos_simultaneos_preservam_blocos(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            resultados = [executor.submit(mensagens.salvar_modelos, {chave: texto})
                          for chave, texto in [('produto', 'Novo {codprod}'), ('preco', 'Venda: {preco}')]]
            for resultado in resultados:
                resultado.result()
        salvos = permissoes.obter_mensagens_personalizadas()
        self.assertEqual(len(salvos), 2)

    def test_json_invalido_nao_impede_resposta_padrao_do_bot(self):
        self.path.with_name('mensagens.json').write_text('arquivo inválido', encoding='utf-8')
        with self.assertLogs('modulos.mensagens', level='WARNING'):
            self.assertIn('CONSULTA DE PRODUTO', mensagens.renderizar_mensagem('produto', descricao='Teste', codprod=6))

    def test_customizacao_nao_libera_preco_programado(self):
        mensagens.salvar_modelos({'produto': 'Minha loja: {descricao}\n',
                                 'programado': 'SEGREDO: {programado}\n'})
        produtos = [{'codprod': 6, 'descricao': 'Teste', 'pvenda': 10,
                     'ptabela': 999, 'numregiao': 1, 'nome_tabela': 'VAREJO'}]
        texto = bot.montar_mensagem_precos(produtos)
        self.assertIn('Minha loja: Teste', texto)
        self.assertNotIn('SEGREDO', texto)
        self.assertNotIn('999', texto)
        self.assertIn('SEGREDO', bot.montar_mensagem_precos(produtos, incluir_programado=True))

    def test_formula_customizada_continua_protegendo_custo(self):
        mensagens.salvar_modelos({'formula_valores': 'SEGREDO: {custo}\n',
                                 'formula_resultado': 'Meu lucro: {lucro}\n'})
        texto = explicar_formula(100, 70, exibir_valores=False)
        self.assertIn('Meu lucro: 42,86%', texto)
        self.assertNotIn('SEGREDO', texto)
        self.assertNotIn('70,00000', texto)
        self.assertIn('SEGREDO', explicar_formula(100, 70, exibir_valores=True))

    def test_relatorio_customizado_nao_libera_custos(self):
        mensagens.salvar_modelos({'departamento': 'Minha empresa: {departamento}\n',
                                 'departamento_custos': 'SEGREDO: {custos}\n'})
        linhas = [{'numregiao': 1, 'nome_tabela': 'VAREJO', 'total_precos': 100, 'total_custos': 70,
                   'produtos_validos': 1, 'total_produtos': 1, 'sem_preco': 0, 'sem_custo': 0, 'custo_zero': 0}]
        depto = {'codepto': 10, 'descricao': 'Teste'}
        texto = formatar_relatorio(depto, 1, linhas, incluir_custos=False)
        self.assertIn('Minha empresa: Teste', texto)
        self.assertNotIn('SEGREDO', texto)
        self.assertIn('SEGREDO', formatar_relatorio(depto, 1, linhas, incluir_custos=True))
