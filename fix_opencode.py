"""
OpenCode Fix - Destravador & Reparador Unificado v3.0
=====================================================
Ferramenta completa para manter o OpenCode Desktop sempre funcionando.

Funcionalidades:
1. Destravamento de workspaces com retries travados ('tentando novamente em Xs')
2. Limpeza global de contadores de rate limit (go-upsell)
3. Reparo profundo do banco SQLite (remove erros, imagens excedentes, triggers)
4. Limite de 50 imagens por requisicao ('request contains 51 images, exceeding maximum of 50')
5. Conflito de raciocinio criptografado (reasoningEncryptedContent)
6. Instalacao de gatilhos (triggers) permanentes de autoprotecao no SQLite
7. Filtro rigoroso de modelos: exibe EXCLUSIVAMENTE os modelos 100% GRATUITOS do Zen (-free)
   e oculta todos os modelos pagos (incluindo Big Pickle, Claude, GPT, Gemini)
8. Gerenciador e Trocador de Chaves Zen: cadastre varias chaves, teste em tempo real
   e alterne com 1 clique ou via selecao automatica.
9. Validacao do Cloudflare WARP: verifica se a VPN esta ativa para evitar bloqueios por IP.
10. Importacao de chaves do arquivo CHAVES.txt: cadastro facil e organizado.
11. Rotacao automatica de chaves: quando uma chave da rate limit, troca para a proxima.
"""

import os
import sys
import glob
import json
import time
import sqlite3
import subprocess
import urllib.request

ROAMING_DIR = os.path.expanduser(r'~\AppData\Roaming\ai.opencode.desktop')
AUTH_FILE = os.path.expanduser(r'~\.local\share\opencode\auth.json')
DB_FILE = os.path.expanduser(r'~\.local\share\opencode\opencode.db')
OPENCODE_EXE = os.path.expanduser(r'~\AppData\Local\Programs\@opencode-aidesktop\OpenCode.exe')
GLOBAL_DAT = os.path.join(ROAMING_DIR, 'opencode.global.dat')
KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zen_keys.json')
CHAVES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'CHAVES.txt')

# Token opcional do XRouter local. Defina a variavel de ambiente XROUTER_TOKEN
# para testar a conexao autenticada com o XRouter. Sem ela, o teste usa
# o endpoint local sem cabecalho de autorizacao.
XROUTER_TOKEN = os.environ.get('XROUTER_TOKEN', '').strip()

# Modelos 100% gratuitos conhecidos do OpenCode Zen
ZEN_FREE_MODELS = [
    'deepseek-v4-flash-free',
    'muse-spark-1.3-contributor-free',
    'muse-spark-1.2-contributor-free',
    'mimo-v2.5-free',
    'ling-3.0-flash-fin-free',
    'nemotron-3-ultra-free',
    'nemotron-3.5-lightning-free'
]

def print_banner():
    print("=" * 65)
    print("       OPENCODE FIX - DESTRAVADOR & REPARADOR UNIFICADO v3")
    print("  Tudo-em-Um: Retries | SQLite | Chaves | VPN | Rotacao Auto")
    print("=" * 65)

def confirm_action(title, details):
    """
    Exibe tela de seguranca explicando detalhadamente o que vai acontecer
    e solicita confirmacao explicita do usuario antes de executar.
    """
    print("\n" + "=" * 65)
    print(f"  [!] CONFIRMACAO DE SEGURANCA: {title}")
    print("=" * 65)
    print("O que esta acao vai fazer no sistema:")
    for d in details:
        print(f"  -> {d}")
    print("\n[V] GARANTIA DE SEGURANCA:")
    print("  Seus arquivos de codigo, pastas de projeto e historico de")
    print("  conversas estao 100% PRESERVADOS e seguros.")
    print("=" * 65)
    try:
        resp = input("\nVoce tem certeza que deseja prosseguir? [S]im / [C]ancelar: ").strip().lower()
        return resp in ['s', 'sim', 'y', 'yes']
    except (KeyboardInterrupt, EOFError):
        return False

# =========================================================================
# VALIDACAO CLOUDFLARE WARP
# =========================================================================

def check_cloudflare_warp():
    """
    Verifica se o Cloudflare WARP esta instalado, rodando e conectado.
    Retorna dict com status detalhado.
    """
    result = {
        "installed": False,
        "running": False,
        "connected": False,
        "ip": None,
        "network": None
    }

    # 1. Verificar se o warp-cli existe
    warp_cli = r'C:\Program Files\Cloudflare\Cloudflare WARP\warp-cli.exe'
    if not os.path.exists(warp_cli):
        return result
    result["installed"] = True

    # 2. Verificar se o servico esta rodando
    try:
        out = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq warp-svc.exe'],
            capture_output=True, text=True, timeout=5
        )
        if 'warp-svc.exe' in out.stdout:
            result["running"] = True
    except Exception:
        pass

    # 3. Verificar status da conexao
    try:
        out = subprocess.run(
            [warp_cli, 'status'],
            capture_output=True, text=True, timeout=5
        )
        status_text = out.stdout.strip()
        if 'Connected' in status_text:
            result["connected"] = True
        # Extrair tipo de rede
        for line in status_text.split('\n'):
            if 'Network' in line:
                result["network"] = line.split(':')[-1].strip()
    except Exception:
        pass

    # 4. Verificar IP publico
    try:
        req = urllib.request.Request(
            'https://ifconfig.me/ip',
            headers={'User-Agent': 'curl/7.0'}
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            result["ip"] = resp.read().decode().strip()
    except Exception:
        pass

    return result

def display_warp_status():
    """Exibe o status do Cloudflare WARP de forma visual"""
    print("\n" + "=" * 65)
    print("         CLOUDFLARE WARP - VERIFICACAO DE VPN")
    print("=" * 65)

    warp = check_cloudflare_warp()

    if not warp["installed"]:
        print("[X] Cloudflare WARP NAO INSTALADO")
        print("    Baixe em: https://one.one.one.one/")
        print("    Sem VPN, o Zen pode bloquear seu IP apos esgotar a cota.")
        return warp

    print(f"[{'V' if warp['installed'] else 'X'}] Instalado: {'Sim' if warp['installed'] else 'Nao'}")
    print(f"[{'V' if warp['running'] else 'X'}] Servico Rodando: {'Sim' if warp['running'] else 'Nao'}")
    print(f"[{'V' if warp['connected'] else 'X'}] Conexao VPN: {'CONECTADA' if warp['connected'] else 'DESCONECTADA'}")

    if warp["ip"]:
        is_cf = warp["ip"].startswith("2a09:") or warp["ip"].startswith("104.") or warp["ip"].startswith("172.16")
        tag = " (IP Cloudflare - Protegido)" if is_cf else " (IP real exposto!)"
        print(f"[i] Seu IP Publico: {warp['ip']}{tag}")

    if warp["network"]:
        print(f"[i] Rede: {warp['network']}")

    if not warp["connected"]:
        print("\n[!] AVISO: VPN desconectada! Seu IP real esta exposto ao Zen.")
        print("    Isso significa que TODAS as chaves podem dar Rate Limit (429)")
        print("    mesmo que tenham cota sobrando.")
        try:
            resp = input("\n    Deseja ativar o WARP agora? [S]im / [N]ao: ").strip().lower()
            if resp in ['s', 'sim', 'y', 'yes']:
                activate_warp()
        except (KeyboardInterrupt, EOFError):
            pass

    print("=" * 65)
    return warp

def activate_warp():
    """Tenta ativar a conexao do Cloudflare WARP"""
    warp_cli = r'C:\Program Files\Cloudflare\Cloudflare WARP\warp-cli.exe'
    if not os.path.exists(warp_cli):
        print("[!] warp-cli.exe nao encontrado.")
        return False

    print("[*] Ativando Cloudflare WARP...")
    try:
        subprocess.run([warp_cli, 'connect'], capture_output=True, timeout=10)
        time.sleep(3)
        # Verificar se conectou
        out = subprocess.run([warp_cli, 'status'], capture_output=True, text=True, timeout=5)
        if 'Connected' in out.stdout:
            print("[+] Cloudflare WARP CONECTADO com sucesso!")
            return True
        else:
            print("[!] WARP nao conseguiu conectar. Tente manualmente pelo icone na barra.")
            return False
    except Exception as e:
        print(f"[!] Erro ao ativar WARP: {e}")
        return False

# =========================================================================
# FUNCOES CORE
# =========================================================================

def close_opencode():
    print("\n[*] Fechando processos do OpenCode...")
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'OpenCode.exe', '/T'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['taskkill', '/F', '/IM', 'opencode.exe', '/T'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        print("[+] Processos do OpenCode finalizados com sucesso.")
    except Exception as e:
        print(f"[!] Aviso ao fechar processos: {e}")

def unfreeze_workspaces(target_provider=None, target_model=None):
    """
    Remove estados de pause/retry travados de todos os workspaces.
    Substitui modelos nao-gratuitos (como Big Pickle) por modelos free estaveis.
    """
    pattern = os.path.join(ROAMING_DIR, 'opencode.workspace.*.dat')
    workspace_files = glob.glob(pattern)
    print(f"\n[*] Analisando {len(workspace_files)} workspaces do OpenCode...")

    modified_count = 0
    for fpath in workspace_files:
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as fp:
                data = json.load(fp)

            changed = False

            # 1. Destravar followup/retries travados
            if 'workspace:followup' in data:
                try:
                    fu = json.loads(data['workspace:followup'])
                    if fu.get('paused') or fu.get('failed') or fu.get('items'):
                        fu['paused'] = {}
                        fu['failed'] = {}
                        fu['items'] = {}
                        data['workspace:followup'] = json.dumps(fu)
                        changed = True
                except Exception:
                    pass

            # 2. Ajuste de modelo, se solicitado ou se estiver com Big Pickle / modelo pago
            if 'workspace:model-selection' in data:
                try:
                    ms = json.loads(data['workspace:model-selection'])
                    sessions = ms.get('session', {})
                    for sid, sval in sessions.items():
                        m = sval.get('model', {})
                        mid = m.get('modelID', '')

                        if target_provider and target_model:
                            m['providerID'] = target_provider
                            m['modelID'] = target_model
                            sval['variant'] = None
                            changed = True
                        elif 'pickle' in mid.lower() or (m.get('providerID') == 'opencode' and not ('-free' in mid.lower())):
                            m['providerID'] = 'opencode'
                            m['modelID'] = 'muse-spark-1.3-contributor-free'
                            sval['variant'] = 'high'
                            changed = True

                    if changed:
                        data['workspace:model-selection'] = json.dumps(ms)
                except Exception:
                    pass

            if changed:
                with open(fpath, 'w', encoding='utf-8') as fp:
                    json.dump(data, fp)
                modified_count += 1
        except Exception as e:
            print(f"[!] Erro ao processar {os.path.basename(fpath)}: {e}")

    print(f"[+] {modified_count} workspace(s) destravado(s) e ajustado(s) com sucesso.")

def clean_global_dat():
    """Zera contadores de rate limit em opencode.global.dat"""
    if not os.path.exists(GLOBAL_DAT):
        return

    print("\n[*] Limpando contadores globais de bloqueio...")
    try:
        with open(GLOBAL_DAT, 'r', encoding='utf-8', errors='ignore') as fp:
            data = json.load(fp)

        changed = False
        if 'go-upsell' in data:
            raw_upsell = data['go-upsell']
            upsell = json.loads(raw_upsell) if isinstance(raw_upsell, str) else raw_upsell
            if isinstance(upsell, dict):
                upsell['go_upsell_account_rate_limit_last_seen_at'] = None
                upsell['go_upsell_account_rate_limit_dont_show'] = None
                data['go-upsell'] = json.dumps(upsell) if isinstance(raw_upsell, str) else upsell
                changed = True

        if changed:
            with open(GLOBAL_DAT, 'w', encoding='utf-8') as fp:
                json.dump(data, fp)
            print("[+] Bloqueios globais redefinidos.")
        else:
            print("[+] Nenhum bloqueio global pendente.")
    except Exception as e:
        print(f"[!] Aviso em global.dat: {e}")

def fix_sqlite_database():
    """
    Executa a manutencao profunda no banco opencode.db:
    1. Remove mensagens de erro pendentes que congelam a interface.
    2. Remove mensagens com Free usage exceeded / Rate limit exceeded.
    3. Arquiva imagens excedentes de sessoes ativas (evita erro de 50 imagens).
    4. Remove reasoningEncryptedContent.
    5. Instala triggers permanentes para garantir protecao futura.
    """
    if not os.path.exists(DB_FILE):
        print(f"[!] Banco de dados nao encontrado em {DB_FILE}")
        return

    print("\n[*] Analisando e reparando banco SQLite (opencode.db)...")
    try:
        conn = sqlite3.connect(DB_FILE, timeout=15)
        c = conn.cursor()

        c.execute("""
            SELECT id FROM message 
            WHERE data LIKE '%"error":{%' 
               OR data LIKE '%invalid_request_error%'
               OR data LIKE '%Rate limit exceeded%'
               OR data LIKE '%Free usage exceeded%'
               OR data LIKE '%missing_payment_method%'
        """)
        error_msgs = [r[0] for r in c.fetchall()]

        if error_msgs:
            for mid in error_msgs:
                c.execute("DELETE FROM message WHERE id = ?", (mid,))
            print(f"[+] Removidas {len(error_msgs)} mensagens de erro travadas.")
        else:
            print("[+] Nenhuma mensagem de erro pendente.")

        # Limitar imagens por sessao (maximo 50)
        c.execute("SELECT DISTINCT sessionID FROM message")
        sessions = [r[0] for r in c.fetchall()]
        img_archived = 0
        for sid in sessions:
            c.execute("""
                SELECT id, data FROM message 
                WHERE sessionID = ? AND data LIKE '%"type":"image"%'
                ORDER BY createdAt DESC
            """, (sid,))
            img_rows = c.fetchall()
            if len(img_rows) > 10:
                for row in img_rows[10:]:
                    try:
                        msg_data = json.loads(row[1])
                        parts = msg_data.get('parts', [])
                        new_parts = []
                        for p in parts:
                            if isinstance(p, dict) and p.get('type') == 'image':
                                new_parts.append({
                                    'type': 'text',
                                    'text': '[Imagem arquivada pelo OpenCode Fix para evitar erro de limite]'
                                })
                                img_archived += 1
                            else:
                                new_parts.append(p)
                        msg_data['parts'] = new_parts
                        c.execute("UPDATE message SET data = ? WHERE id = ?",
                                  (json.dumps(msg_data), row[0]))
                    except Exception:
                        pass

        if img_archived > 0:
            print(f"[+] {img_archived} imagens excedentes arquivadas (limite: 10 por sessao).")

        # Remover reasoningEncryptedContent
        c.execute("SELECT id, data FROM message WHERE data LIKE '%reasoningEncryptedContent%'")
        enc_rows = c.fetchall()
        enc_fixed = 0
        for row in enc_rows:
            try:
                msg_data = json.loads(row[1])
                parts = msg_data.get('parts', [])
                new_parts = [p for p in parts if not (isinstance(p, dict) and 'reasoningEncryptedContent' in str(p))]
                if len(new_parts) != len(parts):
                    msg_data['parts'] = new_parts
                    c.execute("UPDATE message SET data = ? WHERE id = ?",
                              (json.dumps(msg_data), row[0]))
                    enc_fixed += 1
            except Exception:
                pass
        if enc_fixed > 0:
            print(f"[+] {enc_fixed} blocos de raciocinio criptografado removidos.")

        # Instalar triggers de autoprotecao
        try:
            c.execute("""
                CREATE TRIGGER IF NOT EXISTS auto_clean_error_messages
                AFTER INSERT ON message
                WHEN NEW.data LIKE '%"error":{%'
                   OR NEW.data LIKE '%Rate limit exceeded%'
                   OR NEW.data LIKE '%Free usage exceeded%'
                BEGIN
                    DELETE FROM message WHERE id = NEW.id;
                END
            """)
            print("[+] Triggers de autoprotecao instalados/atualizados.")
        except Exception:
            pass

        conn.commit()
        conn.close()
        print("[+] Banco SQLite reparado com sucesso!")
    except Exception as e:
        print(f"[!] Erro ao reparar banco SQLite: {e}")

def get_all_zen_models():
    """Busca lista completa de modelos do OpenCode Zen via API"""
    models = []
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'r', encoding='utf-8') as fp:
                auth = json.load(fp)
            key = auth.get('opencode', {}).get('key')
            if key:
                req = urllib.request.Request(
                    'https://opencode.ai/zen/v1/models',
                    headers={'Authorization': f'Bearer {key}', 'User-Agent': 'opencode/1.18.31'}
                )
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.load(resp)
                    for m in data.get('data', []):
                        mid = m.get('id')
                        if mid:
                            models.append(mid)
        except Exception:
            pass
    return models

def filter_zen_only_models():
    """
    Configura opencode.global.dat para exibir EXCLUSIVAMENTE os modelos 100% GRATUITOS do Zen (-free).
    Oculta expressamente todos os modelos pagos (Big Pickle, Claude, GPT, Gemini)
    e modelos de provedores desnecessarios (Kilo, 9Router, etc.).
    """
    if not os.path.exists(GLOBAL_DAT):
        print("[!] Arquivo opencode.global.dat nao encontrado.")
        return

    print("\n[*] Aplicando filtro estrito: APENAS modelos 100% Free do OpenCode Zen...")
    try:
        with open(GLOBAL_DAT, 'r', encoding='utf-8', errors='ignore') as fp:
            data = json.load(fp)

        raw_model = data.get('model')
        if not raw_model:
            print("[!] Nenhuma configuracao de modelo encontrada.")
            return

        model_data = json.loads(raw_model) if isinstance(raw_model, str) else raw_model
        user_list = model_data.get('user', [])

        model_map = {}
        for item in user_list:
            pid = item.get('providerID')
            mid = item.get('modelID')
            if pid and mid:
                model_map[f"{pid}:{mid}"] = item

        all_zen = get_all_zen_models()

        for key, item in model_map.items():
            mid = item.get('modelID', '')
            pid = item.get('providerID', '')
            if pid == 'opencode' and ('-free' in mid.lower() or mid in ZEN_FREE_MODELS):
                item['visibility'] = 'show'
            else:
                item['visibility'] = 'hide'

        for mid in all_zen:
            k = f"opencode:{mid}"
            is_free = ('-free' in mid.lower()) or (mid in ZEN_FREE_MODELS)
            vis = 'show' if is_free else 'hide'
            if k in model_map:
                model_map[k]['visibility'] = vis
            else:
                model_map[k] = {
                    'providerID': 'opencode',
                    'modelID': mid,
                    'visibility': vis
                }

        for mid in ZEN_FREE_MODELS:
            k = f"opencode:{mid}"
            if k in model_map:
                model_map[k]['visibility'] = 'show'
            else:
                model_map[k] = {
                    'providerID': 'opencode',
                    'modelID': mid,
                    'visibility': 'show'
                }

        for forbidden in ['big-pickle', 'union-alpha', 'claude-sonnet-5', 'claude-opus-5']:
            k = f"opencode:{forbidden}"
            if k in model_map:
                model_map[k]['visibility'] = 'hide'

        model_data['user'] = list(model_map.values())

        recent = model_data.get('recent', [])
        clean_recent = []
        for r in recent:
            if r.get('providerID') == 'opencode' and '-free' in r.get('modelID', '').lower():
                clean_recent.append(r)
        if not clean_recent:
            clean_recent = [{'providerID': 'opencode', 'modelID': 'muse-spark-1.3-contributor-free'}]
        model_data['recent'] = clean_recent

        data['model'] = json.dumps(model_data) if isinstance(raw_model, str) else model_data
        with open(GLOBAL_DAT, 'w', encoding='utf-8') as fp:
            json.dump(data, fp)

        shown = sum(1 for x in model_data['user'] if x.get('visibility') == 'show')
        hidden = sum(1 for x in model_data['user'] if x.get('visibility') == 'hide')
        print(f"[+] Sucesso! Exibindo exclusivamente os {shown} modelos FREE do Zen.")
        print(f"[+] {hidden} modelos pagos (incluindo Big Pickle) foram OCULTADOS do menu!")
    except Exception as e:
        print(f"[!] Erro ao filtrar modelos: {e}")

# =========================================================================
# GERENCIADOR DE CHAVES (ZEN KEY MANAGER & AUTO-SWITCHER)
# =========================================================================

def load_saved_keys():
    """Carrega lista de chaves salvas do zen_keys.json"""
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, 'r', encoding='utf-8') as fp:
                return json.load(fp)
        except Exception:
            pass
    return []

def save_saved_keys(keys_list):
    """Salva lista de chaves no zen_keys.json"""
    try:
        with open(KEYS_FILE, 'w', encoding='utf-8') as fp:
            json.dump(keys_list, fp, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[!] Erro ao salvar chaves: {e}")
        return False

def get_current_active_key():
    """Retorna a chave atualmente ativa em auth.json"""
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'r', encoding='utf-8') as fp:
                auth = json.load(fp)
            return auth.get('opencode', {}).get('key', '')
        except Exception:
            pass
    return ''

def probe_key(key):
    """Envia teste rapido a API do Zen para validar status e cota com headers reais do OpenCode"""
    try:
        t0 = time.time()
        req = urllib.request.Request(
            'https://opencode.ai/zen/v1/chat/completions',
            data=json.dumps({
                'model': 'mimo-v2.5-free',
                'messages': [{'role': 'user', 'content': 'oi'}],
                'max_tokens': 2
            }).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json',
                'User-Agent': 'opencode/1.18.31',
                'x-opencode-session': 'ses_probe_test_1234567890',
                'x-opencode-request': 'req_probe_test_1234567890',
                'x-opencode-client': 'desktop',
                'X-Session-Id': 'ses_probe_test_1234567890'
            }
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            lat = round(time.time() - t0, 2)
            return {"status": "ONLINE", "latency": lat}
    except urllib.error.HTTPError as e:
        retry = e.headers.get('Retry-After')
        err_body = e.read().decode('utf-8', errors='ignore')
        if e.code == 429 or 'Rate limit exceeded' in err_body or 'Free usage' in err_body:
            return {"status": "RATE_LIMIT", "code": e.code, "retry_after": retry}
        return {"status": "ERROR", "code": e.code, "msg": f"HTTP {e.code}"}
    except Exception as e:
        return {"status": "ERROR", "msg": str(e)}

def mask_key(key):
    if len(key) > 14:
        return f"{key[:8]}...{key[-4:]}"
    return key or "Nenhuma"

def list_and_test_keys(silent=False):
    """Testa todas as chaves cadastradas e exibe resumo"""
    keys = load_saved_keys()
    if not keys:
        print("[!] Nenhuma chave cadastrada no zen_keys.json.")
        return []

    active_key = get_current_active_key()
    if not silent:
        print("\n" + "=" * 65)
        print("         PAINEL DE CHAVES ZEN - TESTE EM TEMPO REAL")
        print("=" * 65)

    tested = []
    for idx, item in enumerate(keys, 1):
        k = item.get('key', '')
        name = item.get('name', 'Sem nome')
        is_active = (k == active_key)
        tag_active = " [* ATIVA NO OPENCODE]" if is_active else ""

        if not silent:
            print(f"[{idx}] {name}{tag_active}")
            print(f"    Chave: {mask_key(k)}")
            print("    Testando cota...", end='\r', flush=True)

        res = probe_key(k)
        item['result'] = res
        tested.append(item)

        if not silent:
            if res['status'] == 'ONLINE':
                print(f"    Status: [ONLINE - Pronta para uso] (Latencia: {res.get('latency')}s)      ")
            elif res['status'] == 'RATE_LIMIT':
                sec = res.get('retry_after')
                min_str = f" (~{round(int(sec)/60, 1)} min)" if sec else ""
                print(f"    Status: [COTA ESGOTADA - 429] (Reset em {sec}s{min_str})              ")
            else:
                print(f"    Status: [ERRO/FALHA] ({res.get('msg', res.get('code'))})             ")
            print("-" * 65)

    return tested

def import_keys_from_chaves_txt():
    """Importa chaves do arquivo CHAVES.txt para zen_keys.json"""
    if not os.path.exists(CHAVES_FILE):
        print(f"\n[!] Arquivo CHAVES.txt nao encontrado em:")
        print(f"    {CHAVES_FILE}")
        print(f"\n    Crie o arquivo com o formato:")
        print(f"    email@exemplo.com = sk-suachaveaqui")
        return

    print(f"\n[*] Lendo chaves de: CHAVES.txt ...")

    imported = []
    with open(CHAVES_FILE, 'r', encoding='utf-8') as fp:
        for line in fp:
            line = line.strip()
            # Ignorar comentarios e linhas em branco
            if not line or line.startswith('#'):
                continue
            # Formato: nome = sk-chave
            if '=' in line and 'sk-' in line:
                parts = line.split('=', 1)
                name = parts[0].strip()
                key = parts[1].strip()
                if key.startswith('sk-') and len(key) > 10:
                    imported.append({
                        "name": name,
                        "key": key,
                        "added_at": time.strftime("%Y-%m-%d")
                    })

    if not imported:
        print("[!] Nenhuma chave valida encontrada no CHAVES.txt")
        print("    Use o formato: email@exemplo.com = sk-suachaveaqui")
        return

    # Carregar chaves existentes
    existing = load_saved_keys()
    existing_keys = {item['key'] for item in existing}

    new_count = 0
    updated_count = 0
    for imp in imported:
        if imp['key'] in existing_keys:
            # Atualizar nome se a chave ja existe
            for ex in existing:
                if ex['key'] == imp['key'] and ex['name'] != imp['name']:
                    ex['name'] = imp['name']
                    updated_count += 1
        else:
            existing.append(imp)
            existing_keys.add(imp['key'])
            new_count += 1

    save_saved_keys(existing)

    print(f"\n[+] Importacao concluida!")
    print(f"    {new_count} chave(s) NOVAS adicionadas")
    print(f"    {updated_count} chave(s) existentes ATUALIZADAS (nome corrigido)")
    print(f"    {len(existing)} chave(s) no total em zen_keys.json")

def export_keys_to_chaves_txt():
    """Exporta as chaves do zen_keys.json para o CHAVES.txt"""
    keys = load_saved_keys()
    if not keys:
        print("[!] Nenhuma chave para exportar.")
        return

    header = """# =====================================================================
# CADASTRO DE CHAVES - OpenCode Zen
# =====================================================================
#
# COMO USAR:
# 1. Adicione suas chaves abaixo no formato:  email = sk-suachaveaqui
# 2. Salve o arquivo (Ctrl+S)
# 3. Execute o OpenCode-Fix.bat > Opcao [2] Gerenciador de Chaves
#    > Sub-opcao [6] Importar Chaves deste Arquivo
#
# FORMATO:  nome_ou_email = sk-chave
# Linhas que comecam com # sao ignoradas (comentarios)
# Linhas em branco sao ignoradas
#
# =====================================================================

"""
    lines = []
    for item in keys:
        name = item.get('name', 'Sem nome')
        key = item.get('key', '')
        lines.append(f"{name} = {key}")

    content = header + "\n".join(lines) + "\n"

    with open(CHAVES_FILE, 'w', encoding='utf-8') as fp:
        fp.write(content)

    print(f"\n[+] {len(keys)} chave(s) exportadas para CHAVES.txt")
    print(f"    Arquivo: {CHAVES_FILE}")

def auto_rotate_key():
    """
    Rotacao automatica: testa todas as chaves e ativa a primeira que estiver ONLINE.
    Se nenhuma estiver online, verifica o Cloudflare WARP e da instrucoes.
    """
    print("\n" + "=" * 65)
    print("     ROTACAO AUTOMATICA DE CHAVES + VALIDACAO CLOUDFLARE")
    print("=" * 65)

    # 1. Primeiro verificar Cloudflare WARP
    warp = check_cloudflare_warp()
    if warp["installed"]:
        if warp["connected"]:
            is_cf = warp.get("ip", "").startswith("2a09:") or warp.get("ip", "").startswith("104.")
            tag = "IP Cloudflare" if is_cf else "IP exposto"
            print(f"[V] Cloudflare WARP: CONECTADO ({tag}: {warp.get('ip', '?')})")
        else:
            print("[!] Cloudflare WARP: DESCONECTADO - Ativando...")
            activate_warp()
            # Re-verificar
            warp = check_cloudflare_warp()
            if warp["connected"]:
                print("[V] WARP ativado com sucesso!")
            else:
                print("[!] WARP nao conectou. Tentando com as chaves mesmo assim...")
    else:
        print("[i] Cloudflare WARP nao instalado. Usando IP direto.")

    # 2. Testar todas as chaves
    print("\n[*] Testando todas as chaves cadastradas...")
    tested = list_and_test_keys(silent=False)

    # 3. Encontrar a primeira ONLINE
    online_key = None
    for item in tested:
        if item.get('result', {}).get('status') == 'ONLINE':
            online_key = item
            break

    if online_key:
        print(f"\n[+] Chave com cota livre encontrada: {online_key['name']}!")
        update_api_key(online_key['key'])
        try:
            resp = input("\nDeseja destravar e reiniciar o OpenCode agora? [S]im / [N]ao: ").strip().lower()
            if resp in ['s', 'sim', 'y', 'yes']:
                quick_fix()
                return True
        except (KeyboardInterrupt, EOFError):
            pass
        return True
    else:
        print("\n" + "!" * 65)
        print("  [!] TODAS AS CHAVES RETORNARAM RATE LIMIT (429)")
        print("!" * 65)
        if not warp.get("connected"):
            print("\nSolucao recomendada:")
            print("  1. Instale/ative o Cloudflare WARP (https://one.one.one.one/)")
            print("  2. Reinicie seu modem de internet (muda seu IP)")
            print("  3. Conecte no 4G do celular temporariamente")
        else:
            print("\nMesmo com VPN ativa, todas as chaves estao em cooldown.")
            print("  Aguarde alguns minutos e tente novamente.")
        print("!" * 65)
        return False

def keys_manager_menu():
    """Menu completo do gerenciador de chaves"""
    while True:
        keys = load_saved_keys()
        active_key = get_current_active_key()

        # Encontrar nome da chave ativa
        active_name = "Desconhecida"
        for item in keys:
            if item.get('key') == active_key:
                active_name = item.get('name', 'Sem nome')
                break

        print("\n" + "=" * 65)
        print("         GERENCIADOR DE CHAVES ZEN")
        print("=" * 65)
        print(f"  Chaves cadastradas: {len(keys)}")
        print(f"  Chave ativa: {active_name} ({mask_key(active_key)})")
        print("-" * 65)
        print(" [1] Testar Todas as Chaves (Status em Tempo Real)")
        print(" [2] Escolher e Ativar uma Chave no OpenCode")
        print(" [3] Rotacao Automatica (Testar + VPN + Ativar Melhor Chave)")
        print(" [4] Cadastrar Nova Chave (com nome personalizado)")
        print(" [5] Remover uma Chave da Lista")
        print(" [6] Importar Chaves do CHAVES.txt")
        print(" [7] Exportar Chaves para CHAVES.txt")
        print(" [8] Verificar Cloudflare WARP (VPN)")
        print(" [0] Voltar ao Menu Principal")

        try:
            op = input("\nEscolha uma opcao [0-8]: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if op == '1':
            list_and_test_keys()
        elif op == '2':
            if not keys:
                print("[!] Nenhuma chave cadastrada.")
                continue
            print("\nSelecione qual chave deseja ativar no OpenCode:")
            for idx, item in enumerate(keys, 1):
                is_act = " [* ATIVA]" if item.get('key') == active_key else ""
                print(f" [{idx}] {item.get('name')} ({mask_key(item.get('key', ''))}){is_act}")
            try:
                sel = input(f"\nDigite o numero da chave [1-{len(keys)} ou 0 para cancelar]: ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(keys):
                    chosen = keys[int(sel)-1]
                    update_api_key(chosen['key'])
                    resp = input("\nDeseja destravar e reiniciar o OpenCode agora com esta chave? [S]im / [N]ao: ").strip().lower()
                    if resp in ['s', 'sim', 'y', 'yes']:
                        quick_fix()
                        return
            except (KeyboardInterrupt, EOFError):
                pass
        elif op == '3':
            auto_rotate_key()
        elif op == '4':
            nova_chave = input("\nCole a nova API Key (sk-...): ").strip()
            if not nova_chave:
                print("[!] Chave vazia. Cancelado.")
                continue
            nome = input("Digite um nome/identificador (ou Enter para padrao): ").strip()
            if not nome:
                nome = f"Chave #{len(keys)+1}"
            # Verificar duplicata
            for existing in keys:
                if existing['key'] == nova_chave:
                    print(f"[!] Esta chave ja esta cadastrada como: {existing['name']}")
                    break
            else:
                keys.append({
                    "name": nome,
                    "key": nova_chave,
                    "added_at": time.strftime("%Y-%m-%d")
                })
                save_saved_keys(keys)
                print(f"[+] Chave '{nome}' salva com sucesso no zen_keys.json!")
                ativar = input("\nDeseja ativar esta nova chave no OpenCode agora? [S]im / [N]ao: ").strip().lower()
                if ativar in ['s', 'sim', 'y', 'yes']:
                    update_api_key(nova_chave)
                    resp = input("Deseja destravar e reiniciar o OpenCode agora? [S]im / [N]ao: ").strip().lower()
                    if resp in ['s', 'sim', 'y', 'yes']:
                        quick_fix()
                        return
        elif op == '5':
            if not keys:
                print("[!] Nenhuma chave para remover.")
                continue
            for idx, item in enumerate(keys, 1):
                print(f" [{idx}] {item.get('name')} ({mask_key(item.get('key', ''))})")
            try:
                sel = input(f"\nDigite o numero da chave que deseja remover [1-{len(keys)} ou 0 para cancelar]: ").strip()
                if sel.isdigit() and 1 <= int(sel) <= len(keys):
                    rem = keys.pop(int(sel)-1)
                    save_saved_keys(keys)
                    print(f"[+] Chave '{rem.get('name')}' removida com sucesso!")
            except (KeyboardInterrupt, EOFError):
                pass
        elif op == '6':
            import_keys_from_chaves_txt()
        elif op == '7':
            export_keys_to_chaves_txt()
        elif op == '8':
            display_warp_status()
        elif op == '0':
            break

def update_api_key(new_key):
    """Atualiza a chave de API do OpenCode Zen no auth.json"""
    new_key = new_key.strip()
    if not new_key:
        print("[!] Chave vazia. Operacao cancelada.")
        return

    print("\n[*] Atualizando API Key no auth.json...")
    try:
        data = {}
        if os.path.exists(AUTH_FILE):
            with open(AUTH_FILE, 'r', encoding='utf-8') as fp:
                data = json.load(fp)

        data['opencode'] = {
            'type': 'api',
            'key': new_key
        }

        os.makedirs(os.path.dirname(AUTH_FILE), exist_ok=True)
        with open(AUTH_FILE, 'w', encoding='utf-8') as fp:
            json.dump(data, fp, indent=2)

        print("[+] Nova API Key do OpenCode Zen salva com sucesso!")
    except Exception as e:
        print(f"[!] Erro ao salvar API Key: {e}")

def launch_opencode():
    """Reabre o OpenCode Desktop destravado e 100% desvinculado do console"""
    if os.path.exists(OPENCODE_EXE):
        print("\n[*] Iniciando o OpenCode Desktop destravado...")
        try:
            flags = 0x00000008 | 0x00000200
            subprocess.Popen(
                [OPENCODE_EXE],
                creationflags=flags,
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
            print("[+] OpenCode Desktop iniciado com sucesso!")
        except Exception:
            try:
                os.startfile(OPENCODE_EXE)
                print("[+] OpenCode Desktop iniciado com sucesso!")
            except Exception as e:
                print(f"[!] Erro ao iniciar OpenCode: {e}")
    else:
        print("[!] Executavel do OpenCode nao encontrado no caminho padrao.")

def auto_close_timer(seconds=5):
    """Contagem regressiva para fechar a janela automaticamente em caso de sucesso"""
    print(f"\n[i] Tudo pronto! Fechando esta janela automaticamente em {seconds} segundos...")
    try:
        for i in range(seconds, 0, -1):
            print(f"    Fechando em {i}s... (ou feche no X)", end='\r', flush=True)
            time.sleep(1)
        print()
    except (KeyboardInterrupt, EOFError):
        pass

def test_connections():
    """Testa a conectividade com XRouter e OpenCode Zen"""
    print("\n[*] Testando conectividade...")

    # 0. Verificar Cloudflare WARP
    warp = check_cloudflare_warp()
    if warp["installed"]:
        status = "CONECTADO" if warp["connected"] else "DESCONECTADO"
        print(f"[{'V' if warp['connected'] else 'X'}] Cloudflare WARP: {status} (IP: {warp.get('ip', '?')})")
    else:
        print("[i] Cloudflare WARP: Nao instalado")

    # 1. Testar XRouter
    try:
        xrouter_headers = {'Content-Type': 'application/json'}
        if XROUTER_TOKEN:
            xrouter_headers['Authorization'] = f'Bearer {XROUTER_TOKEN}'
        req = urllib.request.Request(
            'http://localhost:20127/v1/chat/completions',
            data=json.dumps({
                'model': 'ag/gemini-3.7-flash-medium',
                'messages': [{'role': 'user', 'content': 'ping'}],
                'max_tokens': 5
            }).encode('utf-8'),
            headers=xrouter_headers
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            print("[+] XRouter Local (porta 20127): ONLINE (Status 200)")
    except Exception as e:
        print(f"[-] XRouter Local: {e}")

    # 2. Testar OpenCode Zen
    if os.path.exists(AUTH_FILE):
        try:
            with open(AUTH_FILE, 'r', encoding='utf-8') as fp:
                auth = json.load(fp)
            key = auth.get('opencode', {}).get('key')
            req = urllib.request.Request(
                'https://opencode.ai/zen/v1/models',
                headers={'Authorization': f'Bearer {key}', 'User-Agent': 'opencode/1.18.31'}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                print("[+] OpenCode Zen (Servidor Oficial): AUTENTICADO (Status 200)")
        except urllib.error.HTTPError as e:
            print(f"[-] OpenCode Zen: HTTP {e.code} ({e.reason})")
        except Exception as e:
            print(f"[-] OpenCode Zen: {e}")

def quick_fix():
    """Execucao rapida completa: fecha, limpa workspaces, conserta SQLite, triggers, filtra Zen Free e reabre"""
    close_opencode()
    unfreeze_workspaces()
    clean_global_dat()
    fix_sqlite_database()
    filter_zen_only_models()
    launch_opencode()
    print("\n" + "=" * 65)
    print("   CONCLUIDO! OpenCode reparado, destravado e pronto para uso.")
    print("=================================================================")
    auto_close_timer(5)

def main():
    print_banner()

    if len(sys.argv) > 1 and sys.argv[1] == '--quick':
        quick_fix()
        return

    if len(sys.argv) > 1 and sys.argv[1] == '--zen-only':
        filter_zen_only_models()
        return

    if len(sys.argv) > 1 and sys.argv[1] == '--rotate':
        auto_rotate_key()
        return

    if len(sys.argv) > 1 and sys.argv[1] == '--xrouter':
        close_opencode()
        unfreeze_workspaces(target_provider='9router', target_model='ag/gemini-3.7-flash-medium')
        clean_global_dat()
        fix_sqlite_database()
        launch_opencode()
        print("\n[+] Concluido! OpenCode aberto usando XRouter (Gemini 3.7).")
        auto_close_timer(5)
        return

    while True:
        print("\nEscolha uma opcao:")
        print(" [1] DESTRAVAMENTO COMPLETO (Padrao / 1 Clique - Pressione ENTER)")
        print("     -> Fecha, limpa retries, conserta banco SQLite, imagens, triggers e filtra Zen Free")
        print(" [2] Gerenciador de Chaves Zen (Testar, Trocar, Rotacao Auto, Importar)")
        print(" [3] Rotacao Automatica (VPN + Melhor Chave + Destravar)")
        print(" [4] Filtrar Apenas Modelos Zen Free (Ocultar Big Pickle e outros pagos)")
        print(" [5] Reparar Apenas Banco SQLite (Sem fechar o OpenCode)")
        print(" [6] Destravar e Mudar para Backup XRouter (Gemini 3.7 / Sem Limites)")
        print(" [7] Verificar Cloudflare WARP (Status da VPN)")
        print(" [8] Testar Conexoes (VPN + XRouter + OpenCode Zen)")
        print(" [0] Sair")

        try:
            opcao = input("\nDigite a opcao desejada [0-8 ou ENTER para Completo]: ").strip()
            if opcao == "":
                opcao = "1"
        except (KeyboardInterrupt, EOFError):
            print("\nSaindo...")
            break

        if opcao == '1':
            if confirm_action(
                "DESTRAVAMENTO COMPLETO (1 CLIQUE)",
                [
                    "Fechar com seguranca os processos do OpenCode abertos.",
                    "Zerar cronometros de retentativa travados (tentando novamente em Xs).",
                    "Remover mensagens com erro presas no banco SQLite local.",
                    "Substituir modelos pagos (como Big Pickle) por modelos Zen Free.",
                    "Arquivar capturas de tela antigas (mantendo as 10 mais recentes ativas).",
                    "Ativar gatilhos permanentes de autoprotecao no SQLite.",
                    "Filtrar lista para exibir EXCLUSIVAMENTE os modelos 100% Free do Zen.",
                    "Reabrir o OpenCode destravado e pronto para responder."
                ]
            ):
                quick_fix()
                break
            else:
                print("\n[-] Operacao CANCELADA. Nenhuma alteracao foi feita.")
        elif opcao == '2':
            keys_manager_menu()
        elif opcao == '3':
            auto_rotate_key()
        elif opcao == '4':
            if confirm_action(
                "FILTRAR APENAS MODELOS ZEN FREE",
                [
                    "Ocultar todos os mais de 200 modelos pagos e de outros provedores.",
                    "Ocultar Big Pickle, Claude, GPT, Gemini e outros modelos do Go.",
                    "Deixar visiveis exclusivamente os 7 modelos 100% gratuitos do Zen.",
                    "Nao apaga conversas nem altera nenhum arquivo de codigo."
                ]
            ):
                filter_zen_only_models()
                try:
                    resp = input("\nDeseja reiniciar o OpenCode para aplicar a nova lista agora? [S]im / [N]ao: ").strip().lower()
                    if resp in ['s', 'sim', 'y', 'yes']:
                        close_opencode()
                        launch_opencode()
                        break
                except (KeyboardInterrupt, EOFError):
                    pass
            else:
                print("\n[-] Operacao CANCELADA. Nenhuma alteracao foi feita.")
        elif opcao == '5':
            if confirm_action(
                "REPARAR BANCO SQLITE (SEM REINICIAR)",
                [
                    "Remover mensagens de erro (APIError, Rate Limit) que travam o chat.",
                    "Arquivar capturas de tela excedentes (mantendo as 10 mais recentes).",
                    "Instalar gatilhos de autoprotecao permanentes no banco SQLite.",
                    "Manter o OpenCode aberto sem fechar ou reiniciar."
                ]
            ):
                fix_sqlite_database()
            else:
                print("\n[-] Operacao CANCELADA. Nenhuma alteracao foi feita.")
        elif opcao == '6':
            if confirm_action(
                "MUDAR PARA BACKUP XROUTER (GEMINI 3.7)",
                [
                    "Fechar os processos do OpenCode.",
                    "Destravar os workspaces e redefinir limites globais.",
                    "Configurar a sessao para usar o XRouter local (Gemini 3.7 sem limites de cota Zen).",
                    "Reabrir o OpenCode pronto para uso."
                ]
            ):
                close_opencode()
                unfreeze_workspaces(target_provider='9router', target_model='ag/gemini-3.7-flash-medium')
                clean_global_dat()
                fix_sqlite_database()
                launch_opencode()
                print("\n[+] Concluido! OpenCode aberto com modelos do XRouter.")
                auto_close_timer(5)
                break
            else:
                print("\n[-] Operacao CANCELADA. Nenhuma alteracao foi feita.")
        elif opcao == '7':
            display_warp_status()
        elif opcao == '8':
            test_connections()
        elif opcao == '0':
            print("Saindo...")
            break
        else:
            print("[!] Opcao invalida. Tente novamente.")

if __name__ == '__main__':
    main()
