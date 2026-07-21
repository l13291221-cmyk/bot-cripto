# 🤖 Bot Cripto — Sistema di Trading Automatico su Kraken

Sistema completo di trading automatico per criptovalute con:

1. **Analyzer** collegato alle **API pubbliche di Kraken** per i dati di mercato.
2. **Strategia su scala mensile** basata su **RSI, MACD, volume e pattern a candela**,
   con un **filtro di Sentiment Analysis** sulle notizie (RSS crypto/finanza) che
   **sospende i segnali in caso di allerta rossa** (guerre, crolli di mercato).
3. **Bot Telegram** che invia i segnali con **bottoni di conferma** (`Esegui` / `Ignora`).
4. **Modalità Paper Trading** (simulazione con soldi finti) per testare la strategia
   prima di rischiare denaro reale.

Quando ricevi un segnale su Telegram premi **Esegui** e il bot piazza l'ordine
su Kraken via API (in LIVE) oppure lo simula (in PAPER); premi **Ignora** per scartarlo.

---

## ⚠️ Leggi prima di iniziare: aspettative realistiche

Il tuo obiettivo dichiarato è **500 € al mese partendo da 100 €**. Va detto con onestà:

> **500 € di profitto su un capitale di 100 € significa un +500% al mese.**
> Non esiste alcuna strategia che possa garantirlo. Rendimenti di questa
> portata richiedono un rischio talmente alto che l'esito **statisticamente più
> probabile è la perdita totale dei 100 €**, non il guadagno.

Cosa fa (e non fa) questo software:

- ✅ Genera segnali con criteri tecnici **prudenti** e li sottopone alla tua conferma.
- ✅ Ti fa **testare tutto in Paper Trading** senza rischiare un euro.
- ✅ Sospende le operazioni quando le notizie segnalano **guerre o crolli**.
- ❌ **Non** promette e **non** può garantire il target di 500 €/mese.
- ❌ **Non** è consulenza finanziaria.

Il valore `MONTHLY_TARGET_EUR` è usato **solo per il reporting** (per dirti a che
punto sei), **non** per forzare operazioni azzardate pur di raggiungerlo.
Usa solo denaro che puoi permetterti di perdere.

---

## 🧱 Architettura

```
bot-cripto/
├── main.py                  # entrypoint: bot Telegram / --once / --check
├── backtest.py              # backtest indicativo su dati storici Kraken
├── config.py                # configurazione da .env
├── requirements.txt
├── .env.example             # copia in .env e compila
└── src/
    ├── models.py            # Signal, IndicatorSnapshot, SentimentReport, OrderResult
    ├── engine.py            # orchestratore (analyzer+sentiment+strategia+trader)
    ├── kraken/
    │   ├── public_client.py   # dati di mercato (OHLC, ticker) — API pubbliche
    │   └── private_client.py  # saldo e ordini firmati HMAC — API private
    ├── analyzer/
    │   ├── indicators.py      # RSI, MACD, EMA/SMA, volume, pattern (puro Python)
    │   └── market_analyzer.py # scarica dati e calcola gli indicatori
    ├── sentiment/
    │   └── news_sentiment.py  # feed RSS + filtro allerta rossa (guerra/crollo)
    ├── strategy/
    │   └── monthly_strategy.py# combina indicatori + sentiment -> Signal
    ├── trading/
    │   ├── portfolio.py       # portafoglio persistente (JSON) per il paper trading
    │   ├── paper_trader.py    # esecuzione simulata con fee realistiche
    │   └── live_trader.py     # esecuzione reale su Kraken
    └── telegrambot/
        └── bot.py             # bot con bottoni Esegui/Ignora + analisi periodica
```

### Come nasce un segnale

```
API pubbliche Kraken ──▶ MarketAnalyzer ──▶ IndicatorSnapshot (RSI, MACD, volume, pattern)
Feed RSS notizie ─────▶ NewsSentimentAnalyzer ──▶ SentimentReport (score, red_alert)
                                   │
                                   ▼
                          MonthlyStrategy
                    (se red_alert ⇒ HOLD, segnali sospesi)
                                   │
                                   ▼
                               Signal (BUY/SELL)
                                   │
                                   ▼
                     Telegram: [✅ Esegui] [❌ Ignora]
                                   │  (Esegui)
                                   ▼
                    PaperTrader (simulazione)  oppure  LiveTrader (ordine reale)
```

---

## 🚀 Installazione

Richiede **Python 3.10+**.

```bash
# 1. Dipendenze
pip install -r requirements.txt

# 2. Configurazione
cp .env.example .env
# apri .env e compila i valori (vedi sotto)
```

> **Nota su `feedparser`**: è opzionale. Se la sua installazione fallisce nel tuo
> ambiente, il modulo notizie usa automaticamente un parser RSS/Atom basato sulla
> libreria standard (`requests` + `xml.etree`). Il bot funziona comunque.

### Configurazione (`.env`)

| Variabile | Descrizione |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token del bot (crealo con [@BotFather](https://t.me/BotFather)). |
| `TELEGRAM_CHAT_ID` | Il tuo chat id (chiedi a [@userinfobot](https://t.me/userinfobot)). Solo tu potrai comandare il bot. |
| `TRADING_MODE` | `PAPER` (simulazione, default) o `LIVE` (denaro reale). |
| `INITIAL_BUDGET_EUR` | Capitale iniziale (es. `100`). |
| `MONTHLY_TARGET_EUR` | Target mensile — **solo reporting** (es. `500`). |
| `TRADING_PAIRS` | Coppie Kraken separate da virgola (es. `XBTEUR,ETHEUR,SOLEUR`). |
| `MAX_POSITION_FRACTION` | Frazione massima del capitale per singolo trade (0–1). |
| `DEFAULT_STOP_LOSS` / `DEFAULT_TAKE_PROFIT` | Stop/take di default (es. `0.05` = 5%). |
| `ANALYSIS_INTERVAL_MINUTES` | Ogni quanti minuti analizzare i mercati. |
| `NEWS_RSS_FEEDS` | Feed RSS di notizie, separati da virgola. |
| `KRAKEN_API_KEY` / `KRAKEN_API_SECRET` | **Solo per LIVE.** Da Kraken → Settings → API. |

Per il LIVE, sulla chiave Kraken bastano i permessi **Query Funds** e
**Create & Modify Orders** (non abilitare i prelievi).

---

## ▶️ Utilizzo

```bash
# Verifica la configurazione senza avviare nulla
python main.py --check

# Esegui UN solo ciclo di analisi e stampa i segnali (senza Telegram, utile per provare)
python main.py --once

# Avvia il bot Telegram (usa la modalità impostata in .env)
python main.py
```

### Comandi Telegram

| Comando | Azione |
|---|---|
| `/start` | Avvia e mostra i comandi. |
| `/analyze` | Analizza subito i mercati e invia gli eventuali segnali. |
| `/status` | Stato del conto/portafoglio, P&L e posizioni aperte. |
| `/sentiment` | Clima attuale delle notizie ed eventuale allerta rossa. |
| `/help` | Aiuto. |

Il bot esegue anche un'**analisi automatica** ogni `ANALYSIS_INTERVAL_MINUTES`
e ti manda i segnali con i bottoni **✅ Esegui** / **❌ Ignora**.

### Backtest indicativo

```bash
python backtest.py XBTEUR --budget 100
```

Simula la strategia sui dati storici giornalieri (senza filtro notizie, non
disponibile sullo storico). **Il passato non predice il futuro**: serve solo a
farti un'idea della logica.

---

## 🔒 Sicurezza

- Le chiavi stanno nel `.env`, **escluso dal versioning** (`.gitignore`).
- Solo il `TELEGRAM_CHAT_ID` configurato può comandare il bot ed eseguire ordini.
- Il **default è PAPER**: nessun ordine reale finché non imposti `TRADING_MODE=LIVE`.
- Nessun ordine parte in automatico: serve **sempre** la tua conferma su Telegram.
- La chiave Kraken non necessita del permesso di prelievo.

---

## 🧪 Test

```bash
python -m pytest tests/ -q
```

Coprono indicatori, filtro sentiment/allerta rossa, generazione dei segnali e
paper trading (buy/sell, persistenza, saldo insufficiente).

---

## 🌐 Nota sull'accesso di rete

Il sistema chiama host esterni (`api.kraken.com` e i feed RSS). In ambienti con
firewall/proxy restrittivo queste chiamate possono essere bloccate: in tal caso
il bot **non va in crash**, semplicemente non produce segnali (lo vedrai nei log).
Esegui il bot in un ambiente con accesso a Internet verso Kraken e ai feed notizie.

---

## 📋 Disclaimer

Software fornito a scopo **educativo**. Non è consulenza finanziaria. Il trading di
criptovalute comporta un **rischio elevato di perdita del capitale**. L'autore e il
software non sono responsabili di eventuali perdite. Opera solo con denaro che puoi
permetterti di perdere.
