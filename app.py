from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///banco_logistica.db'
db = SQLAlchemy(app)

# 2. Desenhando a Tabela do Banco de Dados (Molde)
class CentroDistribuicao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    metragem = db.Column(db.Float, nullable=False)
    capacidade_paletes = db.Column(db.Integer, nullable=False)

# Molde para os Custos/Faturas de cada CD
class CustoCD(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cd_id = db.Column(db.Integer, db.ForeignKey('centro_distribuicao.id'), nullable=False)
    mes_referencia = db.Column(db.String(7), nullable=False)  # Ex: "2026-08"
    descricao_item = db.Column(db.String(150), nullable=False) # Ex: Aluguel, Fita Stretch
    tipo_custo = db.Column(db.String(50), nullable=False)      # Fixo, Variável ou Mão de Obra
    valor = db.Column(db.Float, nullable=False)

# Molde para registrar o faturamento e ocupação de cada cliente
class OperacaoCliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cd_id = db.Column(db.Integer, db.ForeignKey('centro_distribuicao.id'), nullable=False)
    nome_cliente = db.Column(db.String(100), nullable=False)
    mes_referencia = db.Column(db.String(7), nullable=False)
    faturamento = db.Column(db.Float, nullable=False) # A receita gerada
    paletes_ocupados = db.Column(db.Integer, nullable=False) # O espaço consumido

# 3. Rota da tela de cadastro
@app.route('/cadastro', methods=['GET', 'POST'])
def tela_cadastro():
    # 1. Separando quem está acessando de quem está enviando dados
    if request.method == 'POST':
        # 2. Desempacotando os dados enviados pelo navegador
        nome_digitado = request.form.get('nome_cd')
        metragem_digitada = request.form.get('metragem_m2') or 0
        capacidade_digitada = request.form.get('capacidade_paletes') or 0

        # 3. Preenchendo o molde da tabela
        novo_cd = CentroDistribuicao(
            nome=nome_digitado,
            metragem=float(metragem_digitada),
            capacidade_paletes=int(capacidade_digitada)
        )

        # 4. Efetuando a gravação física
        db.session.add(novo_cd)
        db.session.commit()

        # 5. Reiniciando o ciclo
     # 1. Buscando todos os registros no banco
    lista_cds = CentroDistribuicao.query.all()
    
    # 2. Enviando a lista para a tela HTML
    return render_template('cadastro_cd.html', cds=lista_cds)

# Rota para editar os dados físicos de um CD existente
@app.route('/editar_cd/<int:cd_id>', methods=['GET', 'POST'])
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
def gerenciar_custos(cd_id):
    # Buscando o CD específico no banco
    cd_atual = CentroDistribuicao.query.get_or_404(cd_id)
    
    if request.method == 'POST':
        novo_custo = CustoCD(
            cd_id=cd_atual.id,
            mes_referencia=request.form.get('mes_ref'),
            descricao_item=request.form.get('descricao'),
            tipo_custo=request.form.get('tipo'),
            valor=float(request.form.get('valor'))
        )
        db.session.add(novo_custo)
        db.session.commit()
        return redirect(url_for('gerenciar_custos', cd_id=cd_id))
    
    # Buscando todos os custos já lançados para este CD
    custos_cadastrados = CustoCD.query.filter_by(cd_id=cd_id).all()
    
    # --- INÍCIO DA MATEMÁTICA DO CHECKUP ---
    total_fixo = 0
    for despesa in custos_cadastrados:
        if despesa.tipo_custo == 'Fixo':
            total_fixo += despesa.valor
            
    # Regra de Rateio: Prioriza palete. Se não tiver (zero), usa metragem.
    if cd_atual.capacidade_paletes > 0:
        divisor = cd_atual.capacidade_paletes
        nome_divisor = "Posição Palete"
    else:
        divisor = cd_atual.metragem
        nome_divisor = "m²"
        
    # Prevenção de erro: não dividir por zero
    custo_unitario = total_fixo / divisor if divisor > 0 else 0
    # --- FIM DA MATEMÁTICA ---

    # Atualize esta última linha para enviar os cálculos para a tela
    return render_template(
        'gerenciar_custos.html', 
        cd=cd_atual, 
        custos=custos_cadastrados,
        total_fixo=total_fixo,
        divisor=divisor,
        nome_divisor=nome_divisor,
        custo_unitario=custo_unitario
    )

    
    return render_template('gerenciar_custos.html', cd=cd_atual, custos=custos_cadastrados)

# Rota para deletar um custo lançado errado
@app.route('/excluir_custo/<int:custo_id>', methods=['POST'])
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
def editar_custo(custo_id):
    # 1. Buscando a despesa exata no banco de dados
    custo_atual = CustoCD.query.get_or_404(custo_id)
    
    if request.method == 'POST':
        # 2. Substituindo os valores antigos pelos novos digitados na tela
        custo_atual.mes_referencia = request.form.get('mes_ref')
        custo_atual.descricao_item = request.form.get('descricao')
        custo_atual.tipo_custo = request.form.get('tipo')
        custo_atual.valor = float(request.form.get('valor'))
        
        # 3. Batendo o martelo para salvar a alteração
        db.session.commit()
        
        # 4. Devolvendo o usuário para a tela do CD correto
        return redirect(url_for('gerenciar_custos', cd_id=custo_atual.cd_id))
        
    # Se for método GET (apenas abrir a página), mostra a tela de edição
    return render_template('editar_custo.html', custo=custo_atual)

@app.route('/rentabilidade/<int:cd_id>', methods=['GET', 'POST'])
def rentabilidade_clientes(cd_id):
    cd_atual = CentroDistribuicao.query.get_or_404(cd_id)
    
    # --- 1. O SISTEMA RECALCULA O CUSTO DA POSIÇÃO AUTOMATICAMENTE ---
    custos_cd = CustoCD.query.filter_by(cd_id=cd_id).all()
    total_fixo = sum(c.valor for c in custos_cd if c.tipo_custo == 'Fixo')
    divisor = cd_atual.capacidade_paletes if cd_atual.capacidade_paletes > 0 else cd_atual.metragem
    custo_posicao = total_fixo / divisor if divisor > 0 else 0

    # --- 2. GRAVAÇÃO DO NOVO CLIENTE (Se o usuário enviou o formulário) ---
    if request.method == 'POST':
        nova_operacao = OperacaoCliente(
            cd_id=cd_atual.id,
            nome_cliente=request.form.get('nome_cliente'),
            mes_referencia=request.form.get('mes_ref'),
            faturamento=float(request.form.get('faturamento')),
            paletes_ocupados=int(request.form.get('paletes_ocupados'))
        )
        db.session.add(nova_operacao)
        db.session.commit()
        return redirect(url_for('rentabilidade_clientes', cd_id=cd_id))
    
    # --- 3. MATEMÁTICA: CALCULANDO O LUCRO DE CADA CLIENTE DA LISTA ---
    operacoes_banco = OperacaoCliente.query.filter_by(cd_id=cd_id).all()
    lista_resultados = [] # Caixa vazia para guardarmos os resultados finais
    
    for op in operacoes_banco:
        # Custo do Cliente = Paletes que ele usa VEZES o custo da posição do CD
        custo_do_cliente = op.paletes_ocupados * custo_posicao
        
        # Lucro = Receita (Faturamento) MENOS Custo do Cliente
        lucro_real = op.faturamento - custo_do_cliente
        
        # Margem (%) = (Lucro DIVIDIDO pelo Faturamento) VEZES 100
        margem_percentual = (lucro_real / op.faturamento) * 100 if op.faturamento > 0 else 0
        
        # Guardando tudo empacotado para enviar para a tela
        lista_resultados.append({
            'nome': op.nome_cliente,
            'mes': op.mes_referencia,
            'faturamento': op.faturamento,
            'paletes': op.paletes_ocupados,
            'custo': custo_do_cliente,
            'lucro': lucro_real,
            'margem': margem_percentual
        })

    return render_template('rentabilidade.html', cd=cd_atual, custo_posicao=custo_posicao, resultados=lista_resultados)

@app.route('/')
def painel_gerencial():
    # 1. Buscando todos os CDs da rede
    todos_cds = CentroDistribuicao.query.all()
    
    # Caixas vazias para os totais globais
    total_custo_rede = 0
    total_capacidade_rede = 0
    resumo_bases = [] 

    # 2. O Loop de Varredura
    for cd in todos_cds:
        # Pega apenas os custos fixos (ociosidade) deste CD
        custos_fixos_cd = CustoCD.query.filter_by(cd_id=cd.id, tipo_custo='Fixo').all()
        soma_fixo = sum(conta.valor for conta in custos_fixos_cd)
        
        # Define se a capacidade é medida em paletes ou m²
        divisor = cd.capacidade_paletes if cd.capacidade_paletes > 0 else cd.metragem
        
        # Calcula o custo da posição deste CD específico
        custo_unitario = soma_fixo / divisor if divisor > 0 else 0
        
        # Alimenta os totais da rede
        total_custo_rede += soma_fixo
        total_capacidade_rede += divisor
        
        # Empacota o resumo desta base para enviar à tela
        resumo_bases.append({
            'nome': cd.nome,
            'custo_total': soma_fixo,
            'capacidade': divisor,
            'custo_unitario': custo_unitario
        })
        
    # 3. Calcula a média geral da empresa
    custo_medio_rede = total_custo_rede / total_capacidade_rede if total_capacidade_rede > 0 else 0

    return render_template(
        'dashboard.html',
        total_rede=total_custo_rede,
        capacidade_rede=total_capacidade_rede,
        media_rede=custo_medio_rede,
        bases=resumo_bases
    )

if __name__ == '__main__':
    # 4. Ordem para criar o arquivo do banco antes de ligar o servidor
    with app.app_context():
        db.create_all()
    
    app.run(debug=True)