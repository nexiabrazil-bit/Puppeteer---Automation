import asyncio
from pyppeteer import launch
from pyppeteer.errors import TimeoutError
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def format_number(number):
    """Remove formatações e retorna apenas os dígitos"""
    # Remove todos os caracteres não numéricos
    number = ''.join(filter(str.isdigit, str(number)))
    
    # Remove o código do país se já existir
    if number.startswith('55'):
        number = number[2:]
    
    return number

def try_with_nine(number):
    """Tenta adicionar/remover o 9 para celulares"""
    if len(number) == 11 and number[2] == '9':
        # Remove o 9 (celular com 9 para sem 9)
        return number[:2] + number[3:]
    elif len(number) == 10 and number[2] != '9':
        # Adiciona o 9 (celular sem 9 para com 9)
        return number[:2] + '9' + number[2:]
    return None

async def check_contact_exists(page, number):
    """Verifica se um contato existe usando o campo de pesquisa"""
    print(f"Verificando número: +55{number}")
    
    try:
        # 1. PRIMEIRO: Clica no botão "Nova conversa"
        nova_conversa_button = await page.waitForSelector('button[aria-label="Nova conversa"]', timeout=10000)
        await nova_conversa_button.click()
        await asyncio.sleep(1)
        
        # 2. AGORA: Clica no campo de pesquisa "Pesquisar nome ou número"
        search_input = await page.waitForSelector('div[contenteditable="true"][role="textbox"][aria-label="Pesquisar nome ou número"]', timeout=10000)
        await search_input.click()
        await asyncio.sleep(0.5)
        
        # 3. Limpa o campo de pesquisa
        await page.keyboard.down('Meta')  # Command no Mac (use 'Control' no Windows/Linux)
        await page.keyboard.press('A')
        await page.keyboard.up('Meta')
        await page.keyboard.press('Backspace')
        
        # 4. Digita o número completo com código do país
        full_number = f"55{number}"
        await page.keyboard.type(full_number)
        await asyncio.sleep(3)  # Aguarda os resultados da pesquisa
        
        # 5. Verifica se apareceu algum contato na lista e captura o número CORRETO
        found_contact = False
        correct_number = None  # O número que apareceu no WhatsApp (que é o correto)
        
        # Aguarda um pouco mais para garantir que os resultados carregaram
        await asyncio.sleep(2)
        
        # Procura por qualquer span que contenha um número de telefone
        all_spans = await page.querySelectorAll('span[title]')
        
        for span in all_spans:
            try:
                title_content = await page.evaluate('el => el.getAttribute("title")', span)
                if title_content and '+55' in title_content:
                    correct_number = title_content  # Este é o número correto que apareceu
                    found_contact = True
                    print(f"✅ Contato encontrado: {correct_number}")
                    break
            except:
                continue
        
        # Se não encontrou spans com title, tenta outros elementos
        if not found_contact:
            # Procura por outros elementos que possam conter números
            other_elements = await page.querySelectorAll('div, span')
            
            for element in other_elements[:20]:  # Limita para não verificar muitos elementos
                try:
                    text_content = await page.evaluate('el => el.textContent', element)
                    if text_content and '+55' in text_content and len(text_content) < 50:
                        # Verifica se é um número de telefone válido
                        clean_text = ''.join(filter(str.isdigit, text_content))
                        
                        if len(clean_text) >= 12:  # Pelo menos 12 dígitos (55 + DDD + número)
                            correct_number = text_content  # Este é o número correto
                            found_contact = True
                            print(f"✅ Contato encontrado: {correct_number}")
                            break
                except:
                    continue
        
        if not found_contact:
            print(f"❌ Nenhum contato encontrado para: +55{number}")
        
        return found_contact, correct_number  # Retorna se encontrou E o número correto
        
        # 6. Volta para a tela inicial - clica no botão de voltar ou ESC
        try:
            # Procura pelo botão de voltar (seta para esquerda)
            back_button = await page.querySelector('button[aria-label="Voltar"]')
            if back_button:
                await back_button.click()
            else:
                # Se não encontrar, pressiona Escape
                await page.keyboard.press('Escape')
        except:
            await page.keyboard.press('Escape')
        
        await asyncio.sleep(1)
        return found_contact
        
    except Exception as e:
        print(f"Erro ao verificar contato: {e}")
        # Tenta voltar para tela inicial em caso de erro
        try:
            await page.keyboard.press('Escape')
        except:
            pass
        return False

async def main():
    # Configuração do Google Sheets
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    sheet = client.open('LISTAS').worksheet('LISTA RG - BR TODO')
    
    # Pega os números da planilha
    numbers = sheet.col_values(1)[1:]  # Pula o cabeçalho
    
    # Configuração do browser
    browser = await launch(
        executablePath="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # Ajuste para seu SO
        headless=False,
        userDataDir="./user_data",
        args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
    )
    
    page = await browser.newPage()
    await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Abre o WhatsApp Web
    await page.goto("https://web.whatsapp.com", {'waitUntil': 'networkidle2'})
    print("Aguardando login no WhatsApp Web...")
    
    # Aguarda o login ser concluído - espera pelo botão Nova conversa aparecer
    await page.waitForSelector('button[aria-label="Nova conversa"]', timeout=180000)
    print("Login concluído! Iniciando verificação dos números...")
    await asyncio.sleep(2)  # Aguarda um pouco mais para garantir que tudo carregou
    
    results = []
    found_numbers = []  # Lista para números limpos encontrados
    batch_size = 5  # Salvar a cada 5 números
    
    # Prepara a planilha no início
    try:
        print("🔧 Preparando planilha 'NUMEROS FORMATADOS BOT'...")
        try:
            target_sheet = client.open('LISTAS').worksheet('NUMEROS FORMATADOS BOT')
            print("✅ Planilha encontrada!")
        except:
            # Se não existir, cria uma nova aba
            spreadsheet = client.open('LISTAS')
            target_sheet = spreadsheet.add_worksheet('NUMEROS FORMATADOS BOT', rows=1000, cols=10)
            print("✅ Nova aba criada!")
        
        # Limpa a planilha e adiciona cabeçalho
        target_sheet.clear()
        target_sheet.update(values=[['NUMERO_LIMPO']], range_name='A1')
        print("✅ Planilha preparada!")
        
    except Exception as e:
        print(f"❌ Erro ao preparar planilha: {e}")
        target_sheet = None
    
    for raw_number in numbers:
        if not raw_number.strip():
            continue
            
        print(f"\n--- Processando: {raw_number} ---")
        
        # Formatar o número (remover +55 se existir)
        formatted_number = format_number(raw_number)
        
        # Primeira tentativa com o número original
        print(f"🔍 Tentativa 1: +55{formatted_number}")
        found, correct_number = await check_contact_exists(page, formatted_number)
        
        if found:
            result = f"{raw_number}: TRUE → Número correto: {correct_number}"
            print(f"✅ {result}")
            results.append((raw_number, True, correct_number))
            
            # Adiciona número limpo à lista
            clean_number = correct_number.replace('+', '').replace(' ', '').replace('-', '')
            found_numbers.append(clean_number)
            print(f"📝 Número limpo adicionado: {clean_number} (Total na lista: {len(found_numbers)})")
            
            # Salva a cada 5 números encontrados
            if len(found_numbers) % batch_size == 0 and target_sheet:
                print(f"🎯 Salvando lote de {batch_size} números!")
                try:
                    # Calcula a linha onde inserir (cabeçalho + números já salvos)
                    start_row = len(found_numbers) - batch_size + 2
                    batch_data = [[num] for num in found_numbers[-batch_size:]]
                    
                    # Usa o formato correto com argumentos nomeados
                    range_name = f'A{start_row}:A{start_row + batch_size - 1}'
                    target_sheet.update(values=batch_data, range_name=range_name)
                    print(f"💾 ✅ Lote salvo com sucesso! {len(found_numbers)} números total na planilha")
                    
                except Exception as e:
                    print(f"❌ Erro ao salvar lote: {e}")
                    print(f"🔍 Dados que estavam sendo salvos: {found_numbers[-batch_size:]}")
            else:
                print(f"⏳ Aguardando mais números... ({len(found_numbers)}/{batch_size})")
        else:
            # Segunda tentativa: adicionar/remover o 9
            alt_number = try_with_nine(formatted_number)
            
            if alt_number and alt_number != formatted_number:
                print(f"🔍 Tentativa 2: +55{alt_number}")
                found_alt, correct_number_alt = await check_contact_exists(page, alt_number)
                
                if found_alt:
                    result = f"{raw_number}: TRUE → Número correto: {correct_number_alt}"
                    print(f"✅ {result}")
                    results.append((raw_number, True, correct_number_alt))
                    
                    # Adiciona número limpo à lista
                    clean_number = correct_number_alt.replace('+', '').replace(' ', '').replace('-', '')
                    found_numbers.append(clean_number)
                    print(f"📝 Número limpo adicionado: {clean_number} (Total na lista: {len(found_numbers)})")
                    
                    # Salva a cada 5 números encontrados
                    if len(found_numbers) % batch_size == 0 and target_sheet:
                        print(f"🎯 Salvando lote de {batch_size} números!")
                        try:
                            # Calcula a linha onde inserir
                            start_row = len(found_numbers) - batch_size + 2
                            batch_data = [[num] for num in found_numbers[-batch_size:]]
                            
                            # Usa o formato correto com argumentos nomeados
                            range_name = f'A{start_row}:A{start_row + batch_size - 1}'
                            target_sheet.update(values=batch_data, range_name=range_name)
                            print(f"💾 ✅ Lote salvo com sucesso! {len(found_numbers)} números total na planilha")
                            
                        except Exception as e:
                            print(f"❌ Erro ao salvar lote: {e}")
                            print(f"🔍 Dados que estavam sendo salvos: {found_numbers[-batch_size:]}")
                    else:
                        print(f"⏳ Aguardando mais números... ({len(found_numbers)}/{batch_size})")
                else:
                    result = f"{raw_number}: FALSE → Testados: +55{formatted_number} e +55{alt_number}"
                    print(f"❌ {result}")
                    results.append((raw_number, False, None))
            else:
                result = f"{raw_number}: FALSE → Testado: +55{formatted_number}"
                print(f"❌ {result}")
                results.append((raw_number, False, None))
        
        # Pequena pausa entre verificações para não sobrecarregar
        await asyncio.sleep(2)
    
    # Resumo final
    print("\n" + "="*50)
    print("RESUMO DOS RESULTADOS:")
    print("="*50)
    
    true_count = sum(1 for _, found, _ in results if found)
    false_count = len(results) - true_count
    
    for original, found, used_number in results:
        status = "✅ ENCONTRADO" if found else "❌ NÃO ENCONTRADO"
        used_info = f" → Use: {used_number}" if found and used_number else ""
        print(f"{original}: {status}{used_info}")
    
    print(f"\nTotal: {len(results)} números")
    print(f"Encontrados: {true_count}")
    print(f"Não encontrados: {false_count}")
    
    # Lista apenas os números que foram encontrados com o formato correto
    if true_count > 0:
        print(f"\n📋 NÚMEROS CORRETOS PARA USAR:")
        print("="*50)
        clean_numbers = []  # Lista para números limpos
        
        for original, found, used_number in results:
            if found:
                # Remove espaços, + e hífens do número
                clean_number = used_number.replace('+', '').replace(' ', '').replace('-', '')
                clean_numbers.append(clean_number)
                print(f"Original: {original} → Correto: {used_number} → Limpo: {clean_number}")
        
        # Salva os números limpos na planilha
        try:
            print(f"\n💾 Salvando {len(clean_numbers)} números na planilha 'NUMEROS FORMATADOS BOT'...")
            
            # Tenta abrir a planilha ou criar uma nova
            try:
                target_sheet = client.open('LISTAS').worksheet('NUMEROS FORMATADOS BOT')
                print("✅ Planilha encontrada!")
            except:
                # Se não existir, cria uma nova aba
                spreadsheet = client.open('LISTAS')
                target_sheet = spreadsheet.add_worksheet('NUMEROS FORMATADOS BOT', rows=1000, cols=10)
                print("✅ Nova aba criada!")
            
            # Limpa a planilha antes de adicionar novos dados
            target_sheet.clear()
            
            # Adiciona cabeçalho
            target_sheet.update('A1', 'NUMERO_LIMPO')
            
            # Adiciona os números limpos (um por linha)
            if clean_numbers:
                # Prepara os dados para inserção em batch
                values = [[number] for number in clean_numbers]
                target_sheet.update('A2', values)
                
            print(f"✅ {len(clean_numbers)} números salvos com sucesso na planilha!")
            
        except Exception as e:
            print(f"❌ Erro ao salvar na planilha: {e}")
            print("📝 Números que seriam salvos:")
            for number in clean_numbers:
                print(f"  {number}")
    else:
        print(f"\n❌ Nenhum número válido foi encontrado para salvar na planilha.")
    
    await browser.close()

async def run_bot():
    await main()
