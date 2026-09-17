from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

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