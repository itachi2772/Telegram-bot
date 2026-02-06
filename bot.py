import asyncio
import re
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# ==================  CONFIG ==================
BOT_TOKEN = "8431678781:AAGjoBygFOBfYbfbajkFMbGPGJbBvquo-C8"

# Developer Contact
DEV_CONTACT = "@Catmanskullhurtedwizard"  # Change this to your Telegram username

# Admin IDs - Only these users can use the bot
ADMIN_IDS = [8365902294, 8294407215, 8574635657]

# Chat IDs - Commands se automatically update hongi
CHAT_IDS = [-1003416392561, -1003679594763,-1003811715050]

# Access Codes - Format: {"code": {"user_id": ..., "access_level": "full/limited", "expires": None}}
ACCESS_CODES = {}

# Auto-delete time in seconds (2 minutes)
AUTO_DELETE_SECONDS = 120

# Sites - Format: {"id": 1, "name": "Site1", "login_url": "...", "username": "...", "password": "...", "sms_url": "..."}
SITES = [{'id': 1, 'name': '2D Site', 'login_url': 'http://139.99.63.204/ints/login', 'username': 'Itachi123', 'password': 'Itachi123', 'sms_url': 'http://139.99.63.204/ints/client/SMSCDRStats'}, {'id': 2, 'name': 'http://213.32.24.208/', 'login_url': 'http://213.32.24.208/ints/login', 'username': 'test123', 'password': 'test123', 'sms_url': 'http://213.32.24.208/ints/test/TestSMSCDRStats'}, {'id': 3, 'name': 'http://31.97.116.246/Agent/dashboard', 'login_url': 'http://31.97.116.246/Agent/dashboard', 'username': 'ghost123', 'password': 'ghost123', 'sms_url': 'http://31.97.116.246/Client/Reports'}, {'id': 4, 'name': 'Mait', 'login_url': 'http://217.182.195.194/ints/login', 'username': 'Heart12', 'password': 'Heart12', 'sms_url': 'http://217.182.195.194/ints/agent/SMSCDRStats'}, {'id': 5, 'name': 'Mait', 'login_url': 'http://217.182.195.194/ints/login', 'username': 'Heart12', 'password': 'Heart12', 'sms_url': 'http://217.182.195.194/ints/agent/SMSCDRStats'}, {'id': 6, 'name': 'SMS Panel', 'login_url': 'http://85.195.94.50/sms/SignIn', 'username': 'mr_itachi', 'password': '123456', 'sms_url': 'http://85.195.94.50/sms/reseller/SMSReports', 'universal_scan': True}]

import httpx
from telegram.request import HTTPXRequest

# Create bot with extended timeout
request = HTTPXRequest(connection_pool_size=8, read_timeout=30, write_timeout=30, connect_timeout=30)
bot = Bot(token=BOT_TOKEN, request=request)
site_monitors = {}  # Active monitoring tasks
last_sms_data = {}  # Track last SMS per site
messages_to_delete = []  # Track messages for auto-delete
# =============================================

# Conversation states for adding sites
SITE_NAME, SITE_LOGIN_URL, SITE_USERNAME, SITE_PASSWORD, SITE_SMS_URL = range(5)
# Conversation states for access codes
ACCESS_CODE_CREATE, ACCESS_CODE_LEVEL = range(5, 7)


def update_code_file(var_name, value):
    """Update variable in this Python file"""
    try:
        with open(__file__, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            if line.strip().startswith(f'{var_name} = '):
                if isinstance(value, list):
                    # For lists, format nicely
                    if var_name == "SITES":
                        # Format sites as multiline
                        lines[i] = f'{var_name} = {repr(value)}\n'
                    else:
                        # Format simple lists
                        value_str = repr(value)
                        lines[i] = f'{var_name} = {value_str}\n'
                else:
                    lines[i] = f'{var_name} = {repr(value)}\n'
                break
        
        with open(__file__, 'w', encoding='utf-8') as f:
            f.writelines(lines)
    except Exception as e:
        print(f"[ERROR] updating file: {e}")


def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS


def load_admin_ids():
    return ADMIN_IDS.copy()

def save_admin_ids(admin_ids):
    global ADMIN_IDS
    ADMIN_IDS = admin_ids
    update_code_file('ADMIN_IDS', admin_ids)

def load_chat_ids():
    return CHAT_IDS.copy()

def save_chat_ids(chat_ids):
    global CHAT_IDS
    CHAT_IDS = chat_ids
    update_code_file('CHAT_IDS', chat_ids)

def load_sites():
    return SITES.copy()

def save_sites(sites):
    global SITES
    SITES = sites
    update_code_file('SITES', sites)

def load_access_codes():
    return ACCESS_CODES.copy()

def save_access_codes(codes):
    global ACCESS_CODES
    ACCESS_CODES = codes
    update_code_file('ACCESS_CODES', codes)


async def auto_delete_message(message, delay=AUTO_DELETE_SECONDS):
    """Auto delete message after delay - silent fail"""
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except:
        # Silent fail - don't print errors for timeout/already deleted
        pass


async def send_auto_delete(update, text, parse_mode="HTML", reply_markup=None):
    """Send message that auto-deletes after 2 minutes"""
    try:
        msg = await update.message.reply_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
        asyncio.create_task(auto_delete_message(msg))
        # Also delete the user's command message
        asyncio.create_task(auto_delete_message(update.message))
        return msg
    except Exception as e:
        # If reply fails (message deleted), send directly to chat
        try:
            msg = await bot.send_message(
                chat_id=update.effective_chat.id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            asyncio.create_task(auto_delete_message(msg))
            return msg
        except:
            # Silent fail if even direct send fails
            return None


def solve_math_captcha(captcha_text):
    """Solve math captcha automatically"""
    try:
        match = re.search(r'(\d+)\s*([\+\-\*\/])\s*(\d+)', captcha_text)
        if match:
            num1 = int(match.group(1))
            operator = match.group(2)
            num2 = int(match.group(3))
            
            if operator == '+':
                return num1 + num2
            elif operator == '-':
                return num1 - num2
            elif operator == '*':
                return num1 * num2
            elif operator == '/':
                return num1 // num2
        return None
    except Exception as e:
        print(f"[ERROR] solving captcha: {e}")
        return None


def setup_driver():
    """Setup Chrome driver - Katabump/Docker/Windows compatible"""
    import tempfile
    import os
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--window-size=1280,720")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--disable-logging")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--disable-translate")
    chrome_options.add_argument("--disable-features=NetworkService")
    chrome_options.add_argument("--force-color-profile=srgb")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Cross-platform temp directory
    temp_dir = tempfile.gettempdir()
    chrome_options.add_argument(f"--user-data-dir={temp_dir}/chrome_profile_{int(time.time())}")
    
    try:
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)
    except:
        # Fallback for Katabump/Docker
        return webdriver.Chrome(options=chrome_options)


def get_progress_bar(step, total=5):
    """Generate progress bar"""
    filled = "█" * step
    empty = "░" * (total - step)
    percentage = int((step / total) * 100)
    return f"[{filled}{empty}] {percentage}%"


async def send_progress_update(chat_id, site_name, step, status_text):
    """Send progress update to admin"""
    steps = {
        1: "🔄 Connecting...",
        2: "🌐 Entering Site...",
        3: "🔐 Solving Captcha...",
        4: "✅ Login Success!",
        5: "🎯 Done - Monitoring Active!"
    }
    
    progress = get_progress_bar(step)
    current_status = steps.get(step, status_text)
    
    msg = f"""
<b>🖥️ {site_name}</b>

{progress}
<code>{current_status}</code>
"""
    try:
        sent_msg = await bot.send_message(chat_id, msg, parse_mode="HTML")
        return sent_msg
    except:
        return None


async def login_to_site_with_progress(driver, site, admin_chat_id=None):
    """Login to a site with progress updates"""
    progress_msg = None
    try:
        # Step 1: Connecting
        if admin_chat_id:
            progress_msg = await send_progress_update(admin_chat_id, site['name'], 1, "Connecting...")
        
        print(f"[{datetime.now()}] [{site['name']}] Logging in...")
        driver.get(site['login_url'])
        await asyncio.sleep(2)
        
        # Step 2: Entering site
        if admin_chat_id and progress_msg:
            try:
                await progress_msg.edit_text(
                    f"<b>🖥️ {site['name']}</b>\n\n{get_progress_bar(2)}\n<code>🌐 Entering Site...</code>",
                    parse_mode="HTML"
                )
            except:
                pass
        
        # Fill username
        username_field = driver.find_element(By.NAME, "username")
        username_field.clear()
        username_field.send_keys(site['username'])
        
        # Fill password
        password_field = driver.find_element(By.NAME, "password")
        password_field.clear()
        password_field.send_keys(site['password'])
        
        # Step 3: Solving captcha
        if admin_chat_id and progress_msg:
            try:
                await progress_msg.edit_text(
                    f"<b>🖥️ {site['name']}</b>\n\n{get_progress_bar(3)}\n<code>🔐 Solving Captcha...</code>",
                    parse_mode="HTML"
                )
            except:
                pass
        
        # Get and solve captcha
        captcha_element = driver.find_element(By.XPATH, "//div[@class='wrap-input100']")
        captcha_text = captcha_element.text
        answer = solve_math_captcha(captcha_text)
        
        if answer is None:
            print(f"[{datetime.now()}] [{site['name']}] Could not solve captcha")
            if admin_chat_id and progress_msg:
                try:
                    await progress_msg.edit_text(
                        f"<b>🖥️ {site['name']}</b>\n\n❌ <code>Captcha Failed!</code>",
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(3)
                    await progress_msg.delete()
                except:
                    pass
            return False
        
        print(f"[{datetime.now()}] [{site['name']}] Captcha solved: {answer}")
        
        # Fill captcha
        captcha_field = driver.find_element(By.NAME, "capt")
        captcha_field.clear()
        captcha_field.send_keys(str(answer))
        
        # Click login
        login_button = driver.find_element(By.CLASS_NAME, "login100-form-btn")
        login_button.click()
        await asyncio.sleep(3)
        
        if "login" not in driver.current_url.lower():
            # Step 4: Login success
            if admin_chat_id and progress_msg:
                try:
                    await progress_msg.edit_text(
                        f"<b>🖥️ {site['name']}</b>\n\n{get_progress_bar(4)}\n<code>✅ Login Success!</code>",
                        parse_mode="HTML"
                    )
                except:
                    pass
            
            await asyncio.sleep(1)
            
            # Step 5: Done
            if admin_chat_id and progress_msg:
                try:
                    await progress_msg.edit_text(
                        f"<b>🖥️ {site['name']}</b>\n\n{get_progress_bar(5)}\n<code>🎯 Done - Monitoring Active!</code>",
                        parse_mode="HTML"
                    )
                    await asyncio.sleep(3)
                    await progress_msg.delete()
                except:
                    pass
            
            print(f"[{datetime.now()}] [{site['name']}] Login successful")
            return True
        
        if admin_chat_id and progress_msg:
            try:
                await progress_msg.edit_text(
                    f"<b>🖥️ {site['name']}</b>\n\n❌ <code>Login Failed!</code>",
                    parse_mode="HTML"
                )
                await asyncio.sleep(3)
                await progress_msg.delete()
            except:
                pass
        
        print(f"[{datetime.now()}] [{site['name']}] Login failed")
        return False
        
    except Exception as e:
        print(f"[{datetime.now()}] [{site['name']}] Login error: {e}")
        if admin_chat_id and progress_msg:
            try:
                await progress_msg.edit_text(
                    f"<b>🖥️ {site['name']}</b>\n\n❌ <code>Error: {str(e)[:50]}</code>",
                    parse_mode="HTML"
                )
                await asyncio.sleep(3)
                await progress_msg.delete()
            except:
                pass
        return False


def login_to_site(driver, site):
    """Login to a site (without progress) - handles different login types"""
    try:
        print(f"[{datetime.now()}] [{site['name']}] Logging in...")
        driver.get(site['login_url'])
        time.sleep(2)
        
        # Check if this is a universal_scan site (different login form)
        if site.get('universal_scan', False):
            time.sleep(3)  # Wait for page to fully load
            
            # Get ALL input fields on the page
            all_inputs = driver.find_elements(By.TAG_NAME, "input")
            print(f"[{datetime.now()}] [{site['name']}] Found {len(all_inputs)} input fields")
            
            username_field = None
            password_field = None
            
            # Find username and password fields from all inputs
            for inp in all_inputs:
                try:
                    inp_type = inp.get_attribute("type") or ""
                    inp_name = inp.get_attribute("name") or ""
                    inp_id = inp.get_attribute("id") or ""
                    inp_class = inp.get_attribute("class") or ""
                    inp_placeholder = inp.get_attribute("placeholder") or ""
                    
                    # Debug: print field info
                    print(f"[{datetime.now()}] [{site['name']}] Input: type={inp_type}, name={inp_name}, id={inp_id}")
                    
                    # Password field
                    if inp_type.lower() == "password":
                        password_field = inp
                    # Username/text field
                    elif inp_type.lower() in ["text", "email", ""] and not username_field:
                        # Skip if it's likely a search or other field
                        if "search" not in inp_name.lower() and "search" not in inp_id.lower():
                            username_field = inp
                except:
                    continue
            
            # If still not found, try first two visible inputs
            if not username_field or not password_field:
                visible_inputs = [inp for inp in all_inputs if inp.is_displayed()]
                if len(visible_inputs) >= 2:
                    if not username_field:
                        username_field = visible_inputs[0]
                    if not password_field:
                        password_field = visible_inputs[1]
            
            if username_field and password_field:
                print(f"[{datetime.now()}] [{site['name']}] Found fields, entering credentials...")
                username_field.clear()
                username_field.send_keys(site['username'])
                time.sleep(0.5)
                password_field.clear()
                password_field.send_keys(site['password'])
                time.sleep(0.5)
                
                # Check for captcha field (name='capt' or similar)
                captcha_field = None
                captcha_text = None
                try:
                    # Try to find captcha input
                    captcha_field = driver.find_element(By.NAME, "capt")
                    
                    # Find captcha text/question on page
                    page_text = driver.find_element(By.TAG_NAME, "body").text
                    
                    # Look for math captcha pattern in page
                    import re
                    captcha_match = re.search(r'(\d+)\s*([+\-*\/])\s*(\d+)\s*=', page_text)
                    if captcha_match:
                        num1 = int(captcha_match.group(1))
                        operator = captcha_match.group(2)
                        num2 = int(captcha_match.group(3))
                        
                        if operator == '+':
                            answer = num1 + num2
                        elif operator == '-':
                            answer = num1 - num2
                        elif operator == '*':
                            answer = num1 * num2
                        elif operator == '/':
                            answer = num1 // num2
                        else:
                            answer = None
                        
                        if answer is not None:
                            print(f"[{datetime.now()}] [{site['name']}] Captcha solved: {answer}")
                            captcha_field.clear()
                            captcha_field.send_keys(str(answer))
                            time.sleep(0.5)
                except Exception as e:
                    print(f"[{datetime.now()}] [{site['name']}] No captcha or captcha error: {e}")
                
                # Find and click login button - try many selectors
                login_button = None
                button_selectors = [
                    "button[type='submit']",
                    "input[type='submit']",
                    "button.btn",
                    "button.btn-primary",
                    ".login-btn",
                    ".btn-login",
                    "button",
                    "input[type='button']",
                    ".submit",
                    "a.btn"
                ]
                
                for selector in button_selectors:
                    try:
                        buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                        for btn in buttons:
                            if btn.is_displayed():
                                login_button = btn
                                break
                        if login_button:
                            break
                    except:
                        continue
                
                # Also try finding by text content
                if not login_button:
                    try:
                        buttons = driver.find_elements(By.TAG_NAME, "button")
                        for btn in buttons:
                            if btn.is_displayed():
                                login_button = btn
                                break
                    except:
                        pass
                
                if login_button:
                    print(f"[{datetime.now()}] [{site['name']}] Clicking login button...")
                    login_button.click()
                    time.sleep(4)
                    
                    if "signin" not in driver.current_url.lower() and "login" not in driver.current_url.lower():
                        print(f"[{datetime.now()}] [{site['name']}] Login successful")
                        return True
                    else:
                        print(f"[{datetime.now()}] [{site['name']}] Still on login page, login may have failed")
            
            print(f"[{datetime.now()}] [{site['name']}] Login failed - could not find form fields")
            return False
        
        # Original captcha-based login for other sites
        # Fill username
        username_field = driver.find_element(By.NAME, "username")
        username_field.clear()
        username_field.send_keys(site['username'])
        
        # Fill password
        password_field = driver.find_element(By.NAME, "password")
        password_field.clear()
        password_field.send_keys(site['password'])
        
        # Get and solve captcha
        captcha_element = driver.find_element(By.XPATH, "//div[@class='wrap-input100']")
        captcha_text = captcha_element.text
        answer = solve_math_captcha(captcha_text)
        
        if answer is None:
            print(f"[{datetime.now()}] [{site['name']}] Could not solve captcha")
            return False
        
        print(f"[{datetime.now()}] [{site['name']}] Captcha solved: {answer}")
        
        # Fill captcha
        captcha_field = driver.find_element(By.NAME, "capt")
        captcha_field.clear()
        captcha_field.send_keys(str(answer))
        
        # Click login
        login_button = driver.find_element(By.CLASS_NAME, "login100-form-btn")
        login_button.click()
        time.sleep(3)
        
        if "login" not in driver.current_url.lower():
            print(f"[{datetime.now()}] [{site['name']}] Login successful")
            return True
        
        print(f"[{datetime.now()}] [{site['name']}] Login failed")
        return False
        
    except Exception as e:
        print(f"[{datetime.now()}] [{site['name']}] Login error: {e}")
        return False



def universal_page_scan(driver, site):
    """Universal scanner - handles SMS Panel table with Number at col 2 and Message at LAST col"""
    try:
        driver.get(site['sms_url'])
        time.sleep(3)
        
        # First try to find table
        tables = driver.find_elements(By.TAG_NAME, "table")
        
        if tables:
            for table in tables:
                rows = table.find_elements(By.TAG_NAME, "tr")
                
                # Skip header row, get first data row (latest SMS)
                if len(rows) > 1:
                    first_data_row = rows[1]
                    cells = first_data_row.find_elements(By.TAG_NAME, "td")
                    
                    if len(cells) >= 3:
                        row_data = [cell.text.strip() for cell in cells]
                        
                        # SMS Panel format:
                        # Col 0: Date, Col 1: Range, Col 2: Number, ... Col LAST: Message
                        phone_number = row_data[2] if len(row_data) > 2 else "N/A"
                        message = row_data[-1] if row_data else "N/A"  # LAST column is Message!
                        date_time = row_data[0] if row_data else "N/A"
                        
                        # Clean phone number (remove spaces/dashes)
                        phone_number = re.sub(r'[\s-]', '', phone_number)
                        
                        print(f"[{datetime.now()}] [{site['name']}] Found SMS: {phone_number} -> {message[:50]}...")
                        
                        return {
                            "time": date_time,
                            "number": phone_number,
                            "message": message,
                            "service": site['name']
                        }
        
        # Fallback: scan entire page for phone numbers and OTPs
        page_text = driver.find_element(By.TAG_NAME, "body").text
        
        # Find phone numbers
        phone_matches = re.findall(r'\d{10,15}', page_text)
        
        # Find OTPs (formatted like 831-731 or 6 digits)
        otp_matches = re.findall(r'\d{3}-\d{3}|\b\d{6}\b|\b\d{4,5}\b', page_text)
        
        # Filter OTPs
        otp_matches = [otp for otp in otp_matches if not (1900 <= int(otp.replace('-', '')) <= 2100)]
        
        if phone_matches and otp_matches:
            return {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "number": phone_matches[0],
                "message": otp_matches[0],
                "service": site['name']
            }
        
        return None
        
    except Exception as e:
        print(f"[{datetime.now()}] [{site['name']}] Universal scan error: {e}")
        return None


def fetch_latest_sms(driver, site):
    """Fetch latest SMS from site - uses universal scan if enabled"""
    try:
        # Check if site uses universal scanning
        if site.get('universal_scan', False):
            return universal_page_scan(driver, site)
        
        driver.get(site['sms_url'])
        time.sleep(2)
        
        tables = driver.find_elements(By.TAG_NAME, "table")
        
        if not tables:
            # Fallback to universal scan if no tables found
            print(f"[{datetime.now()}] [{site['name']}] No tables found, using universal scan...")
            return universal_page_scan(driver, site)
        
        for table in tables:
            rows = table.find_elements(By.TAG_NAME, "tr")
            
            # Table shows NEWEST first! Row 0 = header, Row 1 = latest SMS
            if len(rows) > 1:
                first_data_row = rows[1]  # Row 1 = NEWEST SMS
                cells = first_data_row.find_elements(By.TAG_NAME, "td")
                
                if len(cells) >= 3:
                    row_data = [cell.text.strip() for cell in cells]
                    
                    # Try to auto-detect columns with phone numbers and SMS
                    phone_col = -1
                    sms_col = -1
                    
                    for i, cell_text in enumerate(row_data):
                        # Detect phone number column
                        if re.match(r'^\+?\d{8,15}$', cell_text.replace(' ', '').replace('-', '')):
                            phone_col = i
                        # Detect SMS column (usually longest text or has keywords)
                        if any(kw in cell_text.lower() for kw in ['otp', 'code', 'verify', 'password']):
                            sms_col = i
                        # Or just find the longest text cell
                        if sms_col == -1 and len(cell_text) > 20:
                            sms_col = i
                    
                    # Fallback to default positions if not detected
                    if phone_col == -1:
                        phone_col = 2 if len(row_data) > 2 else 0
                    if sms_col == -1:
                        sms_col = 4 if len(row_data) > 4 else (len(row_data) - 1)
                    
                    sms_data = {
                        "time": row_data[0] if len(row_data) > 0 else "N/A",
                        "number": row_data[phone_col] if len(row_data) > phone_col else "N/A",
                        "message": row_data[sms_col] if len(row_data) > sms_col else "N/A",
                        "service": site['name']
                    }
                    
                    return sms_data
        
        return None
        
    except Exception as e:
        print(f"[{datetime.now()}] [{site['name']}] Error fetching SMS: {e}")
        return None


def extract_otp(msg):
    """Extract OTP from message - returns full SMS if no OTP pattern found"""
    if not msg or msg == "N/A":
        return "No OTP"
    
    # Try to find OTP patterns
    for pattern in [r"\d{3}-\d{3}", r"\d{6}", r"\d{5}", r"\d{4}"]:
        m = re.search(pattern, msg)
        if m: 
            return m.group(0)
    
    # If no OTP found, return first 20 chars of message
    if len(msg) > 20:
        return msg[:20] + "..."
    return msg if msg else "No OTP"


def mask(num):
    num = "+" + num if not num.startswith("+") else num
    if len(num) >= 8:
        return num[:3] + "****" + num[-6:]
    return num


def get_country(num):
    try:
        num = "+"+num if not num.startswith("+") else num
        parsed = phonenumbers.parse(num)
        country = geocoder.description_for_number(parsed, "en")
        region = phonenumbers.region_code_for_number(parsed)

        if region:
            flag = chr(127462 + ord(region[0]) - 65) + chr(127462 + ord(region[1]) - 65)
        else:
            flag = "🌍"

        return country or "Unknown", flag
    except:
        return "Unknown", "🌍"


def format_msg(data):
    otp = extract_otp(data["message"])
    country, flag = get_country(data["number"])
    masked = mask(data["number"])

    return f"""🖤 <b>New  Received</b>
{flag} #{country.replace(" ", "")} {masked}

⚡ Powered By Ghost 👻""", otp


async def send_otp(data):
    """Send OTP using direct requests API (more reliable on slow networks)"""
    import requests as req
    
    msg, otp = format_msg(data)
    
    # Show OTP in button - if OTP found show it, else show "View SMS"
    clean_otp = otp.replace("-", "") if otp and otp != "No OTP" else "View SMS"
    button_text = f"📋 {clean_otp}" if clean_otp != "View SMS" else "📋 View SMS"
    
    # Build inline keyboard for Telegram API
    keyboard = {
        "inline_keyboard": [
            [{"text": button_text, "callback_data": "noop"}],
            [{"text": "📢 Channel", "url": "https://t.me/Moon2Eye"},
             {"text": "🔢 Num channel", "url": "https://t.me/+wMG41m7Jfxk5MzYx"}]
        ]
    }
    
    chat_ids = load_chat_ids()
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    for chat_id in chat_ids:
        try:
            # Use requests with timeout - works better on throttled networks
            response = req.post(
                api_url,
                json={
                    "chat_id": chat_id,
                    "text": msg,
                    "parse_mode": "HTML",
                    "reply_markup": keyboard
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    print(f"[{datetime.now()}] [OK] SENT OTP -> {data['number']} to chat {chat_id}")
                    # Schedule delete after 2 minutes (run in background)
                    msg_id = result.get("result", {}).get("message_id")
                    if msg_id:
                        asyncio.create_task(delete_msg_later(chat_id, msg_id))
                else:
                    print(f"[{datetime.now()}] [ERROR] API error: {result}")
            else:
                print(f"[{datetime.now()}] [ERROR] HTTP {response.status_code}: {response.text[:100]}")
        except req.exceptions.Timeout:
            print(f"[{datetime.now()}] [ERROR] Timeout sending to {chat_id}")
        except Exception as e:
            print(f"[{datetime.now()}] [ERROR] Error sending to {chat_id}: {e}")


async def delete_msg_later(chat_id, msg_id):
    """Delete message after 2 minutes"""
    import requests as req
    await asyncio.sleep(AUTO_DELETE_SECONDS)
    try:
        api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
        req.post(api_url, json={"chat_id": chat_id, "message_id": msg_id}, timeout=10)
    except:
        pass


async def monitor_site(site, admin_chat_id=None):
    """Monitor a single site"""
    driver = None
    site_id = site['id']
    
    try:
        print(f"\n[{datetime.now()}] [{site['name']}] Starting monitor...")
        
        driver = setup_driver()
        
        # Use progress version if admin_chat_id provided
        if admin_chat_id:
            success = await login_to_site_with_progress(driver, site, admin_chat_id)
        else:
            success = login_to_site(driver, site)
        
        if not success:
            print(f"[{datetime.now()}] [{site['name']}] Login failed, stopping monitor")
            return
        
        print(f"[{datetime.now()}] [{site['name']}] Monitoring started\n")
        
        while True:
            try:
                sms = fetch_latest_sms(driver, site)
                
                if sms:
                    sms_id = f"{sms['number']}_{sms['message'][:20]}"
                    
                    if site_id not in last_sms_data or last_sms_data[site_id] != sms_id:
                        last_sms_data[site_id] = sms_id
                        await send_otp(sms)
                
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"[{datetime.now()}] [{site['name']}] Error in loop: {e}")
                # Try to re-login
                try:
                    driver.quit()
                    driver = setup_driver()
                    login_to_site(driver, site)
                except:
                    pass
                await asyncio.sleep(10)
                
    except Exception as e:
        print(f"[{datetime.now()}] [{site['name']}] Monitor error: {e}")
    finally:
        if driver:
            driver.quit()


# ========== ACCESS DENIED RESPONSE ==========

async def access_denied(update: Update):
    """Send access denied message"""
    user_id = update.message.from_user.id
    await update.message.reply_text(
        f"🚫 <b>Access Denied!</b>\n\n"
        f"❌ You are not authorized to use this bot.\n"
        f"📞 Contact Developer: {DEV_CONTACT}\n\n"
        f"🆔 Your ID: <code>{user_id}</code>",
        parse_mode="HTML"
    )


# ========== TELEGRAM COMMANDS ==========

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    await send_auto_delete(update,
        "🔐 <b>Welcome Admin!</b>\n\n"
        "Available commands:\n"
        "👤 <b>Admin:</b>\n"
        "/add_admin [user_id]\n"
        "/remove_admin [user_id]\n"
        "/list_admins\n\n"
        "💬 <b>Chats:</b>\n"
        "/chats - List all chats\n"
        "/add_chat [chat_id]\n"
        "/remove_chat [chat_id]\n\n"
        "🌐 <b>Sites (Max 50):</b>\n"
        "/addsite - Add new site\n"
        "/listsites - List all sites\n"
        "/removesite [id] - Remove site\n\n"
        "🔑 <b>Access Codes:</b>\n"
        "/create_code - Create access code\n"
        "/list_codes - List all codes\n"
        "/revoke_code [code] - Revoke code\n\n"
        "📊 /status - Bot status\n"
        "❓ /help - Full help\n\n"
        "⏰ <i>Messages auto-delete in 2 minutes</i>",
        parse_mode="HTML"
    )


async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    try:
        new_admin_id = int(context.args[0])
        admin_ids = load_admin_ids()
        
        if new_admin_id in admin_ids:
            await send_auto_delete(update, f"⚠️ Admin ID <code>{new_admin_id}</code> already exists.")
        else:
            admin_ids.append(new_admin_id)
            save_admin_ids(admin_ids)
            await send_auto_delete(update, f"✅ Admin ID <code>{new_admin_id}</code> added!")
    except (IndexError, ValueError):
        await send_auto_delete(update, "❌ Invalid format. Use: /add_admin <user_id>")


async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    try:
        remove_id = int(context.args[0])
        admin_ids = load_admin_ids()
        
        if remove_id not in admin_ids:
            await send_auto_delete(update, f"⚠️ Admin ID <code>{remove_id}</code> not found.")
        elif remove_id == user_id:
            await send_auto_delete(update, "❌ You cannot remove yourself!")
        else:
            admin_ids.remove(remove_id)
            save_admin_ids(admin_ids)
            await send_auto_delete(update, f"✅ Admin ID <code>{remove_id}</code> removed!")
    except (IndexError, ValueError):
        await send_auto_delete(update, "❌ Invalid format. Use: /remove_admin <user_id>")


async def list_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    admin_ids = load_admin_ids()
    if admin_ids:
        admin_list = "\n".join([f"• <code>{aid}</code>" for aid in admin_ids])
        await send_auto_delete(update, f"👥 <b>Admin IDs:</b>\n{admin_list}")
    else:
        await send_auto_delete(update, "⚠️ No admins registered.")


async def chats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all chats - new /chats command"""
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    chat_ids = load_chat_ids()
    if chat_ids:
        chat_list = "\n".join([f"• <code>{cid}</code>" for cid in chat_ids])
        await send_auto_delete(update, f"💬 <b>Chat IDs ({len(chat_ids)}):</b>\n{chat_list}")
    else:
        await send_auto_delete(update, "⚠️ No chats registered.\n\nUse /add_chat [chat_id] to add one.")


async def add_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    try:
        new_chat_id = int(context.args[0])
        chat_ids = load_chat_ids()
        
        if new_chat_id in chat_ids:
            await send_auto_delete(update, f"⚠️ Chat ID <code>{new_chat_id}</code> already exists.")
        else:
            chat_ids.append(new_chat_id)
            save_chat_ids(chat_ids)
            await send_auto_delete(update, f"✅ Chat ID <code>{new_chat_id}</code> added!")
    except (IndexError, ValueError):
        await send_auto_delete(update, "❌ Invalid format. Use: /add_chat <chat_id>")


async def remove_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    try:
        remove_id = int(context.args[0])
        chat_ids = load_chat_ids()
        
        if remove_id not in chat_ids:
            await send_auto_delete(update, f"⚠️ Chat ID <code>{remove_id}</code> not found.")
        else:
            chat_ids.remove(remove_id)
            save_chat_ids(chat_ids)
            await send_auto_delete(update, f"✅ Chat ID <code>{remove_id}</code> removed!")
    except (IndexError, ValueError):
        await send_auto_delete(update, "❌ Invalid format. Use: /remove_chat <chat_id>")


async def list_chats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias for /chats"""
    await chats_command(update, context)


# ========== ACCESS CODE MANAGEMENT ==========

async def create_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    await send_auto_delete(update, 
        "🔑 <b>Create Access Code</b>\n\n"
        "Enter the access code you want to create:\n"
        "(Example: ABC123, PREMIUM2024, etc.)"
    )
    return ACCESS_CODE_CREATE


async def access_code_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    context.user_data['new_code'] = code
    
    codes = load_access_codes()
    if code in codes:
        await send_auto_delete(update, f"⚠️ Code <code>{code}</code> already exists!\n\nTry another code or /cancel")
        return ACCESS_CODE_CREATE
    
    await send_auto_delete(update,
        f"✅ Code: <code>{code}</code>\n\n"
        "Now select access level:\n"
        "1️⃣ <b>full</b> - Full access to all features\n"
        "2️⃣ <b>limited</b> - View only, no modifications\n\n"
        "Send: full or limited"
    )
    return ACCESS_CODE_LEVEL


async def access_level_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    level = update.message.text.strip().lower()
    
    if level not in ['full', 'limited']:
        await send_auto_delete(update, "❌ Invalid level. Send 'full' or 'limited'")
        return ACCESS_CODE_LEVEL
    
    code = context.user_data.get('new_code')
    codes = load_access_codes()
    
    codes[code] = {
        "access_level": level,
        "created_by": update.message.from_user.id,
        "created_at": datetime.now().isoformat(),
        "used_by": None
    }
    
    save_access_codes(codes)
    
    await send_auto_delete(update,
        f"✅ <b>Access Code Created!</b>\n\n"
        f"🔑 Code: <code>{code}</code>\n"
        f"📊 Level: <b>{level}</b>\n"
        f"📅 Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        "Share this code with the user."
    )
    
    return ConversationHandler.END


async def list_codes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    codes = load_access_codes()
    if codes:
        code_list = []
        for code, info in codes.items():
            status = "✅ Available" if info.get('used_by') is None else f"🔴 Used by {info.get('used_by')}"
            code_list.append(f"• <code>{code}</code> [{info.get('access_level')}] - {status}")
        
        await send_auto_delete(update, f"🔑 <b>Access Codes ({len(codes)}):</b>\n" + "\n".join(code_list))
    else:
        await send_auto_delete(update, "⚠️ No access codes created.\n\nUse /create_code to create one.")


async def revoke_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    try:
        code = context.args[0].upper()
        codes = load_access_codes()
        
        if code not in codes:
            await send_auto_delete(update, f"⚠️ Code <code>{code}</code> not found.")
        else:
            del codes[code]
            save_access_codes(codes)
            await send_auto_delete(update, f"✅ Code <code>{code}</code> revoked!")
    except IndexError:
        await send_auto_delete(update, "❌ Invalid format. Use: /revoke_code <code>")


async def cancel_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_auto_delete(update, "❌ Code creation cancelled.")
    return ConversationHandler.END


# ========== SITE MANAGEMENT ==========

async def addsite_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return ConversationHandler.END
    
    sites = load_sites()
    if len(sites) >= 50:
        await send_auto_delete(update, "❌ Maximum 50 sites allowed! Remove some sites first.")
        return ConversationHandler.END
    
    await send_auto_delete(update, f"🌐 Let's add a new site! ({len(sites)}/50)\n\nPlease enter site name:")
    return SITE_NAME


async def site_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['site_name'] = update.message.text
    # Delete user message
    asyncio.create_task(auto_delete_message(update.message))
    await send_auto_delete(update, "✅ Site name saved!\n\nNow enter the LOGIN URL:")
    return SITE_LOGIN_URL


async def site_login_url_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['login_url'] = update.message.text
    asyncio.create_task(auto_delete_message(update.message))
    await send_auto_delete(update, "✅ Login URL saved!\n\nNow enter USERNAME:")
    return SITE_USERNAME


async def site_username_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['username'] = update.message.text
    asyncio.create_task(auto_delete_message(update.message))
    await send_auto_delete(update, "✅ Username saved!\n\nNow enter PASSWORD:")
    return SITE_PASSWORD


async def site_password_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['password'] = update.message.text
    asyncio.create_task(auto_delete_message(update.message))
    await send_auto_delete(update, "✅ Password saved!\n\nNow enter SMS STATS URL:")
    return SITE_SMS_URL


async def site_sms_url_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['sms_url'] = update.message.text
    asyncio.create_task(auto_delete_message(update.message))
    
    # Create new site
    sites = load_sites()
    new_id = max([s['id'] for s in sites], default=0) + 1
    
    new_site = {
        "id": new_id,
        "name": context.user_data['site_name'],
        "login_url": context.user_data['login_url'],
        "username": context.user_data['username'],
        "password": context.user_data['password'],
        "sms_url": context.user_data['sms_url']
    }
    
    sites.append(new_site)
    save_sites(sites)
    
    # Start monitoring this site with progress
    admin_chat_id = update.message.chat_id
    asyncio.create_task(monitor_site(new_site, admin_chat_id))
    site_monitors[new_id] = True
    
    await send_auto_delete(update,
        f"✅ <b>Site added successfully!</b>\n\n"
        f"ID: {new_id}\n"
        f"Name: {new_site['name']}\n"
        f"Login URL: {new_site['login_url']}\n"
        f"Username: {new_site['username']}\n"
        f"SMS URL: {new_site['sms_url']}\n\n"
        f"🔄 Starting monitor with progress bar..."
    )
    
    return ConversationHandler.END


async def cancel_addsite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_auto_delete(update, "❌ Site addition cancelled.")
    return ConversationHandler.END


async def listsites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    sites = load_sites()
    if sites:
        site_list = "\n\n".join([
            f"🌐 <b>Site ID: {s['id']}</b>\n"
            f"Name: {s['name']}\n"
            f"Login: {s['login_url']}\n"
            f"User: {s['username']}\n"
            f"Status: {'✅ Active' if s['id'] in site_monitors else '⏸️ Stopped'}"
            for s in sites
        ])
        await send_auto_delete(update, f"🌐 <b>All Sites ({len(sites)}/50):</b>\n\n{site_list}")
    else:
        await send_auto_delete(update, "⚠️ No sites configured.\n\nUse /addsite to add one.")


async def removesite_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    try:
        site_id = int(context.args[0])
        sites = load_sites()
        
        site_found = None
        for s in sites:
            if s['id'] == site_id:
                site_found = s
                break
        
        if site_found:
            sites.remove(site_found)
            save_sites(sites)
            
            # Stop monitoring
            if site_id in site_monitors:
                del site_monitors[site_id]
            
            await send_auto_delete(update, f"✅ Site '{site_found['name']}' removed!")
        else:
            await send_auto_delete(update, f"⚠️ Site ID {site_id} not found.")
    except (IndexError, ValueError):
        await send_auto_delete(update, "❌ Invalid format. Use: /removesite <site_id>")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    help_text = """📚 <b>Multi-Site SMS Bot Commands</b>

<b>🆔 General:</b>
/start - Start the bot
/help - Show this help
/status - Bot status

<b>👤 Admin Management:</b>
/add_admin [user_id] - Add new admin
/remove_admin [user_id] - Remove admin
/list_admins - List all admins

<b>💬 Chat Management:</b>
/chats - List all chats  
/add_chat [chat_id] - Add chat for OTP
/remove_chat [chat_id] - Remove chat
/list_chats - Alias for /chats

<b>🌐 Site Management (Max 50):</b>
/addsite - Add new site (interactive)
/listsites - List all sites
/removesite [site_id] - Remove a site

<b>🔑 Access Codes:</b>
/create_code - Create new access code
/list_codes - List all codes
/revoke_code [code] - Revoke a code

<b>📊 Status:</b>
/status - Detailed bot status

<b>📢 Broadcast:</b>
/broadcast [message] - Send to all chats

<b>⏰ Auto-Delete:</b>
All messages auto-delete in 2 minutes!

<b>📞 Developer:</b> """ + DEV_CONTACT
    
    await send_auto_delete(update, help_text)



async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    admin_ids = load_admin_ids()
    chat_ids = load_chat_ids()
    sites = load_sites()
    codes = load_access_codes()
    
    await send_auto_delete(update,
        f"📊 <b>Bot Status</b>\n\n"
        f"👥 Admins: {len(admin_ids)}\n"
        f"💬 Chats: {len(chat_ids)}\n"
        f"🌐 Sites: {len(sites)}/50\n"
        f"🔑 Access Codes: {len(codes)}\n"
        f"✅ Active Monitors: {len(site_monitors)}\n\n"
        f"⏰ Auto-Delete: {AUTO_DELETE_SECONDS}s\n"
        f"📞 Dev Contact: {DEV_CONTACT}\n\n"
        f"✅ Bot is running!"
    )


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcast message to all chats"""
    user_id = update.message.from_user.id
    
    if not is_admin(user_id):
        await access_denied(update)
        return
    
    if not context.args:
        await send_auto_delete(update, "❌ Usage: /broadcast <message>")
        return
    
    message = " ".join(context.args)
    chat_ids = load_chat_ids()
    
    if not chat_ids:
        await send_auto_delete(update, "⚠️ No chats registered!")
        return
    
    success = 0
    failed = 0
    
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, f"📢 <b>Broadcast</b>\n\n{message}", parse_mode="HTML")
            success += 1
        except:
            failed += 1
    
    await send_auto_delete(update, f"✅ Broadcast sent!\n\n📤 Success: {success}\n❌ Failed: {failed}")


async def start_all_monitors():
    """Start monitoring all configured sites and notify admins"""
    sites = load_sites()
    chat_ids = load_chat_ids()
    
    if not sites:
        print("[*] No sites configured")
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id, "⚠️ No sites configured.\nUse /addsite", parse_mode="HTML")
            except:
                pass
        return
    
    # Send simple logging message
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, f"🔄 <b>Logging...</b>\n\n📊 Sites: {len(sites)}", parse_mode="HTML")
        except:
            pass
    
    # Start all monitors
    for site in sites:
        if site['id'] not in site_monitors:
            asyncio.create_task(monitor_site(site))
            site_monitors[site['id']] = True
            print(f"[*] Started monitor for: {site['name']}")
    
    # Wait a bit for logins to complete
    await asyncio.sleep(3)
    
    # Send success message
    for chat_id in chat_ids:
        try:
            await bot.send_message(chat_id, f"✅ <b>Success!</b>\n\n🎯 Fetching Started\n📊 {len(sites)} Sites Active", parse_mode="HTML")
        except:
            pass


async def main():
    print("\n[*] Multi-Site SMS Bot Starting...")
    print(f"[*] Admins: {len(load_admin_ids())}")
    print(f"[*] Chats: {len(load_chat_ids())}")
    print(f"[*] Sites: {len(load_sites())}")
    print(f"[*] Auto-Delete: {AUTO_DELETE_SECONDS}s\n")
    
    # Create bot application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("add_admin", add_admin_command))
    application.add_handler(CommandHandler("remove_admin", remove_admin_command))
    application.add_handler(CommandHandler("list_admins", list_admins_command))
    application.add_handler(CommandHandler("chats", chats_command))
    application.add_handler(CommandHandler("add_chat", add_chat_command))
    application.add_handler(CommandHandler("remove_chat", remove_chat_command))
    application.add_handler(CommandHandler("list_chats", list_chats_command))
    application.add_handler(CommandHandler("listsites", listsites_command))
    application.add_handler(CommandHandler("removesite", removesite_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("list_codes", list_codes_command))
    application.add_handler(CommandHandler("revoke_code", revoke_code_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Add site conversation handler
    site_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("addsite", addsite_start)],
        states={
            SITE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, site_name_received)],
            SITE_LOGIN_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, site_login_url_received)],
            SITE_USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, site_username_received)],
            SITE_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, site_password_received)],
            SITE_SMS_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, site_sms_url_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_addsite)],
    )
    application.add_handler(site_conv_handler)
    
    # Add access code conversation handler
    code_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("create_code", create_code_command)],
        states={
            ACCESS_CODE_CREATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, access_code_received)],
            ACCESS_CODE_LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, access_level_received)],
        },
        fallbacks=[CommandHandler("cancel", cancel_code)],
    )
    application.add_handler(code_conv_handler)
    
    # Start bot
    print("[*] Bot starting...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Start all site monitors
    await start_all_monitors()
    
    print("[*] All monitors started!\n")
    
    # Keep running
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Bot stopped by user")
    except Exception as e:
        print(f"\n[!] Fatal error: {e}")


