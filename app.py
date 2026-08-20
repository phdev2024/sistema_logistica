# app.py

# Importando a ferramenta web e nossas funções de cálculo
from flask import Flask
from core.custos import (
    calcular_custo_fixo_total,
    calcular_custo_variavel_total,
    calcular_custo_operacional_total
)

# 1. Iniciando o motor do site
app = Flask(__name__)

# 2. Criando o caminho (rota) da página principal
@app.route('/')
def pagina_inicial():
    
    # Colocamos os nossos dicionários de teste aqui dentro
    custos_fixos = {
        "Aluguel": 30000.0,
        "Condominio": 5000.0,
        "Seguro": 1500.0
    }
    
    custos_variaveis = {
        "Palete PBR": 41.00,
        "Fita e Stretch": 2.50,
        "Mao de Obra (Rateio)": 15.00
    }
    
    # Colocando o cérebro para trabalhar
    total_fixo = calcular_custo_fixo_total(custos_fixos)
    total_variavel = calcular_custo_variavel_total(custos_variaveis, 100)
    custo_operacional = calcular_custo_operacional_total(total_fixo, total_variavel)
    
    # 3. Devolvendo o resultado formatado como uma página de internet (HTML)
    return f"""
        <h1>Protótipo: Rentabilidade Logcare</h1>
        <h2>Configurações Base</h2>
        <p><b>Custo Fixo Total:</b> R$ {total_fixo}</p>
        <p><b>Custo Variável (100 paletes):</b> R$ {total_variavel}</p>
        <hr>
        <h2 style="color: blue;">Custo Operacional da Base: R$ {custo_operacional}</h2>
    """

# 4. Ordem para manter o servidor ligado
if __name__ == '__main__':
    app.run(debug=True)