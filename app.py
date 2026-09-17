from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import os
from flask_login import LoginManager, login_required, current_user
from auth import auth_bp, inicializar_auth

app = Flask(__name__)
app.secret_key = 'chave_secreta_logistica_2026'

# Filtro para formatar moeda no padrão brasileiro
@app.template_filter('moeda_br')
def formato_moeda_br(valor):
    # Formata com 2 casas decimais e separador de milhar americano (ex: 47,500.00)
    valor_formatado = f"{valor:,.2f}"
    # Inverte os sinais: troca vírgula por X, ponto por vírgula, e o X por ponto
    valor_formatado = valor_formatado.replace(',', 'X').replace('.', ',').replace('X', '.')
    return valor_formatado

# 1. Configurando o endereço do Banco de Dados

# Pergunta: "Existe um banco configurado na nuvem?"
# Se sim, usa ele. Se não (no seu VS Code local), continua no SQLite.
database_url = os.environ.get('DATABASE_URL', 'sqlite:///banco_logistica.db')

# Ajuste técnico: o SQLAlchemy exige o prefixo 'postgresql://'
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
db = SQLAlchemy(app)

# Gerenciador de Acesso
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = "Por favor, faça login para acessar o sistema."
login_manager.login_message_category = "warning"

# Conecta a tabela de usuários e registra as rotas de login
Usuario = inicializar_auth(app, db, login_manager)
app.register_blueprint(auth_bp)

# --- MOLDE 0: EMPRESA (O Isolamento do SaaS) ---
class Empresa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    razao_social = db.Column(db.String(150), nullable=False)
    cnpj = db.Column(db.String(20), unique=True, nullable=True)
    plano_assinatura = db.Column(db.String(50), default='Básico') # Básico, Premium, Standard
    
# --- MOLDE 1: CENTRO DE DISTRIBUIÇÃO ---
class CentroDistribuicao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    # A etiqueta de segurança: Quem é o dono deste CD?
    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False) 
    nome = db.Column(db.String(100), nullable=False)
    metragem = db.Column(db.Float, nullable=False)
    capacidade_paletes = db.Column(db.Integer, nullable=False)

# Molde para os Custos/Faturas de cada CD
class CustoCD(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cd_id = db.Column(db.Integer, db.ForeignKey('centro_distribuicao.id'), nullable=False)
    mes_referencia = db.Column(db.String(7), nullable=False)  # Ex: "2026-09"
    descricao_item = db.Column(db.String(150), nullable=False) # Ex: Aluguel, Fita Stretch
    tipo_custo = db.Column(db.String(50), nullable=False)      # Fixo, Variável ou Mão de Obra
    valor = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(50), nullable=False, default='Outros')

# --- MOLDE 3: OPERAÇÕES DOS CLIENTES (Faturamento e Ocupação) ---
class OperacaoCliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cd_id = db.Column(db.Integer, db.ForeignKey('centro_distribuicao.id'), nullable=False)
    mes_referencia = db.Column(db.String(7), nullable=False, default="2026-09") # Garantindo a existência da coluna
    cliente_nome = db.Column(db.String(100), nullable=False)
    paletes_ocupados = db.Column(db.Float, nullable=False)
    
    # Novas colunas de Faturamento Solicitadas pelo Sócio
    fat_armazenagem = db.Column(db.Float, default=0.0)
    fat_transporte = db.Column(db.Float, default=0.0)
    fat_manuseio = db.Column(db.Float, default=0.0)
    
    custo_variavel = db.Column(db.Float, nullable=False)

    # Propriedade mágica: Soma as três frentes para manter a compatibilidade com o resto do sistema
    @property
    def faturamento(self):
        return self.fat_armazenagem + self.fat_transporte + self.fat_manuseio
    
# --- MOLDE 4: MOVIMENTAÇÃO FÍSICA (Inbound e Outbound) ---
class MovimentacaoFisica(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cd_id = db.Column(db.Integer, db.ForeignKey('centro_distribuicao.id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('operacao_cliente.id'), nullable=False)
    data_operacao = db.Column(db.String(10), nullable=False)  # Ex: "2026-09-05"
    tipo_fluxo = db.Column(db.String(10), nullable=False)     # "Inbound" (Entrada) ou "Outbound" (Saída)
    paletes = db.Column(db.Float, default=0.0)
    caixas = db.Column(db.Integer, default=0)

    # Cria a amarração direta para sabermos o nome do cliente sem buscas manuais
    cliente = db.relationship('OperacaoCliente', backref='movimentacoes')

# A Pergunta: "O banco de dados conectado já possui todas as tabelas necessárias?"
# A Ordem: "Se não possuir, crie todas agora mesmo antes de receber acessos!"
with app.app_context():
    db.create_all()

# 3. Rota da tela de cadastro
@app.route('/cadastro', methods=['GET', 'POST'])
@login_required
def tela_cadastro():
    if request.method == 'POST':
        nome_digitado = request.form.get('nome_cd')
        metragem_digitada = request.form.get('metragem_m2') or 0
        capacidade_digitada = request.form.get('capacidade_paletes') or 0

        novo_cd = CentroDistribuicao(
            empresa_id=current_user.empresa_id, # <-- AQUI ESTÁ O CARIMBO DE ISOLAMENTO (SaaS)
            nome=nome_digitado,
            metragem=float(metragem_digitada),
            capacidade_paletes=int(capacidade_digitada)
        )

        db.session.add(novo_cd)
        db.session.commit()
        
        flash("Base cadastrada com sucesso!", "success")
        return redirect(url_for('tela_cadastro'))

    # A LEITURA BLINDADA: Busca APENAS os CDs da empresa logada
    lista_cds = CentroDistribuicao.query.filter_by(empresa_id=current_user.empresa_id).all()
    
    return render_template('cadastro_cd.html', cds=lista_cds)

# Rota para editar os dados físicos de um CD existente
@app.route('/editar_cd/<int:cd_id>', methods=['GET', 'POST'])
@login_required
def editar_cd(cd_id):
    # Busca o CD exato no banco de dados
    cd_atual = CentroDistribuicao.query.get_or_404(cd_id)
    
    if request.method == 'POST':
        # Atualiza os dados usando a mesma blindagem (or 0) que aprendemos
        cd_atual.nome = request.form.get('nome_cd')
        cd_atual.metragem = float(request.form.get('metragem_m2') or 0)
        cd_atual.capacidade_paletes = int(request.form.get('capacidade_paletes') or 0)
        
        # Bate o martelo e salva no arquivo físico
        db.session.commit()
        return redirect(url_for('tela_cadastro'))
        
    # Se for apenas carregar a página, desenha a tela de edição
    return render_template('editar_cd.html', cd=cd_atual)

@app.route('/excluir_cd/<int:cd_id>', methods=['POST'])
@login_required
def excluir_cd(cd_id):
    cd_para_apagar = CentroDistribuicao.query.get_or_404(cd_id)

    # 1. Investigação de segurança
    total_custos = CustoCD.query.filter_by(cd_id=cd_id).count()
    total_clientes = OperacaoCliente.query.filter_by(cd_id=cd_id).count()

    # 2. A Trava Lógica (Agora enviando um Flash)
    if total_custos > 0 or total_clientes > 0:
        flash("BLOQUEIO DE SEGURANÇA: Este CD já possui faturas ou clientes vinculados. Ele não pode ser excluído.", "danger")
        return redirect(url_for('tela_cadastro'))
    
    # 3. Execução livre
    db.session.delete(cd_para_apagar)
    db.session.commit()
    return redirect(url_for('tela_cadastro'))

@app.route('/custos/<int:cd_id>', methods=['GET', 'POST'])
@login_required
def gerenciar_custos(cd_id):
    cd_atual = CentroDistribuicao.query.get_or_404(cd_id)
    
    # 1. SE O USUÁRIO CLICOU EM SALVAR (POST)
    if request.method == 'POST':
        novo_custo = CustoCD(
            cd_id=cd_id, 
            mes_referencia=request.form.get('mes_ref'),
            descricao_item=request.form.get('descricao'), 
            valor=float(request.form.get('valor')), 
            tipo_custo=request.form.get('tipo'), # Captura do name="tipo"
            categoria=request.form.get('categoria', 'Outros') # A nossa nova coluna
        )
        db.session.add(novo_custo)
        db.session.commit()
        
        flash("Custo adicionado com sucesso!", "success")
        return redirect(url_for('gerenciar_custos', cd_id=cd_id))
        
    # 2. SE O USUÁRIO APENAS ABRIU A TELA (GET)
    custos_cadastrados = CustoCD.query.filter_by(cd_id=cd_id).all()
    
    # --- MATEMÁTICA DO CHECKUP ---
    total_fixo = 0
    for despesa in custos_cadastrados:
        if despesa.tipo_custo == 'Fixo':
            total_fixo += despesa.valor
            
    if cd_atual.capacidade_paletes > 0:
        divisor = cd_atual.capacidade_paletes
        nome_divisor = "Posição Palete"
    else:
        divisor = cd_atual.metragem
        nome_divisor = "m²"
        
    custo_unitario = total_fixo / divisor if divisor > 0 else 0
    
    # ÚNICO RETORNO: O computador finaliza o trabalho enviando TUDO para a tela
    return render_template(
        'gerenciar_custos.html', 
        cd=cd_atual, 
        custos=custos_cadastrados,
        total_fixo=total_fixo,
        divisor=divisor,
        nome_divisor=nome_divisor,
        custo_unitario=custo_unitario
    )

# Rota para deletar um custo lançado errado
@app.route('/excluir_custo/<int:custo_id>', methods=['POST'])
@login_required
def excluir_custo(custo_id):
    # 1. Localiza a despesa exata no banco de dados
    custo_para_apagar = CustoCD.query.get_or_404(custo_id)
    
    # 2. Guarda de qual CD era esse custo para sabermos para onde voltar
    cd_de_origem = custo_para_apagar.cd_id
    
    # 3. Executa a exclusão e bate o martelo
    db.session.delete(custo_para_apagar)
    db.session.commit()
    
    # 4. Recarrega a tela de custos daquele CD específico
    return redirect(url_for('gerenciar_custos', cd_id=cd_de_origem))

# Rota para editar uma despesa já existente
@app.route('/editar_custo/<int:custo_id>', methods=['GET', 'POST'])
@login_required
def editar_custo(custo_id):
    custo = CustoCD.query.get_or_404(custo_id)
    
    if request.method == 'POST':
        custo.mes_referencia = request.form.get('mes_ref')
        custo.descricao_item = request.form.get('descricao')
        custo.valor = float(request.form.get('valor'))
        custo.tipo_custo = request.form.get('tipo')
        custo.categoria = request.form.get('categoria', 'Outros')
        
        db.session.commit()
        flash("Custo atualizado com sucesso!", "success")
        return redirect(url_for('gerenciar_custos', cd_id=custo.cd_id))

    return render_template('editar_custo.html', custo=custo)

@app.route('/rentabilidade/<int:cd_id>', methods=['GET', 'POST'])
@login_required
def rentabilidade_clientes(cd_id):
    cd_atual = CentroDistribuicao.query.get_or_404(cd_id)
    
    # --- 1. O SISTEMA RECALCULA O CUSTO DA POSIÇÃO AUTOMATICAMENTE ---
    custos_cd = CustoCD.query.filter_by(cd_id=cd_id).all()
    total_fixo = sum(c.valor for c in custos_cd if c.tipo_custo == 'Fixo')
    divisor = cd_atual.capacidade_paletes if cd_atual.capacidade_paletes > 0 else cd_atual.metragem
    custo_posicao = total_fixo / divisor if divisor > 0 else 0

   # --- 2. GRAVAÇÃO DO NOVO CLIENTE (Se o usuário enviou o formulário) ---
    if request.method == 'POST':
        novo_cliente = OperacaoCliente(
            cd_id = cd_atual.id,
            cliente_nome = request.form.get('nome_cliente'), # Alinhado com o molde: cliente_nome
            mes_referencia = request.form.get('mes_ref'),
            paletes_ocupados = float(request.form.get('paletes_ocupados') or 0),
            fat_armazenagem = float(request.form.get('fat_armazenagem') or 0),
            fat_transporte = float(request.form.get('fat_transporte') or 0),
            fat_manuseio = float(request.form.get('fat_manuseio') or 0),
            custo_variavel = float(request.form.get('custo_variavel') or 0)
        )
        
        db.session.add(novo_cliente)
        db.session.commit()
        
        flash(f"Cliente {novo_cliente.cliente_nome} registrado com sucesso!", "success")
        return redirect(url_for('rentabilidade_clientes', cd_id=cd_id))
    
    # --- 3. MATEMÁTICA: CALCULANDO O LUCRO DE CADA CLIENTE DA LISTA ---
    operacoes_banco = OperacaoCliente.query.filter_by(cd_id=cd_id).all()
    lista_resultados = [] # Caixa vazia para guardarmos os resultados finais
    
    for op in operacoes_banco:
        # Custo do Cliente = (Espaço Fixo) + (Suor/Variável Direto)
        custo_do_cliente = (op.paletes_ocupados * custo_posicao) + op.custo_variavel
        
        # Lucro = Receita (Faturamento) MENOS Custo do Cliente
        lucro_real = op.faturamento - custo_do_cliente
        
        # Margem (%) = (Lucro DIVIDIDO pelo Faturamento) VEZES 100
        margem_percentual = (lucro_real / op.faturamento) * 100 if op.faturamento > 0 else 0
        
        # Guardando tudo empacotado para enviar para a tela
        lista_resultados.append({
            'id': op.id,
            'nome': op.cliente_nome,
            'mes': op.mes_referencia,
            'fat_arm': op.fat_armazenagem,      # GAVETA 1: Receita de Armazenagem
            'fat_trans': op.fat_transporte,    # GAVETA 2: Receita de Frete
            'fat_man': op.fat_manuseio,        # GAVETA 3: Receita de Handling
            'faturamento': op.faturamento,      # GAVETA TOTAL: Soma calculada pela @property
            'paletes': op.paletes_ocupados,
            'custo': custo_do_cliente,
            'lucro': lucro_real,
            'margem': margem_percentual
        })

    return render_template('rentabilidade.html', cd=cd_atual, custo_posicao=custo_posicao, resultados=lista_resultados)

@app.route('/')
@login_required
def painel_gerencial():
    # 1. Busca apenas os CDs que pertencem à empresa do usuário logado
    todos_cds = CentroDistribuicao.query.filter_by(empresa_id=current_user.empresa_id).all()
    
    # 2. Descobre os IDs desses CDs (Ex: [1, 2, 5])
    meus_cd_ids = [cd.id for cd in todos_cds]
    
    # 3. Busca apenas as Operações (Clientes) que moram dentro dos MEUS CDs
    todas_operacoes = OperacaoCliente.query.filter(OperacaoCliente.cd_id.in_(meus_cd_ids)).all()
    
    # 1. PREPARAÇÃO
    espaco_vendido_por_cd = {}
    faturamento_por_cd = {}
    faturamento_global = 0
    custo_operacional_global = 0
    total_variavel_global = 0
    clientes_rentaveis = clientes_atencao = clientes_deficitarios = 0

    # 2. COLETA DE DADOS (Faturamento e Ocupação)
    for op in todas_operacoes:
        espaco_vendido_por_cd[op.cd_id] = espaco_vendido_por_cd.get(op.cd_id, 0) + op.paletes_ocupados
        faturamento_por_cd[op.cd_id] = faturamento_por_cd.get(op.cd_id, 0) + op.faturamento
        faturamento_global += op.faturamento
        total_variavel_global += op.custo_variavel

    capacidade_paletes_rede = custo_rede_paletes = capacidade_m2_rede = custo_rede_m2 = 0
    custo_ociosidade_global = receita_potencial_global = posicoes_vazias_rede = 0
    resumo_bases = [] 
    memoria_custo_cd = {}
    
    # --- NOVA LÓGICA DA MINI-DRE: As 4 Gavetas ---
    gavetas_dre = {'Armazenagem': 0, 'Mão de Obra': 0, 'Movimentação': 0, 'Outros': 0}

    # 3. LOOP POR BASE (Inteligência Comercial e Custos)
    for cd in todos_cds:
        custos_fixos_cd = CustoCD.query.filter_by(cd_id=cd.id, tipo_custo='Fixo').all()
        soma_fixo = 0
        
        for conta in custos_fixos_cd:
            soma_fixo += conta.valor
            # Guardando o dinheiro na gaveta correta para o gráfico
            cat = conta.categoria if conta.categoria else 'Outros'
            gavetas_dre[cat] = gavetas_dre.get(cat, 0) + conta.valor
        
        if cd.capacidade_paletes > 0:
            divisor = cd.capacidade_paletes
            unidade = "Paletes"
            capacidade_paletes_rede += divisor
            custo_rede_paletes += soma_fixo
        else:
            divisor = cd.metragem
            unidade = "m²"
            capacidade_m2_rede += divisor
            custo_rede_m2 += soma_fixo
            
        custo_unitario = soma_fixo / divisor if divisor > 0 else 0
        memoria_custo_cd[cd.id] = custo_unitario
        
        espaco_vendido = espaco_vendido_por_cd.get(cd.id, 0)
        espaco_vazio = divisor - espaco_vendido if divisor > espaco_vendido else 0
            
        dinheiro_queimado = espaco_vazio * custo_unitario
        custo_ociosidade_global += dinheiro_queimado
        
        ticket_medio = faturamento_por_cd.get(cd.id, 0) / espaco_vendido if espaco_vendido > 0 else 0
        receita_potencial_global += espaco_vazio * ticket_medio
        
        if unidade == "Paletes":
            posicoes_vazias_rede += espaco_vazio
        
        resumo_bases.append({
            'nome': cd.nome, 'custo_total': soma_fixo, 'capacidade': divisor,
            'unidade': unidade, 'custo_unitario': custo_unitario, 'espaco_vazio': espaco_vazio
        })
        
    media_palete = custo_rede_paletes / capacidade_paletes_rede if capacidade_paletes_rede > 0 else 0
    media_m2 = custo_rede_m2 / capacidade_m2_rede if capacidade_m2_rede > 0 else 0

    # 4. FECHAMENTO DA MINI-DRE (Calculando as Porcentagens)
    total_custo_rede = custo_rede_paletes + custo_rede_m2
    porcentagens_dre = {}
    if total_custo_rede > 0:
        for cat, valor in gavetas_dre.items():
            porcentagens_dre[cat] = (valor / total_custo_rede) * 100
    else:
        porcentagens_dre = {'Armazenagem': 0, 'Mão de Obra': 0, 'Movimentação': 0, 'Outros': 0}

    # 5. RENTABILIDADE DOS CLIENTES
    for op in todas_operacoes:
        custo_total_cliente = (op.paletes_ocupados * memoria_custo_cd.get(op.cd_id, 0)) + op.custo_variavel
        custo_operacional_global += custo_total_cliente
        margem = ((op.faturamento - custo_total_cliente) / op.faturamento * 100) if op.faturamento > 0 else 0
        
        if margem >= 20: clientes_rentaveis += 1
        elif margem > 0: clientes_atencao += 1
        else: clientes_deficitarios += 1
            
    lucro_global = faturamento_global - custo_operacional_global
    margem_global = (lucro_global / faturamento_global * 100) if faturamento_global > 0 else 0
    margem_contribuicao = (faturamento_global - total_variavel_global) / faturamento_global if faturamento_global > 0 else 0
    ponto_equilibrio = total_custo_rede / margem_contribuicao if margem_contribuicao > 0 else 0
    margem_potencial = receita_potencial_global - custo_ociosidade_global

    return render_template(
        'dashboard.html',
        media_palete=media_palete, media_m2=media_m2, bases=resumo_bases,
        faturamento=faturamento_global, custo_ops=custo_operacional_global,
        margem=margem_global, rentaveis=clientes_rentaveis, atencao=clientes_atencao, deficitarios=clientes_deficitarios,
        custo_ociosidade=custo_ociosidade_global, ponto_equilibrio=ponto_equilibrio,
        receita_potencial=receita_potencial_global, margem_potencial=margem_potencial, posicoes_vazias=posicoes_vazias_rede,
        # Enviando os cálculos da DRE para o HTML:
        dre_valores=gavetas_dre, dre_pct=porcentagens_dre
    )

# Rota para deletar um cliente lançado errado
@app.route('/excluir_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def excluir_cliente(cliente_id):
    cliente_para_apagar = OperacaoCliente.query.get_or_404(cliente_id)
    cd_de_origem = cliente_para_apagar.cd_id
    
    # 1. Investigação de segurança: Este cliente tem paletes movimentados no histórico?
    total_movimentacoes = MovimentacaoFisica.query.filter_by(cliente_id=cliente_id).count()

    # 2. A Trava Lógica de Proteção
    if total_movimentacoes > 0:
        flash("BLOQUEIO DE SEGURANÇA: Este cliente possui movimentações físicas registradas. Exclua o histórico de movimentação antes de excluir o cliente.", "danger")
        return redirect(url_for('rentabilidade_clientes', cd_id=cd_de_origem))
    
    # 3. Execução livre (se não houver amarrações)
    db.session.delete(cliente_para_apagar)
    db.session.commit()
    
    flash("Cliente excluído com sucesso!", "success")
    return redirect(url_for('rentabilidade_clientes', cd_id=cd_de_origem))

# Rota para editar os dados de faturamento e ocupação
@app.route('/editar_cliente/<int:cliente_id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(cliente_id):
    cliente_atual = OperacaoCliente.query.get_or_404(cliente_id)
    
    if request.method == 'POST':
        cliente_atual.cliente_nome = request.form.get('nome_cliente')
        cliente_atual.mes_referencia = request.form.get('mes_ref')
        cliente_atual.fat_armazenagem = float(request.form.get('fat_armazenagem') or 0)
        cliente_atual.fat_transporte = float(request.form.get('fat_transporte') or 0)
        cliente_atual.fat_manuseio = float(request.form.get('fat_manuseio') or 0)
        cliente_atual.paletes_ocupados = int(request.form.get('paletes_ocupados') or 0)
        cliente_atual.custo_variavel = float(request.form.get('custo_variavel') or 0)
        
        db.session.commit()
        return redirect(url_for('rentabilidade_clientes', cd_id=cliente_atual.cd_id))
        
    return render_template('editar_cliente.html', cliente=cliente_atual)

@app.route('/movimentacao/<int:cd_id>', methods=['GET', 'POST'])
@login_required
def movimentacao_operacional(cd_id):
    cd_atual = CentroDistribuicao.query.get_or_404(cd_id)
    clientes_base = OperacaoCliente.query.filter_by(cd_id=cd_id).all()

    # 1. Gravação de movimentação física (POST)
    if request.method == 'POST':
        nova_mov = MovimentacaoFisica(
            cd_id=cd_atual.id,
            cliente_id=int(request.form.get('cliente_id')),
            data_operacao=request.form.get('data_operacao'),
            tipo_fluxo=request.form.get('tipo_fluxo'),
            paletes=float(request.form.get('paletes') or 0),
            caixas=int(request.form.get('caixas') or 0)
        )
        db.session.add(nova_mov)
        db.session.commit()
        flash("Movimentação física registrada com sucesso!", "success")
        return redirect(url_for('movimentacao_operacional', cd_id=cd_id))

    # 2. Leitura e agregação dos volumes
    movimentacoes = MovimentacaoFisica.query.filter_by(cd_id=cd_id).order_by(MovimentacaoFisica.id.desc()).all()
    
    total_inbound = sum(m.paletes for m in movimentacoes if m.tipo_fluxo == 'Inbound')
    total_outbound = sum(m.paletes for m in movimentacoes if m.tipo_fluxo == 'Outbound')
    total_paletes_girados = total_inbound + total_outbound
    total_caixas_movimentadas = sum(m.caixas for m in movimentacoes)

    # 3. Inteligência Financeira de Giro (Handling)
    receita_total_manuseio = sum(c.fat_manuseio for c in clientes_base)
    
    # Cálculo das taxas unitárias de giro evitam divisão por zero
    rec_por_palete_giro = (receita_total_manuseio / total_paletes_girados) if total_paletes_girados > 0 else 0.0
    rec_por_caixa_giro = (receita_total_manuseio / total_caixas_movimentadas) if total_caixas_movimentadas > 0 else 0.0

    return render_template(
        'movimentacao.html',
        cd=cd_atual,
        clientes=clientes_base,
        movimentacoes=movimentacoes,
        inbound_paletes=total_inbound,
        outbound_paletes=total_outbound,
        total_paletes_girados=total_paletes_girados,
        total_caixas=total_caixas_movimentadas,
        receita_manuseio=receita_total_manuseio,
        rec_por_palete=rec_por_palete_giro,
        rec_por_caixa=rec_por_caixa_giro
    )

# --- ROTA: EDITAR MOVIMENTAÇÃO FÍSICA ---
@app.route('/editar_movimentacao/<int:mov_id>', methods=['GET', 'POST'])
@login_required
def editar_movimentacao(mov_id):
    mov = MovimentacaoFisica.query.get_or_404(mov_id)
    clientes_base = OperacaoCliente.query.filter_by(cd_id=mov.cd_id).all()

    if request.method == 'POST':
        # 1. Pergunta ao formulário: quais são os novos valores corrigidos?
        mov.data_operacao = request.form.get('data_operacao')
        mov.cliente_id = int(request.form.get('cliente_id'))
        mov.tipo_fluxo = request.form.get('tipo_fluxo')
        mov.paletes = float(request.form.get('paletes') or 0)
        mov.caixas = int(request.form.get('caixas') or 0)

        # 2. Ordem ao banco: comite as alterações nesta linha específica
        db.session.commit()
        flash("Movimentação física atualizada com sucesso!", "success")
        return redirect(url_for('movimentacao_operacional', cd_id=mov.cd_id))

    return render_template('editar_movimentacao.html', mov=mov, clientes=clientes_base)


# --- ROTA: EXCLUIR MOVIMENTAÇÃO FÍSICA ---
@app.route('/excluir_movimentacao/<int:mov_id>', methods=['POST'])
@login_required
def excluir_movimentacao(mov_id):
    mov = MovimentacaoFisica.query.get_or_404(mov_id)
    cd_id_retorno = mov.cd_id

    # Ordem ao banco: delete o registro e confirme a operação
    db.session.delete(mov)
    db.session.commit()
    flash("Apontamento excluído com sucesso!", "success")
    return redirect(url_for('movimentacao_operacional', cd_id=cd_id_retorno))

@app.route('/migrar_saas')
def migrar_saas():
    from sqlalchemy import text
    try:
        # 1. Cria a tabela Empresa (se não existir)
        db.create_all()
        
        # 2. Insere a Empresa Padrão para abrigar os dados atuais
        db.session.execute(text("INSERT INTO empresa (razao_social, plano_assinatura) VALUES ('Logcare Matriz', 'Premium');"))
        db.session.commit()
        
        # 3. Descobre qual foi o ID gerado para essa empresa
        resultado = db.session.execute(text("SELECT id FROM empresa LIMIT 1;"))
        empresa_padrao_id = resultado.scalar()
        
        # 4. Injeta a coluna nova nos dados antigos e carimba com o ID da empresa
        db.session.execute(text(f"ALTER TABLE usuario ADD COLUMN empresa_id INTEGER DEFAULT {empresa_padrao_id};"))
        db.session.execute(text(f"ALTER TABLE centro_distribuicao ADD COLUMN empresa_id INTEGER DEFAULT {empresa_padrao_id};"))
        db.session.commit()
        
        return f"SUCESSO: Banco de produção migrado para SaaS! Dados antigos alocados na Empresa ID {empresa_padrao_id}."
    except Exception as e:
        return f"Ocorreu um erro ou o banco já foi migrado: {e}"


if __name__ == '__main__':
    # 4. Ordem para criar o arquivo do banco antes de ligar o servidor
    with app.app_context():
        db.create_all()
    
    app.run(debug=True)