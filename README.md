<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=11998e,38ef7d&height=200&section=header&text=Northstar&fontSize=70&fontColor=ffffff&animation=twinkling" width="100%" />

<img src="https://img.icons8.com/?id=DGsE9caX0XGr&format=png&size=100" width="90" />

<img src="https://readme-typing-svg.demolab.com?font=JetBrains+Mono&weight=600&size=22&duration=2500&pause=1000&color=11998e&center=true&vCenter=true&width=700&height=50&lines=Explainable%20wealth-management%20agent%20toolkit;Python%20+%20Flask" alt="Typing SVG" />

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](#)
[![Flask](https://img.shields.io/badge/Flask-API-000000?style=for-the-badge&logo=flask&logoColor=white)](#)
[![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=for-the-badge&logo=openai&logoColor=white)](#)
[![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge)](#)

</div>

---

## 📖 Overview

**Northstar** — Explainable wealth-management agent toolkit.

Core logic lives in `src/wealth_agent/`. Configuration is centralized in `config/settings.yaml`
and secrets/API keys are loaded from a local `.env` (see `.env.example`).

## 🏗️ Project Layout

```
Northstar/
├── app.py               # Flask entry point
├── src/wealth_agent/
│   └── ...              # Core package — explainable wealth-management agent toolkit
├── config/settings.yaml # App configuration
├── tests/                # Unit tests
├── scripts/setup.sh      # venv + install helper (macOS/Linux)
├── requirements.txt
```


## ⚡ Setup & Run

### 🪟 Windows (PowerShell / CMD)
```cmd
git clone https://github.com/AfnanSharif/Northstar.git
cd Northstar

python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env
:: edit .env to add any API keys — the app runs fully offline without them

python app.py
```

### 🍎 macOS / 🐧 Linux
```bash
git clone https://github.com/AfnanSharif/Northstar.git
cd Northstar

./scripts/setup.sh                 # creates .venv and installs requirements.txt
source .venv/bin/activate

cp .env.example .env
# edit .env to add any API keys — the app runs fully offline without them

python app.py
```

Open **http://localhost:5000**.

```bash
make test    # run the test suite
make lint    # lint the codebase
```

---

<div align="center">

**Created by [AfnanSharif](https://github.com/AfnanSharif)** · ⭐ star this repo if it helped you

<img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&customColorList=11998e,38ef7d&height=80&section=footer" width="100%" />

</div>
