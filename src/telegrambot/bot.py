"""Bot Telegram: invia i segnali con bottoni 'Esegui' / 'Ignora'.

Alla pressione di 'Esegui' il segnale viene eseguito dall'engine
(PAPER o LIVE a seconda della configurazione).

Richiede python-telegram-bot >= 20 (API asincrona).
"""
from __future__ import annotations

import logging
from typing import Dict

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import Settings
from ..engine import TradingEngine
from ..models import Signal, SignalType

log = logging.getLogger(__name__)


def format_signal(signal: Signal) -> str:
    emoji = "🟢" if signal.signal_type == SignalType.BUY else "🔴"
    lines = [
        f"{emoji} <b>SEGNALE {signal.signal_type.value}</b> — <b>{signal.pair}</b>",
        f"💶 Prezzo: <code>{signal.price:.2f}</code>",
        f"🎯 Confidenza: <b>{signal.confidence*100:.0f}%</b>",
    ]
    if signal.signal_type == SignalType.BUY and signal.suggested_stake_eur:
        lines.append(f"💰 Importo suggerito: <b>{signal.suggested_stake_eur:.2f} €</b>")
    if signal.stop_loss:
        lines.append(f"🛑 Stop loss: <code>{signal.stop_loss:.2f}</code>")
    if signal.take_profit:
        lines.append(f"✅ Take profit: <code>{signal.take_profit:.2f}</code>")

    if signal.indicators:
        ind = signal.indicators
        parts = []
        if ind.rsi is not None:
            parts.append(f"RSI {ind.rsi:.0f}")
        if ind.macd_hist is not None:
            parts.append(f"MACD {ind.macd_hist:+.2f}")
        if ind.pattern:
            parts.append(ind.pattern)
        if parts:
            lines.append("📊 " + " | ".join(parts))

    if signal.sentiment:
        lines.append(f"📰 Sentiment: {signal.sentiment.label.value} ({signal.sentiment.score:+.2f})")

    if signal.reasons:
        lines.append("\n<i>Motivazioni:</i>")
        for r in signal.reasons[:6]:
            lines.append(f"• {r}")

    return "\n".join(lines)


class TradingTelegramBot:
    def __init__(self, settings: Settings, engine: TradingEngine):
        self.settings = settings
        self.engine = engine
        self.chat_id = settings.telegram_chat_id
        # Segnali in attesa di conferma: id -> Signal
        self.pending: Dict[str, Signal] = {}
        self.app: Application | None = None

    # ------------------------------------------------------------------
    def _authorized(self, update: Update) -> bool:
        if not self.chat_id:
            return True  # se non configurato, non filtriamo (sconsigliato)
        user_chat = str(update.effective_chat.id) if update.effective_chat else ""
        return user_chat == str(self.chat_id)

    # ---- Comandi -----------------------------------------------------
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        mode = self.settings.trading_mode
        await update.message.reply_text(
            "🤖 <b>Bot Cripto avviato</b>\n"
            f"Modalita': <b>{mode}</b>\n\n"
            "Comandi disponibili:\n"
            "/analyze — analizza ora i mercati\n"
            "/status — stato del conto/portafoglio\n"
            "/sentiment — clima delle notizie\n"
            "/help — aiuto",
            parse_mode=ParseMode.HTML,
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        await update.message.reply_text(
            "ℹ️ Ricevi segnali automatici periodici.\n"
            "Per ogni segnale premi <b>Esegui</b> per piazzare l'ordine "
            "oppure <b>Ignora</b> per scartarlo.\n\n"
            f"Modalita' attuale: <b>{self.settings.trading_mode}</b> "
            "(PAPER = simulazione, LIVE = denaro reale).",
            parse_mode=ParseMode.HTML,
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        st = self.engine.status()
        lines = [f"📈 <b>Stato — {st.get('mode', '?')}</b>"]
        if "equity" in st:
            lines += [
                f"Liquidita': <b>{st['eur_cash']:.2f} €</b>",
                f"Valore totale: <b>{st['equity']:.2f} €</b>",
                f"P&L: <b>{st['pnl_eur']:+.2f} €</b> ({st['pnl_pct']:+.2f}%)",
                f"Operazioni: {st['trades']}",
            ]
            if st.get("open_positions"):
                lines.append("\n<i>Posizioni aperte:</i>")
                for p, pos in st["open_positions"].items():
                    lines.append(f"• {p}: {pos['volume']:.6f} @ {pos['avg_price']:.2f}")
        elif "balance" in st:
            lines.append("Saldo Kraken:")
            for asset, amt in st["balance"].items():
                if amt > 0:
                    lines.append(f"• {asset}: {amt}")
        elif "error" in st:
            lines.append(f"⚠️ {st['error']}")
        lines.append(f"\n🎯 Target mensile: {st.get('target_mensile_eur', 0):.0f} €")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    async def cmd_sentiment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        await update.message.reply_text("🔎 Analizzo le notizie...")
        report = self.engine.sentiment_analyzer.analyze()
        lines = [
            f"📰 <b>Sentiment: {report.label.value}</b> (score {report.score:+.2f})",
        ]
        if report.red_alert:
            lines.append("🚨 <b>ALLERTA ROSSA</b>: segnali operativi sospesi.")
        for r in report.reasons:
            lines.append(f"• {r}")
        if report.headlines:
            lines.append("\n<i>Titoli rilevanti:</i>")
            for h in report.headlines[:5]:
                lines.append(f"— {h}")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

    async def cmd_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self._authorized(update):
            return
        await update.message.reply_text("🔄 Analisi dei mercati in corso...")
        await self._run_and_dispatch(context, chat_id=update.effective_chat.id)

    # ---- Ciclo di analisi + invio segnali ----------------------------
    async def scheduled_analysis(self, context: ContextTypes.DEFAULT_TYPE):
        log.info("Analisi programmata in esecuzione...")
        await self._run_and_dispatch(context, chat_id=self.chat_id)

    async def _run_and_dispatch(self, context: ContextTypes.DEFAULT_TYPE, chat_id):
        import asyncio

        try:
            # Il ciclo fa I/O di rete bloccante: eseguilo in un thread.
            signals = await asyncio.to_thread(self.engine.run_cycle)
        except Exception as exc:
            log.exception("Errore nel ciclo di analisi")
            await context.bot.send_message(chat_id, f"⚠️ Errore analisi: {exc}")
            return

        # Notifica allerta rossa (anche senza segnali operativi).
        sentiment = getattr(self.engine, "last_sentiment", None)
        if sentiment and sentiment.red_alert:
            await context.bot.send_message(
                chat_id,
                "🚨 <b>ALLERTA ROSSA sulle notizie</b>: possibile guerra o crollo. "
                "Segnali operativi sospesi per prudenza.",
                parse_mode=ParseMode.HTML,
            )

        if not signals:
            await context.bot.send_message(chat_id, "✅ Nessun segnale operativo al momento.")
            return

        for signal in signals:
            self.pending[signal.id] = signal
            keyboard = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton("✅ Esegui", callback_data=f"exec:{signal.id}"),
                    InlineKeyboardButton("❌ Ignora", callback_data=f"ignore:{signal.id}"),
                ]]
            )
            await context.bot.send_message(
                chat_id,
                format_signal(signal),
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML,
            )

    # ---- Callback dei bottoni ----------------------------------------
    async def on_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if not self._authorized(update):
            await query.edit_message_text("⛔ Non autorizzato.")
            return

        action, _, signal_id = query.data.partition(":")
        signal = self.pending.get(signal_id)

        if signal is None:
            await query.edit_message_text(
                query.message.text_html + "\n\n⏱ <i>Segnale scaduto o gia' gestito.</i>",
                parse_mode=ParseMode.HTML,
            )
            return

        if action == "ignore":
            self.pending.pop(signal_id, None)
            await query.edit_message_text(
                query.message.text_html + "\n\n❌ <b>IGNORATO</b>",
                parse_mode=ParseMode.HTML,
            )
            return

        if action == "exec":
            self.pending.pop(signal_id, None)
            await query.edit_message_text(
                query.message.text_html + "\n\n⏳ <i>Esecuzione in corso...</i>",
                parse_mode=ParseMode.HTML,
            )
            import asyncio

            result = await asyncio.to_thread(self.engine.execute_signal, signal)
            if result.success:
                txt = (
                    f"\n\n✅ <b>ESEGUITO ({result.mode})</b>\n"
                    f"{result.side.upper()} {result.volume:.8f} {result.pair} "
                    f"@ {result.price:.2f}\n"
                    f"Controvalore: {result.cost_eur:.2f} €"
                )
                if result.order_id:
                    txt += f"\nID ordine: <code>{result.order_id}</code>"
            else:
                txt = f"\n\n⚠️ <b>ESECUZIONE FALLITA</b>: {result.error}"
            await query.edit_message_text(
                query.message.text_html + txt, parse_mode=ParseMode.HTML
            )

    # ------------------------------------------------------------------
    def build(self) -> Application:
        app = Application.builder().token(self.settings.telegram_bot_token).build()
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("portfolio", self.cmd_status))
        app.add_handler(CommandHandler("sentiment", self.cmd_sentiment))
        app.add_handler(CommandHandler("analyze", self.cmd_analyze))
        app.add_handler(CallbackQueryHandler(self.on_button))

        # Analisi periodica (se la job-queue e' disponibile).
        if app.job_queue is not None:
            interval = self.settings.analysis_interval_minutes * 60
            app.job_queue.run_repeating(
                self.scheduled_analysis, interval=interval, first=30
            )
            log.info("Analisi periodica ogni %s minuti.", self.settings.analysis_interval_minutes)
        else:
            log.warning(
                "JobQueue non disponibile: installa python-telegram-bot[job-queue] "
                "per l'analisi automatica. Usa /analyze manualmente."
            )
        self.app = app
        return app

    def run(self):
        app = self.build()
        log.info("Bot Telegram in avvio (polling)...")
        app.run_polling()
