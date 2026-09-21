from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask_mail import Message

auth_bp = Blueprint('auth', __name__)

UsuarioModel = None

def inicializar_auth(app, db, login_manager):
    global UsuarioModel

    class Usuario(UserMixin, db.Model):
        __tablename__ = 'usuario'
        id = db.Column(db.Integer, primary_key=True)
        # O crachá invisível que liga o usuário à sua empresa
        empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
        id = db.Column(db.Integer, primary_key=True)
        email = db.Column(db.String(120), unique=True, nullable=False)
        nome = db.Column(db.String(100), nullable=False)
        senha_hash = db.Column(db.String(256), nullable=False)

        def definir_senha(self, senha_texto):
            self.senha_hash = generate_password_hash(senha_texto)

        def verificar_senha(self, senha_texto):
            return check_password_hash(self.senha_hash, senha_texto)

    UsuarioModel = Usuario

    @login_manager.user_loader
    def carregar_usuario(user_id):
        # A Pergunta: "Quem é o dono da sessão ativa?"
        # A Ordem: "Busque no banco pelo ID salvo no cookie"
        return UsuarioModel.query.get(int(user_id))

    return UsuarioModel

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Se já estiver logado, não precisa logar de novo
    if current_user.is_authenticated:
        return redirect(url_for('painel_gerencial'))

    if request.method == 'POST':
        email = request.form.get('email')
        senha = request.form.get('senha')

        usuario = UsuarioModel.query.filter_by(email=email).first()

        # A Pergunta: "O e-mail existe e a senha bate com a criptografia?"
        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            flash(f"Bem-vindo, {usuario.nome}!", "success")
            proxima_pagina = request.args.get('next')
            return redirect(proxima_pagina or url_for('painel_gerencial'))
        else:
            flash("E-mail ou senha incorretos.", "danger")

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Sessão encerrada com sucesso.", "info")
    return redirect(url_for('auth.login'))

# --- ROTA DE ESQUECI A SENHA ---
@auth_bp.route('/esqueci_senha', methods=['GET', 'POST'])
def esqueci_senha():
    if request.method == 'POST':
        email_digitado = request.form.get('email')
        
        # 1. A Pergunta: "Esse e-mail existe no banco de dados?"
        usuario = UsuarioModel.query.filter_by(email=email_digitado).first()
        
        if usuario:
            # 2. A Ordem: "Gere um Ticket Dourado amarrado ao e-mail dele"
            # O current_app.config['SECRET_KEY'] usa a chave secreta do seu app.py para criar o ticket
            gerador_ticket = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            ticket = gerador_ticket.dumps(email_digitado, salt='recuperacao-de-senha')
            
            # 3. A Ordem: "Crie o link completo para ele clicar"
            # O _external=True garante que o link inclua o "http://..." completo
            link_recuperacao = url_for('auth.redefinir_senha', ticket=ticket, _external=True)
            
            # 3. A Ordem: "Crie o link completo para ele clicar"
            link_recuperacao = url_for('auth.redefinir_senha', ticket=ticket, _external=True)
            
            # A Ordem: "Escreva a carta, coloque o link no texto e entregue!"
            # --- O ENVIO REAL DO E-MAIL ---
            try:
                # 1. A Ordem: "Escreva a carta e coloque o link"
                msg = Message("Recuperação de Senha - CheckUpLog", recipients=[email_digitado])
                msg.body = f"Olá!\n\nVocê solicitou a recuperação de senha no CheckUpLog.\nClique no link abaixo para criar uma nova senha:\n\n{link_recuperacao}\n\nSe você não pediu isso, ignore este e-mail.\nEste link expira em 30 minutos."
                
                # 2. A Importação Tardia: "AGORA SIM, vá no app.py, chame o carteiro e envie"
                from app import mail
                mail.send(msg)
                
                flash("Um link de recuperação foi enviado para o seu e-mail.", "success")
            except Exception as e:
                flash("Erro ao tentar enviar o e-mail. Tente novamente mais tarde.", "danger")
                print(f"Erro de SMTP: {e}")
        else:
            # Segurança: Mesmo se o e-mail não existir, damos a mesma mensagem genérica 
            # para que hackers não descubram quais e-mails estão no sistema.
            flash("Se o e-mail estiver cadastrado, você receberá um link de recuperação em instantes.", "success")
            
        return redirect(url_for('auth.login'))

    return render_template('esqueci_senha.html')

# --- ROTA: REDEFINIR A SENHA (O CLIQUE NO LINK) ---
@auth_bp.route('/redefinir_senha/<ticket>', methods=['GET', 'POST'])
def redefinir_senha(ticket):
    gerador_ticket = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    
    try:
        # A Ordem: "Tente ler o ticket. Ele só é válido se tiver menos de 1800 segundos (30 minutos)"
        email_recuperado = gerador_ticket.loads(ticket, salt='recuperacao-de-senha', max_age=1800)
    except SignatureExpired:
        flash("O link de recuperação expirou (validade de 30 minutos). Solicite um novo.", "danger")
        return redirect(url_for('auth.esqueci_senha'))
    except BadSignature:
        flash("Link de recuperação inválido ou corrompido.", "danger")
        return redirect(url_for('auth.esqueci_senha'))
        
    # Se o ticket for válido e o usuário enviou o formulário com a nova senha
    if request.method == 'POST':
        nova_senha = request.form.get('senha')
        
        usuario = UsuarioModel.query.filter_by(email=email_recuperado).first()
        if usuario:
            # Esmaga a senha velha e gera a nova criptografia
            usuario.senha_hash = generate_password_hash(nova_senha)
            
            # A Importação Tardia: "Agora sim, chame o banco original e salve!"
            from app import db
            db.session.commit()
            
            flash("Sua senha foi redefinida com sucesso! Faça o login.", "success")
            return redirect(url_for('auth.login'))

    # Se ele apenas clicou no link, mostra a tela para digitar a nova senha
    return render_template('redefinir_senha.html', ticket=ticket)