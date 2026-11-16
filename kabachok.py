import json
import os
import re
import threading
import time
from bs4 import BeautifulSoup
import requests
import telebot
from telebot import types

# ================= НАСТРОЙКИ =================
TELEGRAM_TOKEN = '9218068672:AAGClbGyFZA4ucQ2e2Agnnc3QBpelSkrHcc'
BOT_BRAND_NAME = 'Кабачкі от Альберта кобачо☝️😎🤙'

bot = telebot.TeleBot(TELEGRAM_TOKEN)

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,'
        ' like Gecko) Chrome/122.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'uk-UA,uk;q=0.9,ru;q=0.8',
}

USERS_FILE = 'users_db.json'
# Временное хранилище для ввода цен: {chat_id: 'iphone_price' или 'clothes_price'}
waiting_for_input = {}


def load_users():
  if os.path.exists(USERS_FILE):
    try:
      with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)
    except Exception:
      pass
  return {}


def save_users():
  try:
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
      json.dump(users_db, f, ensure_ascii=False, indent=2)
  except Exception as c:
    print(f'Ошибка сохранения базы: {c}')


users_db = load_users()
seen_ids = set()

IPHONE_MODELS = [
    '7',
    '8',
    'se',
    'x',
    'xr',
    'xs',
    '11',
    '12',
    '13',
    '14',
    '15',
    '16',
    '17',
]

STOP_WORDS = [
    'чехол',
    'чохол',
    'стекло',
    'скло',
    'коробка',
    'кабель',
    'зарядка',
    'блок',
    'наушники',
    'навушники',
    'ремонт',
    'разборка',
    'розборка',
    'на запчасти',
    'на запчастини',
    'заблокирован',
    'заблокований',
    'icloud',
    'айклауд',
    'дисплей',
    'аккумулятор',
    'корпус',
    'плата',
]


def get_user_state(chat_id):
  uid = str(chat_id)
  if uid not in users_db:
    users_db[uid] = {
        'running': True,
        'iphones_enabled': True,
        'clothes_enabled': True,
        'sort_mode': 'new',
        'max_iphone_price': 45000,
        'max_clothes_price': 12000,
    }
    save_users()
  return users_db[uid]


def get_main_menu(chat_id):
  state = get_user_state(chat_id)
  markup = types.InlineKeyboardMarkup(row_width=2)

  status_text = '🟢 Мониторинг: ВКЛ' if state['running'] else '🔴 Мониторинг: ВЫКЛ'
  iphone_text = '📱 iPhone: ВКЛ' if state['iphones_enabled'] else '📱 iPhone: ВЫКЛ'
  clothes_text = (
      '🧥 Stone/CP: ВКЛ' if state['clothes_enabled'] else '🧥 Stone/CP: ВЫКЛ'
  )
  sort_text = (
      '🕒 Сорт: Новые' if state['sort_mode'] == 'new' else '💰 Сорт: Дешевые'
  )

  btn_status = types.InlineKeyboardButton(
      status_text, callback_data='toggle_run'
  )
  btn_iphone = types.InlineKeyboardButton(
      iphone_text, callback_data='toggle_iphone'
  )
  btn_clothes = types.InlineKeyboardButton(
      clothes_text, callback_data='toggle_clothes'
  )
  btn_sort = types.InlineKeyboardButton(sort_text, callback_data='toggle_sort')

  # Кнопки изменения цен
  btn_set_iphone_price = types.InlineKeyboardButton(
      f'💵 Лимит iPhone ({state["max_iphone_price"]} грн)',
      callback_data='set_iphone_price',
  )
  btn_set_clothes_price = types.InlineKeyboardButton(
      f'💵 Лимит шмота ({state["max_clothes_price"]} грн)',
      callback_data='set_clothes_price',
  )

  btn_check_now = types.InlineKeyboardButton(
      '🚀 Проверить сейчас', callback_data='force_check'
  )

  markup.add(btn_status)
  markup.add(btn_iphone, btn_clothes)
  markup.add(btn_set_iphone_price, btn_set_clothes_price)
  markup.add(btn_sort)
  markup.add(btn_check_now)
  return markup


@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
  chat_id = message.chat.id
  state = get_user_state(chat_id)

  text = (
      f'<b>⚡ {BOT_BRAND_NAME}</b>\n'
      '━━━━━━━━━━━━━━━━━━━━\n'
      '📱 <b>iPhone:</b> 7, 8, SE, X, XR, XS, 11–17\n'
      f'💵 <b>Лимит iPhone:</b> до {state["max_iphone_price"]} грн\n\n'
      '🧥 <b>Бренды:</b> Stone Island, C.P. Company\n'
      f'💵 <b>Лимит шмота:</b> до {state["max_clothes_price"]} грн\n'
      '━━━━━━━━━━━━━━━━━━━━\n'
      '<i>Управляй ценами и фильтрами кнопками ниже:</i>'
  )
  bot.send_message(
      chat_id, text, parse_mode='HTML', reply_markup=get_main_menu(chat_id)
  )


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
  chat_id = call.message.chat.id
  state = get_user_state(chat_id)

  if call.data == 'toggle_run':
    state['running'] = not state['running']
  elif call.data == 'toggle_iphone':
    state['iphones_enabled'] = not state['iphones_enabled']
  elif call.data == 'toggle_clothes':
    state['clothes_enabled'] = not state['clothes_enabled']
  elif call.data == 'toggle_sort':
    state['sort_mode'] = 'cheap' if state['sort_mode'] == 'new' else 'new'
  elif call.data == 'set_iphone_price':
    waiting_for_input[chat_id] = 'iphone_price'
    bot.answer_callback_query(call.id)
    bot.send_message(
        chat_id,
        '📱 Введи максимальную цену для iPhone в гривнах (например: <code>35000</code>):',
        parse_mode='HTML',
    )
    return
  elif call.data == 'set_clothes_price':
    waiting_for_input[chat_id] = 'clothes_price'
    bot.answer_callback_query(call.id)
    bot.send_message(
        chat_id,
        '🧥 Введи максимальную цену для брендового шмота в гривнах (например:'
        ' <code>8000</code>):',
        parse_mode='HTML',
    )
    return
  elif call.data == 'force_check':
    bot.answer_callback_query(call.id, 'Альберт собирает урожай для тебя...')
    threading.Thread(target=run_check_for_user, args=(chat_id,)).start()
    return

  save_users()
  bot.answer_callback_query(call.id, 'Настройки обновлены!')
  try:
    bot.edit_message_reply_markup(
        chat_id, call.message.message_id, reply_markup=get_main_menu(chat_id)
    )
  except Exception:
    pass


@bot.message_handler(func=lambda message: message.chat.id in waiting_for_input)
def handle_price_input(message):
  chat_id = message.chat.id
  action = waiting_for_input.get(chat_id)
  text = message.text.strip()

  if not text.isdigit():
    bot.send_message(
        chat_id, '❌ Ошибка! Введи только число (например: 30000)'
    )
    return

  price = int(text)
  state = get_user_state(chat_id)

  if action == 'iphone_price':
    state['max_iphone_price'] = price
    bot.send_message(
        chat_id,
        f'✅ Лимит на iPhone успешно изменен: <b>до {price} грн</b>',
        parse_mode='HTML',
        reply_markup=get_main_menu(chat_id),
    )
  elif action == 'clothes_price':
    state['max_clothes_price'] = price
    bot.send_message(
        chat_id,
        f'✅ Лимит на шмот успешно изменен: <b>до {price} грн</b>',
        parse_mode='HTML',
        reply_markup=get_main_menu(chat_id),
    )

  save_users()
  del waiting_for_input[chat_id]


def extract_price_number(price_str):
  digits = re.sub(r'[^\d]', '', price_str)
  return int(digits) if digits else 0


def is_valid_iphone(title, price_num, state):
  title_low = title.lower()
  if 'iphone' not in title_low and 'айфон' not in title_low:
    return False
  for bad in STOP_WORDS:
    if bad in title_low:
      return False
  has_model = any(
      re.search(rf'\b{m}\b', title_low)
      or f'iphone{m}' in title_low
      or f'айфон{m}' in title_low
      for m in IPHONE_MODELS
  )
  if not has_model:
    return False
  if price_num < 1500 or price_num > state['max_iphone_price']:
    return False
  return True


def is_valid_clothes(title, price_num, state):
  title_low = title.lower()
  brands = [
      'stone island',
      'стоник',
      'стон айленд',
      'cp company',
      'c.p. company',
      'сп компани',
      'с.п. компани',
  ]
  if not any(b in title_low for b in brands):
    return False
  if price_num < 300 or price_num > state['max_clothes_price']:
    return False
  return True


def fetch_olx_ads(url, category_type, state):
  found_items = []
  try:
    resp = requests.get(url, headers=HEADERS, timeout=12)
    if resp.status_code != 200:
      return []
    soup = BeautifulSoup(resp.text, 'html.parser')
    cards = soup.select('div[data-cy="l-card"]')

    for ad in cards:
      title_el = ad.select_one('h4')
      link_el = ad.select_one('a')
      price_el = ad.select_one('p[data-testid="ad-price"]')
      loc_el = ad.select_one('p[data-testid="location-date"]')

      if not title_el or not link_el:
        continue

      title = title_el.text.strip()
      link = link_el.get('href', '')
      if link and not link.startswith('http'):
        link = 'https://www.olx.ua' + link

      ad_id = link.split('/')[-1].split('.')[0]
      price_str = price_el.text.strip() if price_el else '0 грн'
      price_num = extract_price_number(price_str)
      location = loc_el.text.strip() if loc_el else 'Украина'

      valid = False
      if category_type == 'iphone' and is_valid_iphone(title, price_num, state):
        valid = True
      elif category_type == 'clothes' and is_valid_clothes(
          title, price_num, state
      ):
        valid = True

      seen_ids.add(ad_id)
      if valid:
        found_items.append({
            'id': ad_id,
            'title': title,
            'price_str': price_str,
            'price_num': price_num,
            'link': link,
            'location': location,
            'type': category_type,
        })
  except Exception as e:
    print(f'Ошибка парсинга ({category_type}): {e}')

  return found_items


def send_ad_to_user(chat_id, item):
  badge = (
      '📱 <b>СВЕЖИЙ IPHONE</b>'
      if item['type'] == 'iphone'
      else '🧥 <b>БРЕНДОВЫЙ ШМОТ</b>'
  )
  card_text = (
      f'🥒 <i>{BOT_BRAND_NAME}</i>\n'
      f'{badge}\n'
      '━━━━━━━━━━━━━━━━━━━━\n'
      f'🏷 <b>{item["title"]}</b>\n\n'
      f'💰 <b>Цена:</b> <code>{item["price_str"]}</code>\n'
      f'📍 <b>Локация:</b> {item["location"]}\n'
      '━━━━━━━━━━━━━━━━━━━━'
  )

  markup = types.InlineKeyboardMarkup()
  markup.add(
      types.InlineKeyboardButton('🔗 Забрать на OLX', url=item['link'])
  )

  try:
    bot.send_message(
        chat_id, card_text, parse_mode='HTML', reply_markup=markup
    )
  except Exception as e:
    print(f'Ошибка отправки пользователю {chat_id}: {e}')


def run_check_for_user(chat_id):
  state = get_user_state(chat_id)
  urls = []
  if state['iphones_enabled']:
    urls.append((
        'https://www.olx.ua/d/uk/elektronika/telefony-i-aksesuary/mobilnye-telefony-smartfony/q-iphone/?search%5Border_filter%5D=created:desc',
        'iphone',
    ))
  if state['clothes_enabled']:
    urls.append((
        'https://www.olx.ua/d/uk/moda-i-stil/q-stone-island/?search%5Border_filter%5D=created:desc',
        'clothes',
    ))
    urls.append((
        'https://www.olx.ua/d/uk/moda-i-stil/q-cp-company/?search%5Border_filter%5D=created:desc',
        'clothes',
    ))

  all_items = []
  for url, cat_type in urls:
    ads = fetch_olx_ads(url, cat_type, state)
    all_items.extend(ads)
    time.sleep(1)

  if state['sort_mode'] == 'cheap':
    all_items.sort(key=lambda x: x['price_num'])
  else:
    all_items.reverse()

  for item in all_items:
    send_ad_to_user(chat_id, item)
    time.sleep(1)


def global_background_loop():
  print(f'[{BOT_BRAND_NAME}] Глобальный цикл мониторинга запущен...')
  dummy_state = {
      'iphones_enabled': True,
      'clothes_enabled': True,
      'max_iphone_price': 100000,
      'max_clothes_price': 50000,
  }
  try:
    for u, c in [
        (
            'https://www.olx.ua/d/uk/elektronika/telefony-i-aksesuary/mobilnye-telefony-smartfony/q-iphone/?search%5Border_filter%5D=created:desc',
            'iphone',
        ),
        (
            'https://www.olx.ua/d/uk/moda-i-stil/q-stone-island/?search%5Border_filter%5D=created:desc',
            'clothes',
        ),
    ]:
      fetch_olx_ads(u, c, dummy_state)
    print(f'Инициализация завершена. В базе {len(seen_ids)} объявлений.')
  except Exception as e:
    print(f'Ошибка инициализации: {e}')

  while True:
    time.sleep(60)
    for chat_id_str, state in list(users_db.items()):
      if not state.get('running', True):
        continue
      try:
        chat_id = int(chat_id_str)
        urls = []
        if state['iphones_enabled']:
          urls.append((
              'https://www.olx.ua/d/uk/elektronika/telefony-i-aksesuary/mobilnye-telefony-smartfony/q-iphone/?search%5Border_filter%5D=created:desc',
              'iphone',
          ))
        if state['clothes_enabled']:
          urls.append((
              'https://www.olx.ua/d/uk/moda-i-stil/q-stone-island/?search%5Border_filter%5D=created:desc',
              'clothes',
          ))
          urls.append((
              'https://www.olx.ua/d/uk/moda-i-stil/q-cp-company/?search%5Border_filter%5D=created:desc',
              'clothes',
          ))

        user_new_ads = []
        for url, cat_type in urls:
          try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
              continue
            soup = BeautifulSoup(resp.text, 'html.parser')
            for ad in soup.select('div[data-cy="l-card"]'):
              title_el = ad.select_one('h4')
              link_el = ad.select_one('a')
              price_el = ad.select_one('p[data-testid="ad-price"]')
              loc_el = ad.select_one('p[data-testid="location-date"]')
              if not title_el or not link_el:
                continue

              title = title_el.text.strip()
              link = link_el.get('href', '')
              if link and not link.startswith('http'):
                link = 'https://www.olx.ua' + link
              ad_id = link.split('/')[-1].split('.')[0]

              if ad_id in seen_ids:
                continue

              price_str = price_el.text.strip() if price_el else '0 грн'
              price_num = extract_price_number(price_str)
              location = loc_el.text.strip() if loc_el else 'Украина'

              valid = False
              if cat_type == 'iphone' and is_valid_iphone(
                  title, price_num, state
              ):
                valid = True
              elif cat_type == 'clothes' and is_valid_clothes(
                  title, price_num, state
              ):
                valid = True

              seen_ids.add(ad_id)
              if valid:
                user_new_ads.append({
                    'id': ad_id,
                    'title': title,
                    'price_str': price_str,
                    'price_num': price_num,
                    'link': link,
                    'location': location,
                    'type': cat_type,
                })
          except Exception:
            pass
          time.sleep(1)

        if state['sort_mode'] == 'cheap':
          user_new_ads.sort(key=lambda x: x['price_num'])
        else:
          user_new_ads.reverse()

        for item in user_new_ads:
          send_ad_to_user(chat_id, item)
          time.sleep(1)

      except Exception as e:
        print(f'Ошибка у пользователя {chat_id_str}: {e}')


if __name__ == '__main__':
  threading.Thread(target=global_background_loop, daemon=True).start()
  print(f'Публичный бот "{BOT_BRAND_NAME}" запущен в облаке!')

  while True:
    try:
      bot.infinity_polling(
          skip_pending=True, timeout=30, long_polling_timeout=20
      )
    except Exception as e:
      print(f'Связь с Telegram оборвалась ({e}). Переподключение...')
      time.sleep(10)

