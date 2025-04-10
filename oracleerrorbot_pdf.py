import os
import json
import fitz  # PyMuPDF
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (ApplicationBuilder, ContextTypes,
                          CommandHandler, MessageHandler, filters)
from deep_translator import GoogleTranslator

# Ortam degiskenlerini yukle
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
JSON_PATH = "oracle_errors.json"
PDF_PATH = "oracle_errors.pdf"


# 1. PDF'i JSON'a Donustur (ilk calistirmada kullan)
def convert_pdf_to_json(pdf_path=PDF_PATH, json_path=JSON_PATH):
    doc = fitz.open(pdf_path)
    errors = {}

    for page in doc:
        text = page.get_text()
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("ORA-") and ":" in line:
                code = line.split()[0].strip()
                explanation = " ".join(lines[i:i+5]).strip()
                errors[code] = explanation

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)


# 2. JSON'dan hata kodu sorgula
def search_error_code(code):
    if not os.path.exists(JSON_PATH):
        convert_pdf_to_json()

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    code = code.strip().upper()

    # Doğrudan eşleşme varsa dön
    if code in data:
        return data[code]

    # Eşleşmeyen ama benzer kod varsa kontrol et
    for k in data:
        if code in k:
            return data[k]

    return None



# 3. JSON'da içerik araması yap
def search_by_keyword(keyword):
    if not os.path.exists(JSON_PATH):
        convert_pdf_to_json()

    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    keyword = keyword.strip().lower()
    results = {}

    for code, text in data.items():
        if keyword in code.lower() or keyword in text.lower():
            results[code] = text
        elif keyword.replace("ora-", "") in code.lower():
            results[code] = text
        elif keyword.isdigit() and keyword in code:
            results[code] = text

    return results


# 4. /search komutu
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Lütfen bir anahtar kelime girin. Örnek: /search column")
        return

    keyword = " ".join(context.args)
    results = search_by_keyword(keyword)

    if not results:
        await update.message.reply_text(f"'{keyword}' ile ilgili sonuç bulunamadı.")
        return

    message = f"🔍 '{keyword}' için bulunan sonuçlar:\n"
    for code, text in list(results.items())[:5]:
        message += f"\n📘 {code}: {text[:150]}..."
    await update.message.reply_text(message)


# 5. Mesajları işleme fonksiyonu
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip().upper()

    if user_input.startswith("ORA-"):
        original_text = search_error_code(user_input)

        if original_text:
            try:
                translated_text = GoogleTranslator(source='auto', target='tr').translate(original_text)
                message = (
                    f"📘 Orijinal:\n{original_text}\n\n"
                    f"🔄 Türkçe Çeviri:\n{translated_text}"
                )
                await update.message.reply_text(message)
            except Exception as e:
                await update.message.reply_text(
                    f"📘 Orijinal:\n{original_text}\n\n⚠️ Çeviri hatası: {e}"
                )
        else:
            await update.message.reply_text("❗ Bu hata kodu veritabanında bulunamadı.")
    else:
        await update.message.reply_text("Lütfen geçerli bir Oracle hata kodu girin (örn: ORA-00904) ya da /search komutunu kullanın.")


# 6. Botu başlat
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(CommandHandler("search", search_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
