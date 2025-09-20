import asyncio
import os
import json
from pyppeteer import launch
from pyppeteer.errors import TimeoutError
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def format_number(number):
    number = ''.join(filter(str.isdigit, str(number)))
    if number.startswith('55'):
        number = number[2:]
    return number

def try_with_nine(number):
    if len(number) == 11 and number[2] == '9':
        return number[:2] + number[3:]
    elif len(number) == 10 and number[2] != '9':
        return number[:2] + '9' + number[2:]
    return None

async def check_contact_exists(page, number):
    print(f"Verificando número: +55{number}")
    try:
        nova_conversa_button = await page.waitForSelector(
            'button[aria-label="Nova conversa"]', timeout=10000)
        await nova_conversa_button.click()
        await asyncio.sleep(1)

        search_input = await page.waitForSelector(
            'div[contenteditable="true"][role="textbox"][aria-label="Pesquisar nome ou número"]',
            timeout=10000)
        await search_input.click()
        await asyncio.sleep(0.5)

        await page.keyboard.down('Meta')  # Command no Mac, Control no Linux/Windows
        await page.keyboard.press('A')
        await page.keyboard.up('Meta')
        await page.keyboard.press('Backspace')

        full_number = f"55{number}"
        await page.keyboard.type(full_number)
        await asyncio.sleep(3)

        found_contact = False
        correct_number = None
        await asyncio.sleep(2)

        all_spans = await page.querySelectorAll('span[title]')
        for span in all_spans:
            try:
                title_content = await page.evaluate('el => el.getAttribute("title")', span)
                if title_content and '+55' in title_content:
                    correct_number = title_content
                    found_contact = True
                    print(f"✅ Contato encontrado: {correct_number}")
                    break
            except:
                continue

        if not found_contact:
            other_elements = await page.querySelectorAll('div, span')
            for element in other_elements[:20]:
                try:
                    text_content = await page.evaluate('el => el.textContent', element)
                    if text_content and '+55' in text_content and len(text_content) < 50:
                        clean_text = ''.join(filter(str.isdigit, text_content))
                        if len(clean_text) >= 12:
                            correct_number = text_content
                            found_contact = True
                            print(f"✅ Contato encontrado: {correct_number}")
                            break
                except:
                    continue

        if not found_contact:
            print(f"❌ Nenhum contato encontrado para: +55{number}")

        try:
            back_button = await page.querySelector('button[aria-label="Voltar"]')
            if back_button:
                await back_button.click()
            else:
                await page.keyboard.press('Escape')
        except:
            await page.keyboard.press('Escape')

        await asyncio.sleep(1)
        return found_contact, correct_number

    except Exception as e:
        print(f"Erro ao verificar contato: {e}")
        try:
            await page.keyboard.press('Escape')
        except:
            pass
        return False, None

async def main():
    # Configuração Google Sheets via variável de ambiente
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds_dict = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    sheet_name = os.getenv("GOOGLE_SHEET_NAME", "LISTAS")
    worksheet_name = os.getenv("GOOGLE_WORKSHEET_NAME", "LISTA RG - BR TODO")
    sheet = client.open(sheet_name).worksheet(worksheet_name)
    numbers = sheet.col_values(1)[1:]

    headless = os.getenv("HEADLESS", "1") in ("1", "true", "yes")
    user_data_dir = os.getenv("USER_DATA_DIR", "./user_data")
    executable_path = os.getenv("PUPPETEER_EXECUTABLE_PATH", "/usr/bin/chromium")

    browser = await launch(
        executablePath=executable_path,
        headless=headless,
        userDataDir=user_data_dir,
        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
    )

    page = await browser.newPage()
    await page.setUserAgent('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    await page.goto("https://web.whatsapp.com", {'waitUntil': 'networkidle2'})
    print("Aguardando login no WhatsApp Web...")
    await page.waitForSelector('button[aria-label="Nova conversa"]', timeout=180000)
    print("Login concluído!")

    results = []
    found_numbers = []
    batch_size = 5

    try:
        target_sheet = client.open(sheet_name).worksheet("NUMEROS FORMATADOS BOT")
        target_sheet.clear()
        target_sheet.update(values=[['NUMERO_LIMPO']], range_name='A1')
    except:
        spreadsheet = client.open(sheet_name)
        target_sheet = spreadsheet.add_worksheet('NUMEROS FORMATADOS BOT', rows=1000, cols=10)
        target_sheet.update(values=[['NUMERO_LIMPO']], range_name='A1')

    for raw_number in numbers:
        if not raw_number.strip():
            continue

        formatted_number = format_number(raw_number)
        found, correct_number = await check_contact_exists(page, formatted_number)

        if not found:
            alt_number = try_with_nine(formatted_number)
            if alt_number and alt_number != formatted_number:
                found, correct_number = await check_contact_exists(page, alt_number)

        if found:
            clean_number = correct_number.replace('+', '').replace(' ', '').replace('-', '')
            found_numbers.append(clean_number)
            if len(found_numbers) % batch_size == 0:
                start_row = len(found_numbers) - batch_size + 2
                batch_data = [[num] for num in found_numbers[-batch_size:]]
                target_sheet.update(values=batch_data, range_name=f'A{start_row}:A{start_row + batch_size - 1}')

    await browser.close()
    return found_numbers

async def run_bot():
    return await main()
