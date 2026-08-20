# main.py

# Importando o nosso motor de cálculos
from core.custos import (
    calcular_custo_fixo_total,
    calcular_custo_variavel_total,
    calcular_custo_operacional_total,
    calcular_preco_venda
)

# --- 1. DADOS DO DIRETOR (Configurações do Galpão) ---
custos_fixos = {
    "Aluguel": 30000.0,
    "Condominio": 5000.0,
    "Seguro": 1500.0
}

custos_variaveis_por_palete = {
    "Palete PBR": 41.00,
    "Fita e Stretch": 2.50,
    "Mao de Obra (Rateio)": 15.00
}

limite_lucro_diretor = 18.0

# --- 2. DADOS DO VENDEDOR (A Proposta do Cliente) ---
dados_cliente = {
    "Nome": "Logística Brasil LTDA",
    "CNPJ": "00.000.000/0001-00",
    "Revisão": "20260820"
}
volume_paletes_cliente = 100
margem_tentativa_venda = 20.0  # Atenção: Vamos tentar vender abaixo do limite para testar a trava!

# --- 3. EXECUTANDO AS ORDENS (Colocando o cérebro para trabalhar) ---
total_fixo = calcular_custo_fixo_total(custos_fixos)
total_variavel = calcular_custo_variavel_total(custos_variaveis_por_palete, volume_paletes_cliente)
custo_da_operacao = calcular_custo_operacional_total(total_fixo, total_variavel)

resultado_proposta = calcular_preco_venda(custo_da_operacao, margem_tentativa_venda, limite_lucro_diretor)

# --- 4. EXIBINDO O RESULTADO NO TERMINAL ---
print("--- RESULTADO DA SIMULAÇÃO ---")
print(f"Custo Fixo Total: R$ {total_fixo}")
print(f"Custo Variável Total (para {volume_paletes_cliente} paletes): R$ {total_variavel}")
print(f"Custo Operacional Total: R$ {custo_da_operacao}")
print("-" * 30)
print(f"Status da Proposta: {resultado_proposta['status'].upper()}")

# Se o status for bloqueado, mostramos o motivo
if resultado_proposta['status'] == 'bloqueado':
    print(f"Motivo: {resultado_proposta['mensagem']}")
else:
    print(f"Preço de Venda Sugerido: R$ {resultado_proposta['preco_final']}")
    print(f"Proposta gerada para: {dados_cliente['Nome']} (CNPJ:{dados_cliente['CNPJ']})")