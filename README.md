# Dashboard de Movimentações Precs 💰

Um dashboard interativo desenvolvido em Streamlit para análise e comparação de saldos municipais com histórico completo de movimentações financeiras.

## 🚀 Funcionalidades

- **Comparativo de Saldos**: Compare saldos entre duas datas específicas
- **Filtros Avançados**: Busque e selecione municípios específicos
- **Histórico Completo**: Visualize todas as movimentações com filtros
- **Formatação BRL**: Valores formatados em Real brasileiro
- **Interface Responsiva**: Layout otimizado para diferentes dispositivos

## 📋 Pré-requisitos

- Python 3.8+
- PostgreSQL
- Acesso ao banco de dados configurado

## 🛠️ Instalação

1. Clone o repositório:
```bash
git clone <url-do-repositorio>
cd dashPrecs-main
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure as variáveis de ambiente:
Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:
```env
DB_HOST=seu_host_do_banco
DB_NAME=nome_do_banco
DB_USER=usuario_do_banco
DB_PASSWORD=senha_do_banco
DB_PORT=5432
```

## 🚀 Como usar

### Executar localmente:
```bash
streamlit run app.py
```

### Deploy no Streamlit Cloud:
1. Faça push do código para o GitHub
2. Conecte seu repositório no [Streamlit Cloud](https://share.streamlit.io/)
3. Configure as variáveis de ambiente no painel do Streamlit Cloud
4. Deploy automático será realizado

## 📊 Estrutura do Banco de Dados

O aplicativo espera uma tabela `movimentacoes` com as seguintes colunas:
- `id`: Identificador único
- `municipio`: Nome do município
- `data_movimentacao`: Data da movimentação
- `saldo_anterior_valor`: Saldo anterior
- `saldo_atualizado_valor`: Saldo atualizado
- `lancamento_valor`: Valor do lançamento

## 🔧 Configuração para Deploy

### Streamlit Cloud
1. Faça fork/clone deste repositório
2. Conecte no Streamlit Cloud
3. Configure as secrets no painel:
   - `DB_HOST`
   - `DB_NAME`
   - `DB_USER`
   - `DB_PASSWORD`
   - `DB_PORT`

### Variáveis de Ambiente
O aplicativo suporta as seguintes variáveis de ambiente:
- `DB_HOST`: Host do banco de dados
- `DB_NAME`: Nome do banco de dados
- `DB_USER`: Usuário do banco
- `DB_PASSWORD`: Senha do banco
- `DB_PORT`: Porta do banco (padrão: 5432)

## 📱 Uso da Aplicação

1. **Seleção de Datas**: Escolha a data de referência e a data atual para comparação
2. **Filtro de Municípios**: Use a busca para encontrar municípios específicos
3. **Visualização**: Analise os dados na tabela comparativa
4. **Histórico**: Explore o histórico completo na seção inferior

## 🤝 Contribuição

1. Faça um fork do projeto
2. Crie uma branch para sua feature (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.
