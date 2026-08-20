# Somando todas as despesas fixas da base
def calcular_custo_fixo_total(dicionario_de_custos):
    # Começamos com a gaveta vazia, valendo zero
    custo_total = 0.0
    
    # O computador vai olhar item por item dentro da caixa de custos
    for custo, valor in dicionario_de_custos.items():
        custo_total = custo_total + valor
    # Devolvendo o resultado final
    return custo_total

def calcular_custo_variavel_total(dicionario_custos_unitarios, volume_operacao):
    # Começamos com a gaveta vazia, forçando o uso de casas decimais
    custo_unitario_total = 0.0
    
    # O computador soma quanto custa preparar UMA única unidade (ex: 1 palete)
    for custo, valor in dicionario_custos_unitarios.items():
        custo_unitario_total = custo_unitario_total + valor
        
    # Multiplica o custo de UMA unidade pelo volume total da operação
    custo_variavel_final = custo_unitario_total * volume_operacao
    
    # Entrega o resultado final
    return custo_variavel_final

def calcular_custo_operacional_total(custo_fixo_calculado, custo_variavel_calculado):
    # Unindo o peso da estrutura com o peso da movimentação
    custo_final = custo_fixo_calculado + custo_variavel_calculado
    
    # Entregando o número real que a empresa gasta
    return custo_final

def calcular_preco_venda(custo_total, margem_desejada, limite_margem_minima):
    
    # 1. A Regra de Segurança (A Trava do Diretor)
    if margem_desejada < limite_margem_minima:
        # Se a trava for acionada, a função é abortada imediatamente aqui
        return {
            "status": "bloqueado",
            "mensagem": "Atenção: A margem digitada é menor que o limite estabelecido."
        }
        
    # 2. O Cálculo do Preço (se passou pela trava ileso)
    fator_markup = 1 - (margem_desejada / 100)
    preco_sugerido = custo_total / fator_markup
    
    # 3. Entregando o orçamento aprovado
    return {
        "status": "aprovado",
        "preco_final": round(preco_sugerido, 2)
    }