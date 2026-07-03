# Interface de Separação de Baseflow

App em Streamlit para a biblioteca [`baseflow`](https://github.com/xiejx5/baseflow), com busca
direta de dados de vazão na ANA (via [`hydrobr`](https://github.com/wallissoncarvalho/hydrobr)).

## Instalação

```bash
pip install -r requirements.txt
```

## Rodar

```bash
streamlit run app.py
```

Abre em `http://localhost:8501`.

## Como usar

1. **Dados**: na barra lateral, escolha entre buscar uma **estação da ANA** pelo código de 8
   dígitos (ex.: `56850000`, encontrado no [Hidroweb](https://www.snirh.gov.br/hidroweb)) ou
   fazer **upload de um CSV** com colunas de data e vazão.
2. **Metadados da bacia**: latitude, longitude e área de drenagem — usados apenas pelos métodos
   `Fixed`, `Local` e `Slide`. Se buscar da ANA, o app tenta preencher automaticamente a partir do
   inventário; do contrário, informe manualmente.
3. **Métodos**: selecione quais dos 12 métodos de separação rodar (UKIH, Local, Fixed, Slide, LH,
   Chapman, CM, Boughton, Furey, Eckhardt, EWMA, Willems).
4. Clique em **Calcular baseflow**. O app mostra:
   - gráfico interativo com a vazão total e o baseflow de cada método;
   - ranking por **KGE** (Kling-Gupta Efficiency), indicando o método com melhor ajuste à recessão;
   - BFI (Baseflow Index) médio por método;
   - tabela completa e botão para baixar os resultados em CSV.

## Notas

- A busca via ANA precisa de internet; se o pacote `hydrobr` não estiver instalado, use a opção
  de upload de CSV.
- Séries muito curtas ou com muitas falhas podem impedir métodos como `Local`/`UKIH`
  (exigem pelo menos 3 pontos de virada identificados).
