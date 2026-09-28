import os
import sqlite3
import urllib.request
import urllib.parse
import json
import time
from datetime import datetime

TOKEN = os.environ.get("BOT_TOKEN")

if not TOKEN:
    print("BOT_TOKEN topilmadi!")
    exit()

DB = "dokon.db"

conn = sqlite3.connect(DB, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    buy_price REAL,
    sell_price REAL,
    stock INTEGER,
    sold INTEGER DEFAULT 0,
    created_at TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    amount REAL,
    description TEXT,
    created_at TEXT
)
""")

conn.commit()


def telegram(method, data=None):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"

    if data:
        data = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(url, data=data)
    else:
        req = urllib.request.Request(url)

    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())


def send(chat_id, text):
    telegram("sendMessage", {
        "chat_id": chat_id,
        "text": text
    })


def help_text():
    return """🤖 DO‘KON HISOBLASH BOTI

📦 Yangi tovar:
 /tovar Nomi|olish_narxi|sotish_narxi|soni

Masalan:
 /tovar Telefon|100|150|10

🛒 Sotuv:
 /sotuv Nomi|soni

Masalan:
 /sotuv Telefon|2

💸 Xarajat:
 /xarajat Summa|izoh

Masalan:
 /xarajat 50|Yetkazib berish

📋 Jadval:
 /jadval

📊 Tahlil:
 /tahlil

❓ Yordam:
 /yordam
"""


def add_product(chat_id, text):
    try:
        parts = text.split("|")

        if len(parts) != 4:
            send(chat_id, "❌ Format xato.\n\nMasalan:\n/tovar Telefon|100|150|10")
            return

        name = parts[0].strip()
        buy = float(parts[1])
        sell = float(parts[2])
        qty = int(parts[3])

        cur.execute("""
        INSERT INTO products
        (name, buy_price, sell_price, stock, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (
            name,
            buy,
            sell,
            qty,
            datetime.now().isoformat()
        ))

        conn.commit()

        send(
            chat_id,
            f"""✅ Tovar qo‘shildi!

📦 {name}
💰 Olish: {buy:,.0f}
💵 Sotish: {sell:,.0f}
📦 Miqdor: {qty} dona
📈 1 donadan foyda: {sell-buy:,.0f}"""
        )

    except sqlite3.IntegrityError:
        send(chat_id, "❌ Bu tovar allaqachon mavjud.")

    except Exception:
        send(chat_id, "❌ Ma'lumotni tekshiring.")


def sell_product(chat_id, text):
    try:
        parts = text.split("|")

        if len(parts) != 2:
            send(chat_id, "❌ Format:\n/sotuv Tovar|soni")
            return

        name = parts[0].strip()
        qty = int(parts[1])

        cur.execute(
            "SELECT buy_price, sell_price, stock, sold FROM products WHERE name=?",
            (name,)
        )

        product = cur.fetchone()

        if not product:
            send(chat_id, "❌ Bunday tovar topilmadi.")
            return

        buy, sell, stock, sold = product

        if qty > stock:
            send(
                chat_id,
                f"❌ Omborda yetarli emas.\n\nQoldiq: {stock} dona"
            )
            return

        cur.execute("""
        UPDATE products
        SET stock = stock - ?, sold = sold + ?
        WHERE name=?
        """, (qty, qty, name))

        conn.commit()

        profit = (sell - buy) * qty

        send(
            chat_id,
            f"""✅ Sotuv yozildi!

📦 {name}
🛒 Sotildi: {qty} dona
💰 Tushum: {sell*qty:,.0f}
📈 Foyda: {profit:,.0f}
📦 Qoldiq: {stock-qty} dona"""
        )

    except Exception:
        send(chat_id, "❌ Formatni tekshiring.")


def add_expense(chat_id, text):
    try:
        parts = text.split("|")

        if len(parts) != 2:
            send(chat_id, "❌ Format:\n/xarajat Summa|izoh")
            return

        amount = float(parts[0])
        description = parts[1].strip()

        cur.execute("""
        INSERT INTO expenses
        (amount, description, created_at)
        VALUES (?, ?, ?)
        """, (
            amount,
            description,
            datetime.now().isoformat()
        ))

        conn.commit()

        send(
            chat_id,
            f"""✅ Xarajat yozildi!

💸 Summa: {amount:,.0f}
📝 {description}"""
        )

    except Exception:
        send(chat_id, "❌ Summani tekshiring.")


def table(chat_id):
    cur.execute("""
    SELECT name, buy_price, sell_price, stock, sold
    FROM products
    ORDER BY name
    """)

    rows = cur.fetchall()

    if not rows:
        send(chat_id, "📋 Hozircha tovarlar yo‘q.")
        return

    text = "📋 DO‘KON JADVALI\n\n"

    for name, buy, sell, stock, sold in rows:
        text += (
            f"📦 {name}\n"
            f"  Olish: {buy:,.0f}\n"
            f"  Sotish: {sell:,.0f}\n"
            f"  Qoldiq: {stock}\n"
            f"  Sotilgan: {sold}\n"
            f"  Foyda/dona: {sell-buy:,.0f}\n\n"
        )

    send(chat_id, text)


def analysis(chat_id):
    cur.execute("""
    SELECT
        COALESCE(SUM(sold * sell_price), 0),
        COALESCE(SUM(sold * (sell_price-buy_price)), 0),
        COALESCE(SUM(stock * buy_price), 0),
        COALESCE(SUM(stock * sell_price), 0),
        COALESCE(SUM(sold), 0)
    FROM products
    """)

    revenue, profit, stock_buy, stock_sell, total_sold = cur.fetchone()

    cur.execute("SELECT COALESCE(SUM(amount),0) FROM expenses")
    expenses = cur.fetchone()[0]

    net_profit = profit - expenses

    cur.execute("""
    SELECT name, sold
    FROM products
    ORDER BY sold DESC
    LIMIT 5
    """)

    best = cur.fetchall()

    best_text = ""

    if best:
        best_text = "\n🔥 ENG YAXSHI SOTILAYOTGANLAR:\n"
        for i, (name, sold) in enumerate(best, 1):
            best_text += f"{i}. {name} — {sold} dona\n"

    text = f"""📊 DO‘KON TAHLILI

💰 Umumiy tushum: {revenue:,.0f}
📈 Savdolardan foyda: {profit:,.0f}
💸 Xarajatlar: {expenses:,.0f}
💵 Sof foyda: {net_profit:,.0f}

🛒 Jami sotilgan: {total_sold} dona

📦 Ombordagi mahsulot tannarxi: {stock_buy:,.0f}
💵 Ombordagi taxminiy sotuv qiymati: {stock_sell:,.0f}
{best_text}
"""

    send(chat_id, text)


def process(update):
    if "message" not in update:
        return

    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if text == "/start":
        send(
            chat_id,
            "👋 Assalomu alaykum!\n\n"
            "Men sizning do‘kon hisob-kitob botingizman.\n\n"
            "Tovar, sotuv, xarajat, foyda va qoldiqni hisoblayman.\n\n"
            "Boshlash uchun /yordam ni bosing."
        )

    elif text == "/yordam":
        send(chat_id, help_text())

    elif text.startswith("/tovar "):
        add_product(chat_id, text[7:])

    elif text.startswith("/sotuv "):
        sell_product(chat_id, text[7:])

    elif text.startswith("/xarajat "):
        add_expense(chat_id, text[9:])

    elif text == "/jadval":
        table(chat_id)

    elif text == "/tahlil":
        analysis(chat_id)

    else:
        send(
            chat_id,
            "❓ Buyruq tushunilmadi.\n\n/yordam ni bosing."
        )


print("🤖 Bot ishga tushdi...")

offset = 0

while True:
    try:
        result = telegram(
            "getUpdates",
            {
                "timeout": 30,
                "offset": offset
            }
        )

        for update in result.get("result", []):
            offset = update["update_id"] + 1
            process(update)

    except Exception as e:
        print("Xato:", e)
        time.sleep(5)
