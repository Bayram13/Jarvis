import os
import logging
import google.generativeai as genai # Gemini API üçün yeni import
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

# .env faylından ətraf mühit dəyişənlərini yüklə
load_dotenv()

# Logging-i konfiqurasiya et
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ətraf mühit dəyişənlərini oxuyun
BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Yeni API açarı dəyişəni
AI_NAME = os.getenv("AI_NAME", "Jarvis")

# Telegram Bot Token və Gemini API Key yoxlanışı
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN ətraf mühit dəyişəni təyin edilməyib!")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY ətraf mühit dəyişəni təyin edilməyib! Lütfən Google Cloud-dan alın.")

# Gemini API-ni konfiqurasiya et
genai.configure(api_key=GEMINI_API_KEY)

# Gemini modeli
GEMINI_MODEL = "gemini-2.5-flash" # Mətn üçün standart modeldir. Şəkil üçün "gemini-pro-vision" ola bilər.

# Sistem mesajı: AI-nın şəxsiyyətini müəyyən edir (Gemini bunu birbaşa dəstəkləmir,
# lakin hər sorğunun əvvəlinə əlavə edərək simulyasiya edə bilərik)
SYSTEM_PROMPT_PREFIX = (
    f"Sən {AI_NAME} adlı, səmimi, əyləncəli və köməksevər bir süni intellektsən. "
    "Mümkün qədər qısa və məzəli cavablar verməyə çalış. "
    "Mürəkkəb mövzularda sadə izahatlar ver. "
    "İstifadəçilərlə dostcasına münasibət qur. "
    "İndi istifadəçinin sualı/mesajı: "
)

# /start komandası üçün idarəedici
async def start(update: Update, context):
    user = update.effective_user
    logger.info(f"Received /start from user: {user.full_name}")
    await update.message.reply_html(
        f"Salam, {user.mention_html()}! Mən **{AI_NAME}**. Sənə necə kömək edə bilərəm? "
        "Mən həm özəl söhbətlərdə, həm də qruplarda sizə cavab verə bilərəm!"
    )

# Gemini-dən cavab almaq üçün funksiya
async def get_gemini_response(prompt: str) -> str:
    try:
        # Mesaja sistem promptunu əlavə edirik ki, tonu qorusun
        full_prompt = SYSTEM_PROMPT_PREFIX + prompt
        
        # Gemini-yə sorğu göndər
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = await model.generate_content_async(full_prompt) # Asinxron çağırış

        # Cavabın mövcudluğunu yoxlayın
        if response and response.candidates:
            # GenerateContentResponse obyektindən mətni çıxarırıq
            if response.candidates[0].content and response.candidates[0].content.parts:
                generated_text = "".join(part.text for part in response.candidates[0].content.parts)
                # Cavabın uzunluğunu yoxlayırıq (maksimum token yox, sadəcə qısa olması üçün)
                # Gemini API-da birbaşa max_tokens parametrləri fərqli işləyir.
                # Qısa cavab üçün promptda təlimat vermək daha effektivdir.
                return generated_text.strip()
        
        logger.warning(f"Unexpected Gemini response format or no content: {response}")
        return "Üzr istəyirəm, cavab ala bilmədim. Bir az sonra yenə cəhd edin."
    
    except Exception as e:
        logger.error(f"Gemini API-də gözlənilməyən xəta: {e}", exc_info=True)
        return "Bağışlayın, Gemini ilə əlaqə qurarkən bir problem yarandı. Yenidən cəhd edin."

# Mətn mesajlarını idarə edən funksiya
async def handle_message(update: Update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_message = update.message.text
    chat_type = update.effective_chat.type

    logger.info(f"Received message in {chat_type} chat from {update.effective_user.full_name} ({user_id}): {user_message}")

    if chat_type == 'private':
        response = await get_gemini_response(user_message)
        await update.message.reply_text(response)
    elif chat_type in ['group', 'supergroup']:
        bot_username = context.bot.username
        if bot_username and user_message.startswith(f"@{bot_username}"):
            cleaned_message = user_message[len(f"@{bot_username}"):].strip()
            if cleaned_message:
                response = await get_gemini_response(cleaned_message)
                await update.message.reply_text(response)
            else:
                await update.message.reply_text(f"Nə lazımdır, {update.effective_user.first_name}? Mən {AI_NAME}.")

# Əsas funksiya (botu işə salır)
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS), handle_message))

    PORT = int(os.environ.get("PORT", "8000"))
    RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME")

    if not RENDER_EXTERNAL_HOSTNAME:
        logger.info("RENDER_EXTERNAL_HOSTNAME təyin edilməyib. Bot yerli rejimdə (polling) işə salındı.")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        webhook_url = f"https://{RENDER_EXTERNAL_HOSTNAME}/{BOT_TOKEN}"
        logger.info(f"Bot webhook rejimində Render.com-da işə salındı. Port: {PORT}, Webhook URL: {webhook_url}")
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=BOT_TOKEN,
            webhook_url=webhook_url
        )

if __name__ == "__main__":
    main()
