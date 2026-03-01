# Simulados DEVOPS (AWS SAA-C03) 🧠

Simulador offline em Flask para treinar questões estilo prova AWS Solutions Architect Associate (SAA-C03), com bancos JSON locais, modo estudo e modo prova com timer.

---

## ✅ Recursos

- Interface web local (Flask): http://127.0.0.1:5000
- Bancos de questões em `banks/*.json`
- Seleção de banco via dropdown
- **Modo estudo**
  - feedback por questão (certo/errado)
  - explicação geral e por alternativa
- **Modo prova**
  - sem feedback entre questões
  - timer (minutos configuráveis)
  - resultado ao final
- Revisão das erradas: `/review`
- Explicações completas da sessão: `/explanations`
- **Prova real 65 ponderada**
  - usa todos os bancos da pasta `banks/`
  - sorteio ponderado por macro-temas
  - timer habilitado automaticamente

---

## 📦 Estrutura do projeto

```
├── web_quiz.py
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── question.html
│   ├── feedback.html
│   ├── result.html
│   ├── review.html
│   └── explanations.html
└── banks/
    ├── aws_saa_c03.json
    ├── aws_saa_c03_vpc_set1.json
    └── ...
```

---

## 🚀 Como rodar

### 1) Criar e ativar ambiente virtual

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2) Instalar dependências

Se existir `requirements.txt`:

```bash
pip install -r requirements.txt
```

Ou instalação mínima:

```bash
pip install Flask
```

### 3) Executar aplicação

```bash
python web_quiz.py
```

Abra no navegador:

```
http://127.0.0.1:5000
```

---

## 🧪 Modos de uso

### 📘 Modo estudo (recomendado para aprender)

1. Escolha um banco no dropdown
2. Defina nº de questões (ex: 20)
3. Clique em **Começar**

---

### 📝 Modo prova (simular exame)

1. Marque **Modo prova**
2. Defina minutos (ex: 130)
3. Clique em **Começar**

---

### 🎯 Prova real 65 ponderada (mistura bancos)

1. Marque **Prova real 65 ponderada**
2. Ajuste os minutos (ex: 130)
3. Clique em **Começar**

> Observação: no modo 65 ponderada, o timer é ativado automaticamente.

---

## 🗂 Formato do banco JSON

Cada arquivo em `banks/*.json` segue:

```json
{
  "questions": [
    {
      "id": "1",
      "topic": "vpc",
      "question": "Pergunta...",
      "choices": {
        "A": "Alternativa A",
        "B": "Alternativa B",
        "C": "Alternativa C",
        "D": "Alternativa D"
      },
      "correct": ["A"],
      "explanation": "Explicação geral...",
      "choice_explanations": {
        "A": "Por que A está certa",
        "B": "Por que B está errada",
        "C": "Por que C está errada",
        "D": "Por que D está errada"
      },
      "tags": ["route53", "dns"]
    }
  ]
}
```

---

## 🧰 Dicas

Validar rapidamente um JSON:

```bash
python -m json.tool banks/arquivo.json > /dev/null && echo OK
```

---

## 🏷 Versionamento

Este repositório segue versionamento simples:

- `0.1.0` = primeira versão estável local  
  (modo estudo + modo prova + revisão + explicações + 65 ponderada)

---

Boa prova e bons estudos ☕