import os
import logging
import httpx # Asinxron HTTP sorğuları üçün
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv

# .env faylından ətraf mühit dəyişənlərini yüklə
load_dotenv()

# Logging-i konfiqurasiya et (botun işini izləmək üçün)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ətraf mühit dəyişənlərini oxuyun
BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
AI_NAME = os.getenv("AI_NAME", "Jarvis") # AI adı, .env-dən oxu, yoxdursa "Jarvis" olsun

# Telegram Bot Token və OpenAI API Key yoxlanışı
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN ətraf mühit dəyişəni təyin edilməyib!")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY ətraf mühit dəyişəni təyin edilməyib!")

# OpenAI API üçün HTTP client
# Asinxron işləmək üçün httpx istifadə edirik
openai_client = httpx.AsyncClient(base_url="https://api.openai.com/v1/", timeout=60.0)

# GPT model adı (pulsuz tier üçün GPT-3.5 Turbo ən məqsədəuyğundur)
GPT_MODEL = "gpt-3.5-turbo" # Və ya GPT-4o-mini, hansı ki, daha yeni və səmərəlidir.

# Sistem mesajı: AI-nın şəxsiyyətini müəyyən edir
SYSTEM_MESSAGE = (
    f"Sən {AI_NAME} adlı, səmimi, əyləncəli və köməksevər bir süni intellektsən. "
    "Mümkün qədər qısa və məzəli cavablar verməyə çalış. "
    "Mürəkkəb mövzularda sadə izahatlar ver. "
    "İstifadəçilərlə dostcasına münasibət qur."
)

# /start komandası üçün idarəedici
async def start(update: Update, context):
    user = update.effective_user
    logger.info(f"Received /start from user: {user.full_name}")
    await update.message.reply_html(
        f"Salam, {user.mention_html()}! Mən **{AI_NAME}**. Sənə necə kömək edə bilərəm? "
        "Mən həm özəl söhbətlərdə, həm də qruplarda sizə cavab verə bilərəm!"
    )

# AI-dan cavab almaq üçün funksiya
async def get_gpt_response(prompt: str, user_id: int) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_MESSAGE},
        {"role": "user", "content": prompt}
    ]
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    json_data = {
        "model": GPT_MODEL,
        "messages": messages,
        "temperature": 0.7, # Yaradıcılıq dərəcəsi
        "max_tokens": 150,  # Cavabın maksimum uzunluğu (tokenlərlə)
        "user": str(user_id) # API istifadəsini izləmək üçün
    }

    try:
        response = await openai_client.post("chat/completions", headers=headers, json=json_data)
        response.raise_for_status() # HTTP xətalarını qaldır
        response_data = response.json()
        
        if response_data and 'choices' in response_data and len(response_data['choices']) > 0:
            return response_data['choices'][0]['message']['content'].strip()
        else:
            logger.warning(f"Unexpected GPT response format: {response_data}")
            return "Üzr istəyirəm, cavab ala bilmədim. Bir az sonra yenə cəhd edin."
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP xətası baş verdi: {e.response.status_code} - {e.response.text}")
        if e.response.status_code == 429:
            return "Çox sorğu göndərildi, zəhmət olmasa bir az gözləyin."
        return "Üzr istəyirəm, xəta baş verdi. Zəhmət olmasa bir az sonra yenə cəhd edin."
    except httpx.RequestError as e:
        logger.error(f"Sorğu xətası baş verdi: {e}")
        return "Şəbəkə xətası baş verdi. Zəhmət olmasa internet bağlantınızı yoxlayın."
    except Exception as e:
        logger.error(f"Gözlənilməyən xəta: {e}", exc_info=True)
        return "Bilinməyən bir xəta baş verdi. Zəhmət olmasa administratorla əlaqə saxlayın."


# Mətn mesajlarını idarə edən funksiya
async def handle_message(update: Update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    user_message = update.message.text
    chat_type = update.effective_chat.type # 'private', 'group', 'supergroup'

    logger.info(f"Received message in {chat_type} chat from {update.effective_user.full_name} ({user_id}): {user_message}")

    if chat_type == 'private':
        # Şəxsi söhbətlərdə hər mesaja cavab ver
        response = await get_gpt_response(user_message, user_id)
        await update.message.reply_text(response)
    elif chat_type in ['group', 'supergroup']:
        # Qrup söhbətlərində yalnız botun adı çəkiləndə cavab ver
        # Və ya bot /komanda ilə çağırılanda (bu hissəni command handler artıq edir)
        # Check if the message starts with the bot's mention in a group
        bot_username = context.bot.username # Botun istifadəçi adını alırıq
        if bot_username and user_message.startswith(f"@{bot_username}"):
            # Botun adını mesajdan silib GPT-yə göndəririk
            cleaned_message = user_message[len(f"@{bot_username}"):].strip()
            if cleaned_message: # Boş mesaj olmasın
                response = await get_gpt_response(cleaned_message, user_id)
                await update.message.reply_text(response)
            else:
                await update.message.reply_text(f"Nə lazımdır, {update.effective_user.first_name}? Mən {AI_NAME}.")
        # Əlavə: Qrupda hər mesaja cavab vermək istəmiriksə, yuxarıdakı "if" kifayətdir.
        # Əgər bütün mesajlara cavab verməsini istəyiriksə, bu hissəni də qeyd etmək olar.
        # Amma bu, adətən qrup söhbətlərində narahatlıq yarada bilər.
    else:
        logger.info(f"Unsupported chat type: {chat_type}. Message: {user_message}")


# Əsas funksiya (botu işə salır)
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Komanda idarəedicilərini əlavə edirik
    application.add_handler(CommandHandler("start", start))

    # Mətn mesajları üçün idarəedici
    # filters.TEXT & ~filters.COMMAND - yəni yalnız mətn olsun və komanda olmasın
    # filters.ChatType.PRIVATE | filters.ChatType.GROUPS - həm özəl, həm də qrup söhbətlərini dəstəkləyir
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & (filters.ChatType.PRIVATE | filters.ChatType.GROUPS), handle_message))

    # Render.com üçün webhook
    PORT = int(os.environ.get("PORT", "8000"))
    RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME") # Render.com tərəfindən təyin olunur

    if not RENDER_EXTERNAL_HOSTNAME:
        # Yerli test üçün polling istifadə edin, əgər RENDER_EXTERNAL_HOSTNAME təyin edilməyibsə
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
