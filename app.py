from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from functools import wraps
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging
import hashlib
import os
from datetime import datetime, timedelta

app = Flask(__name__, template_folder='client/templates', static_folder='client/static')
app.secret_key = 'sistema_escolar_nicola_mastrocola_2025_seguranca'

# Configurar logging
logging.basicConfig(level=logging.DEBUG)

# ====== CONFIGURAÇÕES DE AUTENTICAÇÃO ======
USUARIOS = {
    'diretor': {
        'senha': hashlib.sha256('Nicgestao@25'.encode()).hexdigest(),
        'tipo': 'diretor',
        'nome': 'Diretor',
        'permissoes': ['ver_tudo', 'editar_tudo', 'excluir_tudo', 'gerenciar_usuarios']
    },
    'proatec': {
        'senha': hashlib.sha256('Nicproati@25'.encode()).hexdigest(),
        'tipo': 'proatec',
        'nome': 'Coordenador PROATEC',
        'permissoes': ['ver_tudo', 'editar_registros', 'adicionar_registros']
    },
    'professor': {
        'senha': hashlib.sha256('Nicprof@25'.encode()).hexdigest(),
        'tipo': 'professor',
        'nome': 'Professor',
        'permissoes': ['ver_turmas', 'adicionar_registros', 'ver_registros_proprios']
    }
}

# ====== DECORATORS DE AUTENTICAÇÃO ======
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def diretor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session or session.get('tipo') != 'diretor':
            return jsonify({'success': False, 'error': 'Acesso não autorizado'}), 403
        return f(*args, **kwargs)
    return decorated_function

def proatec_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session or session.get('tipo') not in ['diretor', 'proatec']:
            return jsonify({'success': False, 'error': 'Acesso não autorizado'}), 403
        return f(*args, **kwargs)
    return decorated_function

# ====== ROTAS PRINCIPAIS ======
@app.route('/')
def login_page():
    """Página principal - Login"""
    # Se já estiver logado, redireciona para o dashboard
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Rota de processamento do login"""
    # Se já estiver logado, redireciona para o dashboard
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        
        if not username or not password:
            return render_template('login.html', error='Usuário e senha são obrigatórios')
        
        if username in USUARIOS:
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            if USUARIOS[username]['senha'] == hashed_password:
                session['usuario'] = username
                session['tipo'] = USUARIOS[username]['tipo']
                session['nome'] = USUARIOS[username]['nome']
                session['permissoes'] = USUARIOS[username]['permissoes']
                session['login_time'] = datetime.now().isoformat()
                
                app.logger.info(f"Login bem-sucedido: {username} ({session['tipo']})")
                return redirect(url_for('dashboard'))
        
        return render_template('login.html', error='Usuário ou senha inválidos')
    
    # Se for GET, redireciona para a página principal de login
    return redirect(url_for('login_page'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal após o login (antigo index.html)"""
    try:
        turmas = [ws.title for ws in sheet.worksheets()] if sheet else []
        return render_template('index.html', 
                             turmas=turmas,
                             usuario=session['usuario'],
                             tipo_usuario=session['tipo'],
                             nome_usuario=session['nome'])
    except Exception as e:
        app.logger.error(f"Erro na página inicial: {str(e)}")
        return f"Erro: {str(e)}", 500

@app.route('/logout')
def logout():
    """Logout do sistema"""
    session.clear()
    return redirect(url_for('login_page'))

@app.route('/trocar-senha', methods=['POST'])
@login_required
def trocar_senha():
    try:
        data = request.get_json()
        senha_atual = data.get('senha_atual', '')
        nova_senha = data.get('nova_senha', '')
        confirmar_senha = data.get('confirmar_senha', '')
        
        if not senha_atual or not nova_senha or not confirmar_senha:
            return jsonify({'success': False, 'error': 'Todos os campos são obrigatórios'})
        
        if nova_senha != confirmar_senha:
            return jsonify({'success': False, 'error': 'As senhas não coincidem'})
        
        usuario = session['usuario']
        hashed_senha_atual = hashlib.sha256(senha_atual.encode()).hexdigest()
        
        if USUARIOS[usuario]['senha'] != hashed_senha_atual:
            return jsonify({'success': False, 'error': 'Senha atual incorreta'})
        
        USUARIOS[usuario]['senha'] = hashlib.sha256(nova_senha.encode()).hexdigest()
        
        return jsonify({'success': True, 'message': 'Senha alterada com sucesso!'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ====== CONFIG GOOGLE SHEETS ======
SERVICE_ACCOUNT_FILE = r'C:\Users\guilh\Desktop\Welton\App_Welton\key.json'
SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    creds = ServiceAccountCredentials.from_json_keyfile_name(SERVICE_ACCOUNT_FILE, SCOPE)
    gc = gspread.authorize(creds)
    SPREADSHEET_ID = '1OrwwdI9hUnwbesir-6sz-B7CvA8N1p7mvUJwzzjgBL0'
    sheet = gc.open_by_key(SPREADSHEET_ID)
    app.logger.info("Planilha aberta com sucesso")
except Exception as e:
    app.logger.error(f"Erro ao abrir planilha: {str(e)}")
    sheet = None

# ====== MIDDLEWARE PARA VERIFICAR AUTENTICAÇÃO ======
@app.before_request
def check_authentication():
    # Rotas públicas que não requerem autenticação
    public_routes = ['login_page', 'login', 'static', 'logout']
    
    # Se a rota atual não é pública e o usuário não está logado, redireciona para login
    if request.endpoint not in public_routes and 'usuario' not in session:
        return redirect(url_for('login_page'))

# ====== ROTAS DO SISTEMA (PROTEGIDAS) ======
@app.route('/serie/<turma>')
@login_required
def mostrar_alunos(turma):
    try:
        if not sheet:
            return "Erro de conexão com Google Sheets", 500
            
        turma_norm = turma.upper().strip()
        
        try:
            worksheet = sheet.worksheet(turma_norm)
        except gspread.WorksheetNotFound:
            # Apenas diretor e proatec podem criar novas turmas
            if session['tipo'] not in ['diretor', 'proatec']:
                return "Acesso não autorizado", 403
                
            worksheet = sheet.add_worksheet(title=turma_norm, rows=100, cols=10)
            cabecalhos = ["Chamada", "Nome do Aluno"]
            worksheet.append_row(cabecalhos)
            app.logger.info(f"Nova aba criada: {turma_norm}")
        
        data = worksheet.get_all_values()
        header = data[0] if data else []
        alunos = data[1:] if len(data) > 1 else []
        
        return render_template('students.html', 
                             turma=turma_norm, 
                             header=header, 
                             alunos=alunos,
                             usuario=session['usuario'],
                             tipo_usuario=session['tipo'],
                             nome_usuario=session['nome'])
        
    except Exception as e:
        app.logger.error(f"Erro ao acessar turma {turma}: {str(e)}")
        return f"Erro ao acessar a turma: {str(e)}", 500

@app.route('/adicionar-aluno/<turma>', methods=['POST'])
@login_required
def adicionar_aluno(turma):
    try:
        # Apenas diretor e proatec podem adicionar alunos
        if session['tipo'] not in ['diretor', 'proatec']:
            return jsonify({'success': False, 'error': 'Acesso não autorizado'})
            
        if not sheet:
            return jsonify({'success': False, 'error': 'Erro de conexão com Google Sheets'})
            
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Dados não fornecidos'})
            
        nome = data.get('nome', '').strip()
        ra = data.get('ra', '').strip()
        
        if not nome:
            return jsonify({'success': False, 'error': 'Nome é obrigatório'})
        
        app.logger.info(f"Tentando adicionar aluno: RA={ra}, Nome={nome} na turma {turma}")
        
        worksheet = sheet.worksheet(turma.upper())
        
        # Verificar se o RA já existe
        existing_data = worksheet.get_all_values()
        for row in existing_data[1:]:
            if row and len(row) > 0 and str(row[0]).strip() == ra:
                return jsonify({'success': False, 'error': 'RA já existe'})
        
        worksheet.append_row([ra, nome])
        app.logger.info("Aluno adicionado com sucesso")
        
        return jsonify({'success': True, 'message': 'Aluno adicionado com sucesso!'})
        
    except Exception as e:
        app.logger.error(f"Erro ao adicionar aluno: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/importar-csv/<turma>', methods=['POST'])
@proatec_required
def importar_csv(turma):
    try:
        if not sheet:
            return jsonify({'success': False, 'error': 'Erro de conexão com Google Sheets'})
            
        file = request.files.get('file')
        if not file:
            return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'})
        
        file_content = file.read()
        app.logger.info(f"Tamanho do arquivo: {len(file_content)} bytes")
        
        encodings = ['utf-8', 'latin-1', 'iso-8859-1', 'windows-1252', 'cp1252']
        content_decoded = None
        used_encoding = None
        
        for encoding in encodings:
            try:
                content_decoded = file_content.decode(encoding)
                used_encoding = encoding
                app.logger.info(f"Arquivo decodificado com sucesso usando: {encoding}")
                break
            except UnicodeDecodeError:
                continue
        
        if content_decoded is None:
            try:
                content_decoded = file_content.decode('utf-8', errors='ignore')
                used_encoding = 'utf-8 (com ignore errors)'
            except:
                return jsonify({'success': False, 'error': 'Não foi possível decodificar o arquivo.'})
        
        lines = content_decoded.splitlines()
        app.logger.info(f"Número de linhas no arquivo: {len(lines)}")
        
        delimiters = [',', ';', '\t', '|']
        rows = []
        best_delimiter = ','
        max_columns = 0
        
        for delimiter in delimiters:
            try:
                import csv
                from io import StringIO
                
                temp_rows = []
                csv_reader = csv.reader(StringIO(content_decoded), delimiter=delimiter)
                
                for row in csv_reader:
                    if row and any(cell.strip() for cell in row):
                        temp_rows.append([cell.strip() for cell in row])
                        if len(row) > max_columns:
                            max_columns = len(row)
                            best_delimiter = delimiter
            except:
                continue
        
        import csv
        from io import StringIO
        
        csv_reader = csv.reader(StringIO(content_decoded), delimiter=best_delimiter)
        rows = []
        
        for i, row in enumerate(csv_reader):
            if row and any(cell.strip() for cell in row):
                cleaned_row = [cell.strip() for cell in row]
                rows.append(cleaned_row)
                app.logger.info(f"Linha {i+1} com delimitador '{best_delimiter}': {cleaned_row}")
        
        app.logger.info(f"Delimitador detectado: '{best_delimiter}'")
        app.logger.info(f"Número máximo de colunas: {max_columns}")
        
        if not rows:
            return jsonify({'success': False, 'error': 'O arquivo está vazio ou não contém dados válidos.'})
        
        worksheet = sheet.worksheet(turma.upper())
        
        existing_data = worksheet.get_all_values()
        existing_ras = set()
        
        for existing_row in existing_data[1:]:
            if existing_row and len(existing_row) > 0:
                ra = str(existing_row[0]).strip()
                if ra:
                    existing_ras.add(ra)
        
        app.logger.info(f"RAs existentes na turma: {list(existing_ras)}")
        
        added_count = 0
        new_rows = []
        skipped_rows = []
        
        for i, row in enumerate(rows):
            if not row or not any(cell.strip() for cell in row):
                skipped_rows.append(f"Linha {i+1}: Vazia")
                continue
            
            ra = ""
            nome = ""
            
            if len(row) >= 2:
                ra = str(row[0]).strip()
                nome = str(row[1]).strip()
            elif len(row) == 1:
                nome = str(row[0]).strip()
                if not nome:
                    skipped_rows.append(f"Linha {i+1}: Nome vazio")
                    continue
                
                next_ra = 1
                if existing_ras:
                    numeric_ras = [int(r) for r in existing_ras if r.isdigit()]
                    if numeric_ras:
                        next_ra = max(numeric_ras) + 1
                
                while str(next_ra) in existing_ras:
                    next_ra += 1
                
                ra = str(next_ra)
                app.logger.info(f"RA gerado automaticamente: {ra} para {nome}")
            else:
                skipped_rows.append(f"Linha {i+1}: Formato inválido")
                continue
            
            header_keywords = ['ra', 'chamada', 'numero', 'número', 'codigo', 'código', 'nome', 'aluno', 'student']
            if any(ra.lower() in header_keywords for keyword in header_keywords) or \
               any(nome.lower() in header_keywords for keyword in header_keywords):
                skipped_rows.append(f"Linha {i+1}: Cabeçalho ignorado - RA: '{ra}', Nome: '{nome}'")
                continue
            
            if not nome:
                skipped_rows.append(f"Linha {i+1}: Nome vazio")
                continue
            
            if not ra:
                next_ra = 1
                if existing_ras:
                    numeric_ras = [int(r) for r in existing_ras if r.isdigit()]
                    if numeric_ras:
                        next_ra = max(numeric_ras) + 1
                while str(next_ra) in existing_ras:
                    next_ra += 1
                ra = str(next_ra)
            
            if ra in existing_ras:
                skipped_rows.append(f"Linha {i+1}: RA {ra} já existe")
                continue
            
            new_rows.append([ra, nome])
            existing_ras.add(ra)
            added_count += 1
            app.logger.info(f"Novo aluno adicionado: {ra} - {nome}")
        
        if new_rows:
            worksheet.append_rows(new_rows)
            app.logger.info(f"Total de {len(new_rows)} alunos adicionados à planilha")
        
        message = f'{added_count} alunos importados com sucesso!'
        if skipped_rows:
            message += f'\n\nDetalhes:'
            message += f'\n• Delimitador detectado: "{best_delimiter}"'
            message += f'\n• Codificação: {used_encoding}'
            message += f'\n• Linhas processadas: {len(rows)}'
            message += f'\n• Linhas adicionadas: {added_count}'
            message += f'\n• Linhas ignoradas: {len(skipped_rows)}'
            
            if len(skipped_rows) <= 10:
                message += f'\n\nLinhas ignoradas:'
                for skip in skipped_rows:
                    message += f'\n• {skip}'
        
        return jsonify({
            'success': True, 
            'message': message,
            'details': {
                'encoding': used_encoding,
                'delimiter': best_delimiter,
                'processed': len(rows),
                'added': added_count,
                'skipped': len(skipped_rows)
            }
        })
        
    except Exception as e:
        app.logger.error(f"Erro ao importar CSV: {str(e)}")
        import traceback
        app.logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': f'Erro na importação: {str(e)}'})

@app.route('/aluno/<turma>/<int:chamada>')
@login_required
def detalhes_aluno(turma, chamada):
    try:
        if not sheet:
            return "Erro de conexão com Google Sheets", 500
            
        turma_norm = turma.upper().strip()
        worksheet = sheet.worksheet(turma_norm)
        
        data = worksheet.get_all_values()
        header = data[0] if data else []
        aluno_encontrado = None
        
        for i, row in enumerate(data[1:], start=2):
            if len(row) >= 2 and str(row[0]).strip() == str(chamada):
                aluno_encontrado = {
                    'Chamada': row[0] if len(row) > 0 else '',
                    'Nome': row[1] if len(row) > 1 else '',
                    'linha': i,
                    'turma': turma_norm
                }
                break
        
        if not aluno_encontrado:
            return f"Aluno com chamada {chamada} não encontrado na turma {turma_norm}", 404
        
        registros = []
        header_registros = ['Data', 'Tipo', 'Descrição', 'Professor']
        
        try:
            worksheet_registros = sheet.worksheet('Registros')
            todos_registros = worksheet_registros.get_all_values()
            
            if len(todos_registros) > 1:
                for registro in todos_registros[1:]:
                    if (len(registro) >= 6 and 
                        registro[1] == turma_norm and 
                        str(registro[2]).strip() == str(chamada)):
                        registros.append([registro[0], registro[3], registro[4], registro[5]])
        except gspread.WorksheetNotFound:
            app.logger.info("Aba Registros não encontrada")
        
        return render_template('aluno_detalhes.html', 
                             aluno=aluno_encontrado, 
                             turma=turma_norm,
                             registros=registros,
                             header=header_registros,
                             usuario=session['usuario'],
                             tipo_usuario=session['tipo'],
                             nome_usuario=session['nome'])
        
    except Exception as e:
        app.logger.error(f"Erro ao buscar aluno: {str(e)}")
        return f"Erro ao buscar aluno: {str(e)}", 500

@app.route('/adicionar-registro/<turma>/<int:chamada>', methods=['POST'])
@login_required
def adicionar_registro(turma, chamada):
    try:
        if not sheet:
            return jsonify({'success': False, 'error': 'Erro de conexão com Google Sheets'})
            
        data = request.get_json()
        tipo = data.get('tipo', '').strip()
        descricao = data.get('descricao', '').strip()
        professor = data.get('professor', '').strip()
        
        # Professor só pode adicionar elogios e observações
        if session['tipo'] == 'professor' and tipo in ['Advertência', 'Ocorrência']:
            return jsonify({'success': False, 'error': 'Professores só podem adicionar elogios e observações'})
        
        if not tipo or not descricao:
            return jsonify({'success': False, 'error': 'Tipo e descrição são obrigatórios'})
        
        try:
            worksheet_registros = sheet.worksheet('Registros')
        except gspread.WorksheetNotFound:
            # Apenas diretor e proatec podem criar a aba de registros
            if session['tipo'] not in ['diretor', 'proatec']:
                return jsonify({'success': False, 'error': 'Acesso não autorizado para criar registros'})
                
            worksheet_registros = sheet.add_worksheet(title='Registros', rows=1000, cols=10)
            cabecalhos = ["Data", "Turma", "Chamada", "Tipo", "Descrição", "Professor", "Registrado Por"]
            worksheet_registros.append_row(cabecalhos)
            app.logger.info("Aba Registros criada com sucesso")
        
        from datetime import datetime
        data_hora = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        novo_registro = [data_hora, turma.upper(), chamada, tipo, descricao, professor, session['nome']]
        worksheet_registros.append_row(novo_registro)
        
        return jsonify({'success': True, 'message': 'Registro adicionado com sucesso!'})
        
    except Exception as e:
        app.logger.error(f"Erro ao adicionar registro: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/editar-aluno/<turma>', methods=['POST'])
@login_required
def editar_aluno(turma):
    try:
        # Apenas diretor e proatec podem editar alunos
        if session['tipo'] not in ['diretor', 'proatec']:
            return jsonify({'success': False, 'error': 'Acesso não autorizado'})
            
        if not sheet:
            return jsonify({'success': False, 'error': 'Erro de conexão com Google Sheets'})
            
        data = request.get_json()
        linha = data.get('linha')
        novo_nome = data.get('novo_nome', '').strip()
        novo_ra = data.get('novo_ra', '').strip()
        
        if not linha or not novo_nome:
            return jsonify({'success': False, 'error': 'Dados incompletos'})
        
        worksheet = sheet.worksheet(turma.upper())
        
        worksheet.update(f'A{linha}', [[novo_ra, novo_nome]])
        
        return jsonify({'success': True, 'message': 'Aluno atualizado com sucesso!'})
        
    except Exception as e:
        app.logger.error(f"Erro ao editar aluno: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/excluir-aluno/<turma>', methods=['POST'])
@login_required
def excluir_aluno(turma):
    try:
        # Apenas diretor e proatec podem excluir alunos
        if session['tipo'] not in ['diretor', 'proatec']:
            return jsonify({'success': False, 'error': 'Acesso não autorizado'})
            
        if not sheet:
            return jsonify({'success': False, 'error': 'Erro de conexão com Google Sheets'})
            
        data = request.get_json()
        linha = data.get('linha')
        
        if not linha:
            return jsonify({'success': False, 'error': 'Linha não especificada'})
        
        try:
            linha_int = int(linha)
        except ValueError:
            return jsonify({'success': False, 'error': 'Número de linha inválido'})
        
        worksheet = sheet.worksheet(turma.upper())
        
        worksheet.delete_rows(linha_int)
        
        return jsonify({'success': True, 'message': 'Aluno excluído com sucesso!'})
        
    except Exception as e:
        app.logger.error(f"Erro ao excluir aluno: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
    
@app.route('/excluir-registro/<turma>/<int:index>', methods=['DELETE'])
@proatec_required
def excluir_registro(turma, index):
    try:
        worksheet_registros = sheet.worksheet('Registros')
        registros = worksheet_registros.get_all_values()
        
        linha_para_excluir = index + 2
        
        if linha_para_excluir <= len(registros):
            worksheet_registros.delete_rows(linha_para_excluir)
            return jsonify({'success': True, 'message': 'Registro excluído!'})
        else:
            return jsonify({'success': False, 'error': 'Registro não encontrado'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    

@app.route('/api/advertencias-por-turma/<serie>')
@app.route('/api/advertencias-por-turma/<serie>/<tipo>')
@login_required
def advertencias_por_turma(serie, tipo=None):
    try:
        if not sheet:
            return jsonify({'error': 'Erro de conexão com Google Sheets'}), 500
        
        try:
            worksheet_registros = sheet.worksheet('Registros')
            registros = worksheet_registros.get_all_values()
        except gspread.WorksheetNotFound:
            return jsonify({'turmas': [], 'advertencias': [], 'tipos_disponiveis': []})
        
        turmas_da_serie = []
        if serie == '6':
            turmas_da_serie = ['6A', '6B', '6C', '6D']
        elif serie == '7':
            turmas_da_serie = ['7A', '7B', '7C', '7D']
        elif serie == '8':
            turmas_da_serie = ['8A', '8B', '8C', '8D']
        elif serie == '9':
            turmas_da_serie = ['9A', '9B', '9C', '9D']
        elif serie == '1':
            turmas_da_serie = ['1A', '1B', '1C', '1D']
        elif serie == '2':
            turmas_da_serie = ['2A', '2B', '2C', '2D']
        elif serie == '3':
            turmas_da_serie = ['3A', '3B', '3C', '3D']
        
        tipos_disponiveis = set()
        contador_advertencias = {turma: 0 for turma in turmas_da_serie}
        
        if len(registros) > 1:
            for registro in registros[1:]:
                if len(registro) >= 4:
                    turma = registro[1].strip().upper()
                    tipo_registro = registro[3].strip().lower()
                    
                    if tipo_registro:
                        tipos_disponiveis.add(tipo_registro.title())
                    
                    if turma in contador_advertencias:
                        if tipo is None or tipo == 'todos':
                            contador_advertencias[turma] += 1
                        else:
                            if tipo_registro.lower() == tipo.lower():
                                contador_advertencias[turma] += 1
        
        turmas = list(contador_advertencias.keys())
        advertencias = list(contador_advertencias.values())
        
        return jsonify({
            'turmas': turmas,
            'advertencias': advertencias,
            'tipos_disponiveis': sorted(list(tipos_disponiveis)),
            'tipo_selecionado': tipo if tipo else 'todos'
        })
        
    except Exception as e:
        app.logger.error(f"Erro ao buscar dados para gráfico: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/baixar-planilha-serie/<serie>')
@login_required
def baixar_planilha_serie(serie):
    try:
        if not sheet:
            return jsonify({'error': 'Erro de conexão com Google Sheets'}), 500
        
        if serie == '6':
            turmas = ['6A', '6B', '6C', '6D']
        elif serie == '7':
            turmas = ['7A', '7B', '7C', '7D']
        elif serie == '8':
            turmas = ['8A', '8B', '8C', '8D']
        elif serie == '9':
            turmas = ['9A', '9B', '9C', '9D']
        elif serie == '1':
            turmas = ['1A', '1B', '1C', '1D']
        elif serie == '2':
            turmas = ['2A', '2B', '2C', '2D']
        elif serie == '3':
            turmas = ['3A', '3B', '3C', '3D']
        else:
            return jsonify({'error': 'Série não encontrada'}), 404
        
        planilha_url = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}"
        
        return jsonify({
            'success': True,
            'message': f'Planilha da série {serie} disponível no Google Sheets',
            'url': planilha_url
        })
        
    except Exception as e:
        app.logger.error(f"Erro ao gerar planilha: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/pesquisar-aluno/<nome>')
@login_required
def pesquisar_aluno(nome):
    try:
        if not sheet:
            return jsonify({'success': False, 'error': 'Erro de conexão com Google Sheets'})
        
        resultados = []
        nome_pesquisa = nome.lower().strip()
        
        todas_turmas = []
        series = ['6', '7', '8', '9', '1', '2', '3']
        turmas = ['A', 'B', 'C', 'D']
        
        for serie in series:
            for turma in turmas:
                todas_turmas.append(f"{serie}{turma}")
        
        app.logger.info(f"Pesquisando aluno: {nome_pesquisa}")
        app.logger.info(f"Turmas a verificar: {todas_turmas}")
        
        for turma in todas_turmas:
            try:
                worksheet = sheet.worksheet(turma)
                dados = worksheet.get_all_values()
                app.logger.info(f"Verificando turma {turma} - {len(dados)} linhas")
                
                for i, linha in enumerate(dados[1:], start=2):
                    if len(linha) >= 2:
                        ra_aluno = str(linha[0]).strip()
                        nome_aluno = str(linha[1]).strip()
                        
                        if nome_pesquisa in nome_aluno.lower():
                            resultados.append({
                                'ra': ra_aluno,
                                'nome': nome_aluno,
                                'turma': turma,
                                'linha': i
                            })
                            app.logger.info(f"Aluno encontrado: {nome_aluno} na turma {turma}")
                            
            except gspread.WorksheetNotFound:
                app.logger.info(f"Turma {turma} não encontrada, pulando...")
                continue
            except Exception as e:
                app.logger.error(f"Erro ao acessar turma {turma}: {str(e)}")
                continue
        
        app.logger.info(f"Total de resultados encontrados: {len(resultados)}")
        
        return jsonify({
            'success': True,
            'alunos': resultados,
            'total': len(resultados)
        })
        
    except Exception as e:
        app.logger.error(f"Erro na pesquisa de aluno: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/editar-registro/<turma>/<int:index>', methods=['PUT'])
@proatec_required
def editar_registro(turma, index):
    try:
        data = request.get_json()
        return jsonify({'success': True, 'message': 'Edição em desenvolvimento'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ====== ROTA DE GERENCIAMENTO DE USUÁRIOS (APENAS DIRETOR) ======
@app.route('/admin/usuarios')
@diretor_required
def gerenciar_usuarios():
    return render_template('admin_usuarios.html',
                         usuarios=USUARIOS,
                         usuario=session['usuario'],
                         tipo_usuario=session['tipo'],
                         nome_usuario=session['nome'])

@app.route('/admin/adicionar-usuario', methods=['POST'])
@diretor_required
def adicionar_usuario():
    try:
        data = request.get_json()
        username = data.get('username', '').strip().lower()
        password = data.get('password', '')
        tipo = data.get('tipo', '').strip().lower()
        nome = data.get('nome', '').strip()
        
        if not username or not password or not tipo or not nome:
            return jsonify({'success': False, 'error': 'Todos os campos são obrigatórios'})
        
        if username in USUARIOS:
            return jsonify({'success': False, 'error': 'Usuário já existe'})
        
        if tipo not in ['diretor', 'proatec', 'professor']:
            return jsonify({'success': False, 'error': 'Tipo de usuário inválido'})
        
        permissoes = []
        if tipo == 'diretor':
            permissoes = ['ver_tudo', 'editar_tudo', 'excluir_tudo', 'gerenciar_usuarios']
        elif tipo == 'proatec':
            permissoes = ['ver_tudo', 'editar_registros', 'adicionar_registros']
        elif tipo == 'professor':
            permissoes = ['ver_turmas', 'adicionar_registros', 'ver_registros_proprios']
        
        USUARIOS[username] = {
            'senha': hashlib.sha256(password.encode()).hexdigest(),
            'tipo': tipo,
            'nome': nome,
            'permissoes': permissoes
        }
        
        return jsonify({'success': True, 'message': 'Usuário adicionado com sucesso!'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/admin/excluir-usuario/<username>', methods=['DELETE'])
@diretor_required
def excluir_usuario(username):
    try:
        if username == 'diretor':
            return jsonify({'success': False, 'error': 'Não é possível excluir o usuário diretor principal'})
        
        if username not in USUARIOS:
            return jsonify({'success': False, 'error': 'Usuário não encontrado'})
        
        del USUARIOS[username]
        return jsonify({'success': True, 'message': 'Usuário excluído com sucesso!'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)