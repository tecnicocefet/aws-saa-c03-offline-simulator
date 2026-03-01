# Simulados DEVOPS (AWS SAA-C03) 🧠

Simulador offline em Flask para treinar questões estilo prova (AWS Solutions Architect Associate SAA-C03), com bancos JSON locais, modo estudo e modo prova com timer.

## ✅ Recursos

- Interface web local (Flask) em `http://127.0.0.1:5000`
- Bancos de questões em `banks/*.json`
- Seleção de banco via dropdown
- **Modo estudo**:
  - feedback por questão (certo/errado)
  - explicação geral e por alternativa
- **Modo prova**:
  - sem feedback entre questões
  - timer (minutos configuráveis)
  - resultado ao final
- Revisão das erradas (`/review`)
- Explicações completas da sessão (`/explanations`)
- (Opcional) “Prova real 65 ponderada” usando todos os bancos da pasta `banks/` (quando habilitado no app)

## 📦 Estrutura do projeto


├── web_quiz.py
├── templates/
│ ├── base.html
│ ├── home.html
│ ├── question.html
│ ├── feedback.html
│ ├── result.html
│ ├── review.html
│ └── explanations.html
└── banks/
├── aws_saa_c03.json
├── aws_saa_c03_vpc_set1.json
├── ..


## 🚀 Como rodar

### 1 Criar/ativar venv

python3 -m venv venv
source venv/bin/activate

2) Instalar dependências

pip install -U pip
pip install flask

Se você já tem requirements.txt, use:

pip install -r requirements.txt

3) Executar

python web_quiz.py


Abra no navegador:

http://127.0.0.1:5000

🧪 Modos de uso
Modo estudo (recomendado para aprender)

Escolha um banco no dropdown

Defina nº de questões (ex: 20)

Começar

Modo prova (simular exame)

Marque Modo prova

Defina minutos (ex: 130)

Começar

Prova real 65 ponderada (mistura bancos)

Marque Prova real 65 ponderada

Opcional: marque Modo prova + minutos (ex: 130)

Começar

🗂 Formato do banco JSON

Cada arquivo em banks/*.json segue:

🧰 Dicas

Para checar se um JSON está válido:

python -m json.tool banks/arquivo.json > /dev/null && echo OK

🏷 Versionamento

Este repositório segue tags simples:

0.1.0 = primeira versão estável local (modo estudo + modo prova + revisão/explicações)

Boa prova e bons estudos ☕