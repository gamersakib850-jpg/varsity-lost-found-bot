import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)
from fuzzywuzzy import fuzz

# Logging সেটআপ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Bot Token
TOKEN = "8809347415:AAFwSQE2A9Tij1IM7-7odohAP9kHnRJpEDg"

# চ্যানেল আইডি (চ্যানেলে পোস্ট করতে না চাইলে None রাখুন)
CHANNEL_ID ="-1004462373531"

# Conversation States
CATEGORY, TITLE, LOCATION, DESCRIPTION, PHOTO, CONTACT = range(6)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('lost_found.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT,
            title TEXT,
            location TEXT,
            description TEXT,
            photo_id TEXT,
            contact TEXT,
            status TEXT DEFAULT 'ACTIVE'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def insert_item(user_id, category, title, location, description, photo_id, contact):
    conn = sqlite3.connect('lost_found.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO items (user_id, category, title, location, description, photo_id, contact)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, category, title, location, description, photo_id, contact))
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return item_id

def get_all_items():
    conn = sqlite3.connect('lost_found.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, category, title, location, description, contact FROM items WHERE status = 'ACTIVE' ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
    return rows

def search_items(keyword):
    conn = sqlite3.connect('lost_found.db')
    cursor = conn.cursor()
    query = f"%{keyword}%"
    cursor.execute("SELECT id, category, title, location, description, contact FROM items WHERE status = 'ACTIVE' AND (title LIKE ? OR description LIKE ? OR location LIKE ?) ORDER BY id DESC", (query, query, query))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_user_items(user_id):
    conn = sqlite3.connect('lost_found.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, category, title, location FROM items WHERE user_id = ? AND status = 'ACTIVE' ORDER BY id DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_item(item_id, user_id):
    conn = sqlite3.connect('lost_found.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE items SET status = 'RESOLVED' WHERE id = ? AND user_id = ?", (item_id, user_id))
    conn.commit()
    conn.close()

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("Lost (হারিয়ে গেছে)", callback_data="Lost"),
            InlineKeyboardButton("Found (পাওয়া গেছে)", callback_data="Found"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "স্বাগতম! আপনি কি কোনো জিনিস হারিয়েছেন নাকি খুঁজে পেয়েছেন?\n\n"
        "💡 **দরকারি কমান্ডসমূহ:**\n"
        "• /all - সর্বশেষ ১০টি পোস্ট দেখতে\n"
        "• /search <নাম> - নির্দিষ্ট কোনো জিনিস খুঁজতে\n"
        "• /my_items - আপনার তৈরি পোস্ট দেখতে ও ডিলিট করতে",
        reply_markup=reply_markup
    )
    return CATEGORY

async def category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['category'] = query.data
    
    await query.edit_message_text(
        text=f"আপনি **{query.data}** নির্বাচন করেছেন।\n\nজিনিসটির নাম বা শিরোনাম লিখুন (যেমন: কালো মানিব্যাগ, আইডি কার্ড):"
    )
    return TITLE

async def title_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['title'] = update.message.text
    await update.message.reply_text("কোথায় হারিয়েছেন বা পেয়েছেন? (লোকেশন লিখুন):")
    return LOCATION

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['location'] = update.message.text
    await update.message.reply_text("জিনিসটির বিস্তারিত বিবরণ দিন (যেমন: রং, ব্র্যান্ড বা অন্য কোনো বিশেষ চিহ্ন):")
    return DESCRIPTION

async def description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['description'] = update.message.text
    
    keyboard = [[InlineKeyboardButton("ছবি ছাড়া চালিয়ে যান (Skip)", callback_data="skip_photo")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "জিনিসটির একটি ছবি পাঠাতে পারেন (ছবি না থাকলে নিচের Skip বাটনে ক্লিক করুন):",
        reply_markup=reply_markup
    )
    return PHOTO

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.photo:
        context.user_data['photo_id'] = update.message.photo[-1].file_id
    else:
        context.user_data['photo_id'] = None
        
    await update.message.reply_text("আপনার সাথে যোগাযোগ করার ঠিকানা/ফোন নম্বর/টেলিগ্রাম ইউজারনেম দিন:")
    return CONTACT

async def skip_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['photo_id'] = None
    
    await query.edit_message_text("ছবি স্কিপ করা হয়েছে।")
    await query.message.reply_text("আপনার সাথে যোগাযোগ করার ঠিকানা/ফোন নম্বর/টেলিগ্রাম ইউজারনেম দিন:")
    return CONTACT

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        contact = update.message.text
        
        category = context.user_data.get('category', 'N/A')
        title = context.user_data.get('title', 'N/A')
        location = context.user_data.get('location', 'N/A')
        description = context.user_data.get('description', 'N/A')
        photo_id = context.user_data.get('photo_id')
        
        # ১. ডাটাবেজে সেভ
        item_id = insert_item(user_id, category, title, location, description, photo_id, contact)
        
        summary = (
            f"✅ **আপনার এন্ট্রি সফলভাবে সেভ হয়েছে! (ID: #{item_id})**\n\n"
            f"**টাইপ:** {category}\n"
            f"**নাম:** {title}\n"
            f"**লোকেশন:** {location}\n"
            f"**বিবরণ:** {description}\n"
            f"**যোগাযোগ:** {contact}"
        )
        
        # ২. ইউজারকে সাথে সাথে রিপ্লাই দেওয়া
        if photo_id:
            await update.message.reply_photo(photo=photo_id, caption=summary)
        else:
            await update.message.reply_text(summary)
            
        # ৩. চ্যানেলে অটো-পোস্ট (যদি CHANNEL_ID সেট করা থাকে)
        if CHANNEL_ID:
            try:
                channel_text = f"📢 **NEW {category.upper()} ITEM**\n\n📌 **{title}**\n📍 **লোকেশন:** {location}\n📝 **বিবরণ:** {description}\n📞 **যোগাযোগ:** {contact}"
                if photo_id:
                    await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo_id, caption=channel_text)
                else:
                    await context.bot.send_message(chat_id=CHANNEL_ID, text=channel_text)
            except Exception as channel_err:
                logging.error(f"Channel post error: {channel_err}")

        # ৪. ম্যাচিং এন্ট্রি চেক
        await check_matches(update, context, title, category)

    except Exception as e:
        logging.error(f"Contact handler error: {e}")
        await update.message.reply_text("❌ একটি সমস্যা হয়েছে, অনুগ্রহ করে /start লিখে আবার চেষ্টা করুন।")

    return ConversationHandler.END

async def check_matches(update: Update, context: ContextTypes.DEFAULT_TYPE, new_title, new_category):
    try:
        opposite_category = "Found" if new_category == "Lost" else "Lost"
        
        conn = sqlite3.connect('lost_found.db')
        cursor = conn.cursor()
        cursor.execute("SELECT title, location, contact FROM items WHERE category = ? AND status = 'ACTIVE'", (opposite_category,))
        items = cursor.fetchall()
        conn.close()
        
        matches = []
        for title, location, contact in items:
            ratio = fuzz.partial_ratio(new_title.lower(), title.lower())
            if ratio > 60:
                matches.append(f"• **{title}** ({location}) - যোগাযোগ: {contact}")
                
        if matches:
            text = "🔎 **আপনার পোস্টের সাথে সামঞ্জস্যপূর্ণ কিছু পোস্ট পাওয়া গেছে:**\n\n" + "\n".join(matches)
            await update.message.reply_text(text)
    except Exception as e:
        logging.error(f"Match check error: {e}")

async def show_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    items = get_all_items()
    if not items:
        await update.message.reply_text("এখনো কোনো সক্রিয় পোস্ট নেই।")
        return
        
    text = "📋 **সর্বশেষ ১০টি পোস্ট:**\n\n"
    for item_id, cat, title, loc, desc, cont in items:
        text += f"🆔 #{item_id} | 📌 [{cat}] **{title}**\n📍 {loc} | 📝 {desc}\n📞 {cont}\n-------------------\n"
        
    await update.message.reply_text(text)

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("কীওয়ার্ড দিয়ে সার্চ করতে এভাবে লিখুন:\n`/search moneybag` অথবা `/search ID`")
        return
        
    keyword = " ".join(context.args)
    results = search_items(keyword)
    
    if not results:
        await update.message.reply_text(f"❌ **'{keyword}'** সম্পর্কিত কোনো পোস্ট পাওয়া যায়নি।")
        return
        
    text = f"🔎 **'{keyword}' লিখে সার্চ করার ফলাফল:**\n\n"
    for item_id, cat, title, loc, desc, cont in results:
        text += f"🆔 #{item_id} | 📌 [{cat}] **{title}**\n📍 {loc} | 📝 {desc}\n📞 {cont}\n-------------------\n"
        
    await update.message.reply_text(text)

async def my_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    items = get_user_items(user_id)
    
    if not items:
        await update.message.reply_text("আপনার কোনো সক্রিয় পোস্ট নেই।")
        return
        
    await update.message.reply_text("📋 **আপনার সকল পোস্ট:**")
    for item_id, cat, title, loc in items:
        keyboard = [[InlineKeyboardButton("✅ পেয়ে গেছি / ডিলিট করুন (Resolved)", callback_data=f"del_{item_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"🆔 **ID:** #{item_id}\n📌 **টাইপ:** {cat}\n🏷 **নাম:** {title}\n📍 **লোকেশন:** {loc}",
            reply_markup=reply_markup
        )

async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    item_id = int(query.data.split("_")[1])
    user_id = query.from_user.id
    
    delete_item(item_id, user_id)
    await query.edit_message_text(f"✅ পোস্টটি (ID: #{item_id}) সফলভাবে ডিলিট/Resolved করা হয়েছে!")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("প্রসেসটি বাতিল করা হয়েছে। নতুন করে শুরু করতে /start লিখুন।")
    return ConversationHandler.END

def main():
    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .get_updates_read_timeout(30.0)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CATEGORY: [CallbackQueryHandler(category_callback, pattern="^(Lost|Found)$")],
            TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, title_handler)],
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, location_handler)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description_handler)],
            PHOTO: [
                MessageHandler(filters.PHOTO, photo_handler),
                CallbackQueryHandler(skip_photo_callback, pattern="^skip_photo$")
            ],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact_handler)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler('all', show_all))
    app.add_handler(CommandHandler('search', search_command))
    app.add_handler(CommandHandler('my_items', my_items))
    app.add_handler(CallbackQueryHandler(delete_callback, pattern="^del_"))

    print("Bot running...")
    app.run_polling()

if __name__ == '__main__':
    main()