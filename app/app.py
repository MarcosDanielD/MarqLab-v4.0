"""
Nexus Lead Pro - B2B Growth Engine & Lead Generation Dashboard.
Flask application server with SSE streaming, REST API, Chart data, and CRM actions.

"""

import os
import sys
import io
import re
import json
import time
import queue
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, Response, send_file, session, redirect, url_for
import pandas as pd

# Guarantee app directory is in sys.path for local module resolution
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if _CURRENT_DIR not in sys.path:
    sys.path.insert(0, _CURRENT_DIR)

import banco_dados
import minerador
import gerador_propostas
import servico_prints
import servico_cnpj
import autenticacao
import servico_radar_cnpj
import servico_instagram

app = Flask(
    __name__,
    template_folder=os.path.join(_CURRENT_DIR, "templates"),
    static_folder=os.path.join(_CURRENT_DIR, "static"),
)
app.secret_key = os.environ.get("MARQ_SECRET_KEY", "marq-lab-lead-secret-key-prod-secure-2026")
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

# Ensure schema migrations run immediately on app startup
try:
    banco_dados.init_db()
except Exception as _e:
    print(f"Warning: init_db on startup encountered: {_e}")

# Queue for Server-Sent Events (SSE)
sse_queues = []
active_presences = {}


def broadcast_sse(data):
    """Broadcast an event to all connected users via SSE."""
    msg = f"data: {json.dumps(data)}\n\n"
    for q in list(sse_queues):
        try:
            q.put_nowait(msg)
        except Exception:
            pass


def sse_event_listener(data):
    """Callback for scraper events to broadcast to all open SSE connections."""
    broadcast_sse(data)


# Register listener to active scraper
minerador.active_scraper.subscribers.append(sse_event_listener)


# ----------------------------------------------------
# STATIC ASSETS & FAVICON
# ----------------------------------------------------
@app.route("/favicon.ico")
def favicon():
    fav_path = os.path.join(app.static_folder, "favicon.ico")
    if os.path.exists(fav_path):
        return send_file(fav_path, mimetype="image/x-icon")
    return ("", 204)


# ----------------------------------------------------
# AUTHENTICATION & SESSION ROUTES
# ----------------------------------------------------
@app.route("/login", methods=["GET"])
def login_view():
    banco_dados.init_db()
    if autenticacao.get_current_user():
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    identifier = data.get("identifier", "").strip()
    password = data.get("password", "")
    remember = data.get("remember", True)

    user = autenticacao.authenticate(identifier, password)
    if not user:
        return jsonify({"success": False, "error": "E-mail/usuário ou senha incorretos."}), 401

    session.permanent = bool(remember)
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user.get("email")
    session["permission_level"] = user.get("permission_level", "SDR")

    banco_dados.add_log(f"Login efetuado com sucesso pelo usuário '{user['name']}' ({user.get('permission_level')}).", "INFO")
    return jsonify({"success": True, "user": user})


@app.route("/api/auth/logout", methods=["POST", "GET"])
def api_logout():
    user_name = session.get("user_name", "Usuário")
    session.clear()
    banco_dados.add_log(f"Usuário '{user_name}' encerrou a sessão.", "INFO")
    if request.path.startswith("/api/"):
        return jsonify({"success": True, "message": "Sessão encerrada com sucesso."})
    return redirect(url_for("login_view"))


@app.route("/api/auth/me", methods=["GET"])
def api_me():
    user = autenticacao.get_current_user()
    if not user:
        return jsonify({"success": False, "unauthenticated": True}), 401
    return jsonify({"success": True, "user": user})


@app.route("/api/auth/operators_setup", methods=["GET"])
def api_operators_setup():
    """Public helper for first-time onboarding / password activation."""
    ops = banco_dados.get_operators()
    has_any = banco_dados.count_operators_with_access() > 0
    safe_ops = [{"id": o["id"], "name": o["name"], "role": o.get("role", "SDR"), "email": o.get("email"), "has_access": o.get("has_access", False)} for o in ops]
    return jsonify({"success": True, "operators": safe_ops, "has_any_access": has_any})


@app.route("/api/auth/activate", methods=["POST"])
def api_activate():
    """Sets initial password and email for an operator."""
    data = request.get_json() or {}
    op_id = data.get("operator_id")
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not op_id or not email or not password:
        return jsonify({"success": False, "error": "Todos os campos são obrigatórios."}), 400

    if len(password) < 6:
        return jsonify({"success": False, "error": "A senha deve conter no mínimo 6 caracteres."}), 400

    op = banco_dados.get_operator_by_id(op_id)
    if not op:
        return jsonify({"success": False, "error": "Membro não encontrado."}), 404

    # Check if email is already taken by another operator
    existing = banco_dados.get_operator_by_email(email)
    if existing and existing["id"] != op_id:
        return jsonify({"success": False, "error": "Este e-mail já está em uso por outro membro."}), 400

    pwd_hash = autenticacao.hash_password(password)
    banco_dados.set_operator_credentials(op_id, email, pwd_hash)

    # Automatically log the user in
    session.permanent = True
    session["user_id"] = op["id"]
    session["user_name"] = op["name"]
    session["user_email"] = email.lower()
    session["permission_level"] = op.get("permission_level", "SDR")

    banco_dados.add_log(f"Primeiro acesso/ativação de senha concluído para '{op['name']}' ({email}).", "SUCCESS")
    return jsonify({"success": True, "message": "Conta ativada com sucesso!", "user": {
        "id": op["id"],
        "name": op["name"],
        "email": email,
        "permission_level": op.get("permission_level", "SDR")
    }})


@app.route("/api/presence/ping", methods=["POST"])
@autenticacao.login_required
def presence_ping():
    """Heartbeat endpoint for multi-user presence."""
    user = autenticacao.get_current_user()
    now = time.time()
    active_presences[user["id"]] = {
        "id": user["id"],
        "name": user["name"],
        "role": user.get("role", "SDR"),
        "permission_level": user.get("permission_level", "SDR"),
        "last_seen": now
    }
    # Clean up presences older than 60s
    active_list = [p for p in active_presences.values() if now - p["last_seen"] < 60]
    return jsonify({"success": True, "active_users": active_list})


# ----------------------------------------------------
# MAIN DASHBOARD VIEW
# ----------------------------------------------------
@app.route("/")
@autenticacao.login_required
def index():
    banco_dados.init_db()
    return render_template("index.html")


@app.route("/api/scrape/start", methods=["POST"])
@autenticacao.login_required
def start_scrape():
    data = request.get_json() or {}
    niche = data.get("niche", "").strip()
    city = data.get("city", "").strip()
    target_count = int(data.get("target_count") or 100)

    if not niche or not city:
        return jsonify({"success": False, "error": "Informe o Nicho e a Cidade para iniciar a busca."}), 400

    if minerador.active_scraper.is_running:
        return jsonify({"success": False, "error": "Uma extração já está em andamento. Aguarde ou clique em Parar."}), 400

    try:
        campaign_id = minerador.start_scraping(niche, city, target_count)
        return jsonify({
            "success": True,
            "campaign_id": campaign_id,
            "message": f"Mineração iniciada para '{niche}' em '{city}'. Meta: {target_count} leads."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/scrape/stop", methods=["POST"])
@autenticacao.login_required
def stop_scrape():
    stopped = minerador.stop_scraping()
    return jsonify({"success": True, "stopped": stopped})


@app.route("/api/scrape/status", methods=["GET"])
def get_scrape_status():
    progress = 0
    if minerador.active_scraper.target_count > 0:
        progress = min(100, round((minerador.active_scraper.leads_count / minerador.active_scraper.target_count) * 100, 1))

    return jsonify({
        "is_running": minerador.active_scraper.is_running,
        "leads_count": minerador.active_scraper.leads_count,
        "target_count": minerador.active_scraper.target_count,
        "current_lead": minerador.active_scraper.current_lead_name,
        "status_message": minerador.active_scraper.status_message,
        "progress_percent": progress,
    })


@app.route("/api/stream")
def sse_stream():
    """Server-Sent Events endpoint for real-time progress & terminal logs."""
    def event_stream():
        client_queue = queue.Queue(maxsize=100)
        sse_queues.append(client_queue)
        try:
            # Send initial keepalive
            yield f"data: {json.dumps({'type': 'connected'})}\n\n"
            while True:
                msg = client_queue.get(timeout=30)
                yield msg
        except (GeneratorExit, queue.Empty):
            pass
        finally:
            if client_queue in sse_queues:
                sse_queues.remove(client_queue)

    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/api/leads", methods=["GET"])
@autenticacao.login_required
def list_leads():
    campaign_id = request.args.get("campaign_id", type=int)
    status_filter = request.args.get("status", "all")
    operator_filter = request.args.get("operator", "all")
    phone_type_filter = request.args.get("phone_type", "all")
    search = request.args.get("search", "")
    sort_by = request.args.get("sort_by", "score_desc")
    cnpj_filter = request.args.get("cnpj_filter", "all")

    leads = banco_dados.get_leads(
        campaign_id=campaign_id,
        status_filter=status_filter,
        operator_filter=operator_filter,
        phone_type_filter=phone_type_filter,
        cnpj_filter=cnpj_filter,
        search=search,
        sort_by=sort_by,
        limit=500
    )

    # Attach dynamic whatsapp URL and phone_type detection
    for lead in leads:
        clean_phone = lead.get("clean_phone") or gerador_propostas.clean_phone_number(lead.get("phone", ""))
        lead["whatsapp_url"] = (
            f"https://wa.me/{clean_phone}?text={gerador_propostas.urllib.parse.quote(lead.get('whatsapp_script') or '')}"
            if clean_phone else ""
        )
        if not lead.get("phone_type") or lead.get("phone_type") == "unknown":
            lead["phone_type"] = gerador_propostas.detect_phone_type(lead.get("phone", ""))

    if leads:
        try:
            servico_prints.prefetch(leads[:15], app.static_folder)
        except Exception:
            pass

    return jsonify({"success": True, "total": len(leads), "leads": leads})


@app.route("/api/kpis", methods=["GET"])
@autenticacao.login_required
def get_dashboard_kpis():
    campaign_id = request.args.get("campaign_id", type=int)
    kpis = banco_dados.get_kpis(campaign_id)

    # Calculate distribution for Chart 1 (Status Distribution)
    status_chart = {
        "labels": ["Sem Site (Prioridade Crítica)", "Precisa de Modernização", "Site Ativo (Baixa Prioridade)"],
        "data": [
            kpis["sem_site"],
            kpis["modernizacao"],
            max(0, kpis["total_leads"] - kpis["sem_site"] - kpis["modernizacao"]),
        ],
        "colors": ["#ef4444", "#f59e0b", "#10b981"]
    }

    # Fetch top leads for Maturity Scatter/Bubble chart
    all_leads = banco_dados.get_leads(campaign_id=campaign_id, limit=100)
    maturity_chart = []
    for l in all_leads:
        maturity_chart.append({
            "name": l["name"],
            "x": l["reviews_count"],   # Total de Avaliações
            "y": l["rating"],          # Nota do Google (0 a 5.0)
            "score": l["lead_score"],
            "status": l["qualification_status"],
            "temperature": l["lead_temperature"],
        })

    return jsonify({
        "success": True,
        "kpis": kpis,
        "status_chart": status_chart,
        "maturity_chart": maturity_chart,
    })


@app.route("/api/lead/<int:lead_id>/crm_status", methods=["POST"])
@autenticacao.login_required
def update_crm_status(lead_id):
    lead = banco_dados.get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"success": False, "error": "Lead não encontrado."}), 404

    user = autenticacao.get_current_user()
    if not autenticacao.can_edit_lead(user, lead):
        return jsonify({
            "success": False,
            "error": f"Acesso Negado: Este lead pertence a '{lead.get('assigned_to')}'. Apenas o responsável ou o Gestor podem editá-lo."
        }), 403

    data = request.get_json() or {}
    new_status = data.get("status", "Novo")
    notes = data.get("notes")

    # If lead was unassigned, assign to current user
    if not lead.get("assigned_to") or lead.get("assigned_to") in ["unassigned", "Sem Atribuição"]:
        banco_dados.assign_lead(lead_id, user["name"])

    banco_dados.update_lead_crm_status(lead_id, new_status, notes)
    banco_dados.add_log(f"Status do Lead #{lead_id} alterado para '{new_status}' por '{user['name']}'.", "INFO")
    broadcast_sse({
        "type": "lead_status_changed",
        "lead_id": lead_id,
        "new_status": new_status,
        "operator": user["name"],
        "assigned_to": lead.get("assigned_to") or user["name"]
    })
    return jsonify({"success": True, "lead_id": lead_id, "new_status": new_status})


@app.route("/api/leads/clear", methods=["POST"])
@autenticacao.admin_required
def clear_leads_api():
    user = autenticacao.get_current_user()
    banco_dados.clear_all_leads()
    try:
        servico_prints.clear_cache(app.static_folder)
    except Exception:
        pass
    banco_dados.add_log(f"Base de dados de leads limpa pelo administrador '{user['name']}'.", "WARNING")
    broadcast_sse({"type": "database_cleared", "operator": user["name"]})
    return jsonify({"success": True, "message": "Base de leads e histórico limpos com sucesso."})


@app.route("/api/lead/<int:lead_id>/schedule", methods=["POST"])
@autenticacao.login_required
def schedule_lead_meeting(lead_id):
    lead = banco_dados.get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"success": False, "error": "Lead não encontrado."}), 404

    user = autenticacao.get_current_user()
    if not autenticacao.can_edit_lead(user, lead):
        return jsonify({
            "success": False,
            "error": f"Acesso Negado: Este lead pertence a '{lead.get('assigned_to')}'. Apenas o responsável ou o Gestor podem agendar reuniões."
        }), 403

    data = request.get_json() or {}
    scheduled_at = data.get("scheduled_at", "").strip()
    meeting_notes = data.get("meeting_notes", "").strip()
    if not scheduled_at:
        return jsonify({"success": False, "error": "Informe data e horário do agendamento."}), 400

    banco_dados.schedule_meeting(lead_id, scheduled_at, meeting_notes)
    banco_dados.add_log(f"Reunião agendada para o Lead #{lead_id} em {scheduled_at} por '{user['name']}'.", "INFO")
    broadcast_sse({
        "type": "meeting_scheduled",
        "lead_id": lead_id,
        "lead_name": lead["name"],
        "scheduled_at": scheduled_at,
        "operator": user["name"]
    })
    return jsonify({"success": True, "lead_id": lead_id, "scheduled_at": scheduled_at})


@app.route("/api/lead/<int:lead_id>/unschedule", methods=["POST"])
@autenticacao.login_required
def unschedule_lead_meeting(lead_id):
    lead = banco_dados.get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"success": False, "error": "Lead não encontrado."}), 404

    user = autenticacao.get_current_user()
    if not autenticacao.can_edit_lead(user, lead):
        return jsonify({
            "success": False,
            "error": f"Acesso Negado: Este lead pertence a '{lead.get('assigned_to')}'."
        }), 403

    banco_dados.unschedule_meeting(lead_id)
    banco_dados.add_log(f"Reunião cancelada/removida para o Lead #{lead_id} por '{user['name']}'.", "INFO")
    broadcast_sse({
        "type": "meeting_unscheduled",
        "lead_id": lead_id,
        "lead_name": lead["name"],
        "operator": user["name"]
    })
    return jsonify({"success": True, "lead_id": lead_id, "message": "Reunião cancelada com sucesso."})


@app.route("/api/lead/<int:lead_id>/cnpj", methods=["GET", "POST"])
def enrich_lead_cnpj_api(lead_id):
    lead = banco_dados.get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"success": False, "error": "Lead não encontrado."}), 404

    force_refresh = request.method == "POST" or request.args.get("refresh") == "1"
    # If already cached and not forced, return cached CNPJ details
    if lead.get("cnpj") and not force_refresh:
        return jsonify({
            "success": True,
            "lead_id": lead_id,
            "lead_name": lead.get("name"),
            "data": {
                "cnpj": lead.get("cnpj"),
                "cnpj_formatted": lead.get("cnpj"),
                "razao_social": lead.get("cnpj_razao_social"),
                "situacao_cadastral": lead.get("cnpj_situacao"),
                "data_inicio_atividade": lead.get("cnpj_abertura"),
                "porte": lead.get("cnpj_porte"),
                "socios_str": lead.get("cnpj_socios"),
                "capital_social": lead.get("cnpj_capital"),
                "cnae_fiscal_descricao": lead.get("cnpj_cnae"),
                "regime": lead.get("cnpj_regime"),
            }
        })

    res = servico_cnpj.enrich_lead_cnpj(lead_id)
    return jsonify(res)


@app.route("/api/meetings", methods=["GET"])
def list_meetings():
    meetings = banco_dados.get_scheduled_meetings()
    for m in meetings:
        clean_phone = m.get("clean_phone") or gerador_propostas.clean_phone_number(m.get("phone", ""))
        m["whatsapp_url"] = (
            f"https://wa.me/{clean_phone}?text={gerador_propostas.urllib.parse.quote(m.get('whatsapp_script') or '')}"
            if clean_phone else ""
        )
    return jsonify({"success": True, "total": len(meetings), "meetings": meetings})



@app.route("/api/lead/<int:lead_id>/script", methods=["GET"])
def get_lead_script(lead_id):
    lead = banco_dados.get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"success": False, "error": "Lead não encontrado"}), 404

    clean_phone = lead.get("clean_phone") or gerador_propostas.clean_phone_number(lead.get("phone", ""))
    scripts = gerador_propostas.generate_scripts(lead, niche="sua área", city=lead.get("address", ""))
    notes = banco_dados.get_lead_notes(lead_id)

    return jsonify({
        "success": True,
        "lead": lead,
        "cold_call_script": lead.get("cold_call_script") or scripts["cold_call_script"],
        "whatsapp_script": lead.get("whatsapp_script") or scripts["whatsapp_script"],
        "whatsapp_followup_1": scripts["whatsapp_followup_1"],
        "whatsapp_followup_2": scripts["whatsapp_followup_2"],
        "whatsapp_url": scripts["whatsapp_url"],
        "followup_1_url": scripts["followup_1_url"],
        "followup_2_url": scripts["followup_2_url"],
        "proposal_text": scripts["proposal_text"],
        "phone_type": lead.get("phone_type") or scripts["phone_type"],
        "notes": notes,
    })


@app.route("/api/lead/<int:lead_id>/claim", methods=["POST"])
@autenticacao.login_required
def claim_lead_api(lead_id):
    user = autenticacao.get_current_user()
    lead = banco_dados.get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"success": False, "error": "Lead não encontrado."}), 404

    assigned = (lead.get("assigned_to") or "").strip()
    if assigned and assigned != user["name"] and user["permission_level"] != "ADMIN":
        return jsonify({"success": False, "error": f"Este lead já está atribuído a '{assigned}'."}), 403

    banco_dados.claim_lead(lead_id, user["name"])
    banco_dados.add_log(f"Lead #{lead_id} ({lead['name']}) assumido por '{user['name']}'.", "INFO")
    broadcast_sse({
        "type": "lead_claimed",
        "lead_id": lead_id,
        "lead_name": lead["name"],
        "assigned_to": user["name"]
    })
    return jsonify({"success": True, "lead_id": lead_id, "assigned_to": user["name"]})


@app.route("/api/lead/<int:lead_id>/assign", methods=["POST"])
@autenticacao.login_required
def assign_lead_api(lead_id):
    user = autenticacao.get_current_user()
    data = request.get_json() or {}
    operator = data.get("operator", "Jamilly").strip()

    lead = banco_dados.get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"success": False, "error": "Lead não encontrado."}), 404

    # If SDR tries to reassign someone else's lead, require ADMIN
    if user["permission_level"] != "ADMIN" and operator != user["name"] and not autenticacao.can_edit_lead(user, lead):
        return jsonify({"success": False, "error": "Acesso negado: Apenas gestores podem transferir leads de outros vendedores."}), 403

    banco_dados.assign_lead(lead_id, operator)
    banco_dados.add_log(f"Lead #{lead_id} atribuído ao operador '{operator}' por '{user['name']}'.", "INFO")
    broadcast_sse({
        "type": "lead_assigned",
        "lead_id": lead_id,
        "lead_name": lead["name"],
        "operator": operator,
        "assigned_by": user["name"]
    })
    return jsonify({"success": True, "lead_id": lead_id, "operator": operator})


@app.route("/api/leads/assign_bulk", methods=["POST"])
@autenticacao.admin_required
def assign_leads_bulk_api():
    user = autenticacao.get_current_user()
    data = request.get_json() or {}
    lead_ids = data.get("lead_ids", [])
    operator = data.get("operator", "Jamilly").strip()
    if not lead_ids:
        return jsonify({"success": False, "error": "Nenhum lead selecionado"}), 400

    banco_dados.assign_leads_bulk(lead_ids, operator)
    banco_dados.add_log(f"{len(lead_ids)} leads atribuídos a '{operator}' pelo gestor '{user['name']}'.", "INFO")
    broadcast_sse({
        "type": "leads_bulk_assigned",
        "lead_ids": lead_ids,
        "operator": operator,
        "assigned_by": user["name"]
    })
    return jsonify({"success": True, "count": len(lead_ids), "operator": operator})


@app.route("/api/lead/<int:lead_id>/notes", methods=["GET", "POST"])
@autenticacao.login_required
def lead_notes_api(lead_id):
    user = autenticacao.get_current_user()
    if request.method == "POST":
        lead = banco_dados.get_lead_by_id(lead_id)
        if not lead:
            return jsonify({"success": False, "error": "Lead não encontrado."}), 404

        if not autenticacao.can_edit_lead(user, lead):
            return jsonify({
                "success": False,
                "error": f"Acesso negado: Este lead pertence a '{lead.get('assigned_to')}'."
            }), 403

        data = request.get_json() or {}
        note_text = data.get("note_text", "").strip()
        if not note_text:
            return jsonify({"success": False, "error": "Texto da anotação vazio."}), 400

        note_id = banco_dados.add_lead_note(lead_id, note_text, user["name"])
        banco_dados.add_log(f"Nova anotação registrada no Lead #{lead_id} por '{user['name']}'.", "INFO")
        broadcast_sse({
            "type": "lead_note_added",
            "lead_id": lead_id,
            "operator": user["name"]
        })
        return jsonify({"success": True, "note_id": note_id})
    else:
        notes = banco_dados.get_lead_notes(lead_id)
        return jsonify({"success": True, "notes": notes})


@app.route("/api/operators", methods=["GET", "POST"])
@autenticacao.login_required
def operators_api():
    user = autenticacao.get_current_user()
    if request.method == "POST":
        if user["permission_level"] != "ADMIN":
            return jsonify({"success": False, "error": "Acesso negado: Apenas Gestores podem adicionar membros à equipe."}), 403

        data = request.get_json() or {}
        name = data.get("name", "").strip()
        role = data.get("role", "SDR / Closer").strip()
        permission_level = data.get("permission_level", "SDR").strip().upper()
        email = data.get("email", "").strip() or None
        password = data.get("password", "").strip()

        if not name:
            return jsonify({"success": False, "error": "Nome obrigatório."}), 400

        if email:
            existing = banco_dados.get_operator_by_email(email)
            if existing:
                return jsonify({"success": False, "error": "E-mail já cadastrado para outro membro."}), 400

        pwd_hash = autenticacao.hash_password(password) if password else None
        op_id = banco_dados.add_operator(name, role, permission_level, email, pwd_hash)
        banco_dados.add_log(f"Novo membro '{name}' ({permission_level}) adicionado à equipe por '{user['name']}'.", "INFO")
        return jsonify({"success": True, "id": op_id, "name": name, "role": role, "permission_level": permission_level, "email": email})
    else:
        ops = banco_dados.get_operators()
        return jsonify({"success": True, "operators": ops})


@app.route("/api/operator/<int:op_id>", methods=["PUT", "DELETE"])
@autenticacao.admin_required
def manage_operator_api(op_id):
    user = autenticacao.get_current_user()
    op = banco_dados.get_operator_by_id(op_id)
    if not op:
        return jsonify({"success": False, "error": "Membro não encontrado."}), 404

    if request.method == "DELETE":
        if user["id"] == op_id:
            return jsonify({"success": False, "error": "Você não pode desativar seu próprio usuário."}), 400
        banco_dados.deactivate_operator(op_id)
        banco_dados.add_log(f"Membro '{op['name']}' desativado da equipe por '{user['name']}'.", "WARNING")
        return jsonify({"success": True, "message": f"Membro '{op['name']}' desativado com sucesso."})

    # PUT: update operator
    data = request.get_json() or {}
    name = data.get("name", op["name"]).strip()
    role = data.get("role", op.get("role", "SDR")).strip()
    perm = data.get("permission_level", op.get("permission_level", "SDR")).strip().upper()
    email = data.get("email", op.get("email") or "").strip() or None
    new_password = data.get("password", "").strip()

    if email:
        existing = banco_dados.get_operator_by_email(email)
        if existing and existing["id"] != op_id:
            return jsonify({"success": False, "error": "Este e-mail já pertence a outro membro."}), 400

    pwd_hash = autenticacao.hash_password(new_password) if new_password else None
    banco_dados.update_operator(op_id, name, role, perm, email, pwd_hash)
    banco_dados.add_log(f"Dados do membro '{name}' atualizados por '{user['name']}'.", "INFO")
    return jsonify({"success": True, "message": "Membro atualizado com sucesso."})


@app.route("/api/meetings/today", methods=["GET"])
def todays_meetings_api():
    operator = request.args.get("operator", "all")
    meetings = banco_dados.get_todays_meetings(operator)
    return jsonify({"success": True, "total": len(meetings), "meetings": meetings})


@app.route("/lead/<int:lead_id>/proposal_print", methods=["GET"])
def proposal_print_view(lead_id):
    lead = banco_dados.get_lead_by_id(lead_id)
    if not lead:
        return "Lead não encontrado", 404

    lead_dict = dict(lead)
    raw_website = lead_dict.get("website") or ""
    clean_website = gerador_propostas.clean_site_display(raw_website)
    lead_dict["clean_website"] = clean_website

    scripts = gerador_propostas.generate_scripts(lead_dict, niche="sua área", city=lead.get("address", ""))
    return render_template(
        "proposal_print.html",
        lead=lead_dict,
        clean_website=clean_website,
        scripts=scripts,
        now_date=datetime.now().strftime("%d/%m/%Y"),
        user_base_address=gerador_propostas.USER_BASE_ADDRESS
    )


def resolve_google_ad_url(url: str) -> str:
    return gerador_propostas.resolve_google_ad_url(url)


@app.route("/api/lead/<int:lead_id>/screenshot", methods=["GET"])
def lead_screenshot_api(lead_id):
    lead = banco_dados.get_lead_by_id(lead_id)
    if not lead:
        return jsonify({"success": False, "error": "Lead não encontrado."}), 404

    force_refresh = request.args.get("refresh", "0") == "1"
    try:
        data = servico_prints.get_screenshot(lead, app.static_folder, force=force_refresh)
        return jsonify(data)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Erro ao capturar screenshot: {str(e)}",
            "lead_id": lead_id,
            "lead_name": lead.get("name"),
            "website": lead.get("website") or "Sem site cadastrado"
        }), 500


@app.route("/api/logs", methods=["GET"])
def get_logs():
    logs = banco_dados.get_recent_logs(limit=40)
    return jsonify({"success": True, "logs": logs})


@app.route("/api/export/excel", methods=["GET"])
def export_excel():
    campaign_id = request.args.get("campaign_id", type=int)
    leads = banco_dados.get_leads(campaign_id=campaign_id, limit=2000)

    if not leads:
        return "Nenhum lead disponível para exportação.", 400

    df_data = []
    for l in leads:
        clean_phone = l.get("clean_phone") or gerador_propostas.clean_phone_number(l.get("phone", ""))
        wp_link = f"https://wa.me/{clean_phone}" if clean_phone else ""
        df_data.append({
            "ID": l["id"],
            "Empresa": l["name"],
            "Telefone": l["phone"],
            "WhatsApp": wp_link,
            "Endereço": l["address"],
            "Nota Google": l["rating"],
            "Nº Avaliações": l["reviews_count"],
            "Website Cadastrado": l["website"],
            "Status de Qualificação": l["qualification_status"],
            "Diagnóstico Técnico": l["qualification_detail"],
            "Score (0-100)": l["lead_score"],
            "Temperatura": l["lead_temperature"],
            "Status CRM": l["crm_status"],
            "Script Cold Call": l["cold_call_script"],
            "Data Captação": l["created_at"],
        })

    df = pd.DataFrame(df_data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Leads Qualificados")
    output.seek(0)

    filename = f"leads_prospeccao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return send_file(
        output,
        download_name=filename,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route("/api/export/csv", methods=["GET"])
def export_csv():
    campaign_id = request.args.get("campaign_id", type=int)
    leads = banco_dados.get_leads(campaign_id=campaign_id, limit=2000)

    if not leads:
        return "Nenhum lead disponível para exportação.", 400

    df_data = []
    for l in leads:
        clean_phone = l.get("clean_phone") or gerador_propostas.clean_phone_number(l.get("phone", ""))
        df_data.append({
            "Empresa": l["name"],
            "Telefone": l["phone"],
            "WhatsApp": f"https://wa.me/{clean_phone}" if clean_phone else "",
            "Nota": l["rating"],
            "Avaliacoes": l["reviews_count"],
            "Website": l["website"],
            "Qualificacao": l["qualification_status"],
            "Diagnostico": l["qualification_detail"],
            "Lead Score": l["lead_score"],
            "Temperatura": l["lead_temperature"],
            "Status CRM": l["crm_status"],
        })

    df = pd.DataFrame(df_data)
    output = io.StringIO()
    # Write with UTF-8 SIG for correct opening in Excel Windows
    output.write("\ufeff")
    df.to_csv(output, index=False, sep=";")

    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8-sig"))
    mem.seek(0)

    filename = f"leads_prospeccao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(
        mem,
        download_name=filename,
        as_attachment=True,
        mimetype="text/csv"
    )


# ----------------------------------------------------
# RADAR DE CNPJS RECÉM-ABERTOS
# ----------------------------------------------------
@app.route("/api/radar_cnpj/scan", methods=["POST"])
@autenticacao.login_required
def api_radar_cnpj_scan():
    """Busca empresas recém-abertas por UF, Cidade e Nicho."""
    data = request.get_json() or {}
    uf = data.get("uf", "SP").strip()
    cidade = data.get("cidade", "Sorocaba").strip()
    nicho = data.get("nicho", "").strip()
    periodo_dias = int(data.get("periodo_dias", 90))
    limite = min(int(data.get("limite", 20)), 50)

    try:
        empresas = servico_radar_cnpj.escanear_cnpjs_recentes(
            uf=uf, cidade=cidade, nicho=nicho, periodo_dias=periodo_dias, limite=limite
        )
        return jsonify({
            "success": True,
            "total": len(empresas),
            "empresas": empresas,
            "parametros": {"uf": uf, "cidade": cidade, "nicho": nicho, "periodo_dias": periodo_dias}
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Erro no escaneamento de CNPJs: {str(e)}"}), 500


@app.route("/api/radar_cnpj/import", methods=["POST"])
@autenticacao.login_required
def api_radar_cnpj_import():
    """Importa uma empresa do radar de CNPJ diretamente para a Central de Leads."""
    data = request.get_json() or {}
    curr_user = autenticacao.get_current_user() or {}
    operator_name = curr_user.get("name") or "Jamilly"

    lead_data = {
        "name": data.get("razao_social") or data.get("nome_fantasia") or "Nova Empresa",
        "phone": data.get("phone") or "",
        "clean_phone": data.get("clean_phone") or "",
        "address": f"{data.get('logradouro', '')}, {data.get('bairro', '')} - {data.get('municipio', '')}/{data.get('uf', '')}".strip(", -/"),
        "rating": 5.0,
        "reviews_count": 0,
        "website": "",
        "maps_url": "",
        "qualification_status": "🚨 Nova Empresa: Sem Site",
        "qualification_detail": f"Empresa recém-aberta ({data.get('tag_tempo', 'Recém-Inaugurada')}). CNAE: {data.get('cnae', '')}",
        "lead_score": int(data.get("lead_score") or 95),
        "lead_temperature": data.get("lead_temperature") or "🔥 Super Quente",
        "assigned_to": operator_name,
        "cnpj": data.get("cnpj") or "",
        "cnpj_razao_social": data.get("razao_social") or "",
        "cnpj_situacao": data.get("situacao") or "ATIVA",
        "cnpj_abertura": data.get("data_abertura") or "",
        "cnpj_porte": data.get("porte") or "",
        "cnpj_socios": data.get("socios") or "",
        "cnpj_cnae": data.get("cnae") or "",
        "cnpj_regime": data.get("regime") or "",
        "lead_origin": "cnpj_novo",
        "cold_call_script": data.get("cold_call_script") or "",
        "whatsapp_script": data.get("whatsapp_script") or "",
    }

    try:
        lead_id = banco_dados.import_custom_lead(lead_data)
        banco_dados.add_lead_note(lead_id, operator_name, f"Importado via Radar de CNPJ Recém-Aberto ({data.get('tag_tempo', '')}).")
        broadcast_sse({
            "type": "lead_imported",
            "lead_id": lead_id,
            "origin": "cnpj_novo",
            "name": lead_data["name"],
            "operator": operator_name
        })
        return jsonify({"success": True, "lead_id": lead_id, "message": "Empresa importada para a Central de Leads com sucesso!"})
    except Exception as e:
        return jsonify({"success": False, "error": f"Erro ao importar lead: {str(e)}"}), 500


# ----------------------------------------------------
# AUDITOR DE PERFIS E LINKS NO INSTAGRAM
# ----------------------------------------------------
@app.route("/api/instagram/scan", methods=["POST"])
@autenticacao.login_required
def api_instagram_scan():
    """Busca e audita perfis do Instagram e seus links na bio."""
    data = request.get_json() or {}
    cidade = data.get("cidade", "Sorocaba").strip()
    nicho = data.get("nicho", "Dentista").strip()
    limite = min(int(data.get("limite", 15)), 40)

    try:
        perfis = servico_instagram.escanear_perfis_instagram(cidade=cidade, nicho=nicho, limite=limite)
        quebrados = sum(1 for p in perfis if p.get("link_categoria") == "quebrado")
        sem_link = sum(1 for p in perfis if p.get("link_categoria") in ["sem_link", "apenas_whatsapp", "linktree"])
        ativos = sum(1 for p in perfis if p.get("link_categoria") == "ativo")

        return jsonify({
            "success": True,
            "total": len(perfis),
            "stats": {
                "quebrados": quebrados,
                "sem_link_ou_linktree": sem_link,
                "ativos": ativos
            },
            "perfis": perfis,
            "parametros": {"cidade": cidade, "nicho": nicho}
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Erro na auditoria do Instagram: {str(e)}"}), 500


@app.route("/api/instagram/import", methods=["POST"])
@autenticacao.login_required
def api_instagram_import():
    """Importa um perfil do Instagram auditado diretamente para a Central de Leads."""
    data = request.get_json() or {}
    curr_user = autenticacao.get_current_user() or {}
    operator_name = curr_user.get("name") or "Jamilly"

    link_diag = data.get("link_diagnostico") or ""
    diag_cat = data.get("link_categoria") or "sem_link"
    qual_status = "🚨 Instagram: Link Quebrado" if diag_cat == "quebrado" else ("⚡ Instagram: Sem Site Próprio" if diag_cat in ["sem_link", "linktree", "apenas_whatsapp"] else "Instagram: Lead Qualificado")

    lead_data = {
        "name": data.get("nome") or data.get("handle") or "Perfil Instagram",
        "phone": data.get("phone") or "",
        "clean_phone": "".join(re.findall(r"\d", data.get("phone") or "")),
        "address": f"{data.get('cidade', '')} (Instagram @{data.get('handle_raw', '')})",
        "rating": 5.0,
        "reviews_count": 0,
        "website": data.get("link_bio") or "",
        "maps_url": data.get("instagram_url") or f"https://www.instagram.com/{data.get('handle_raw', '')}/",
        "qualification_status": qual_status,
        "qualification_detail": f"Instagram @{data.get('handle_raw', '')} | Diagnóstico do Link: {link_diag}. {data.get('link_detalhe', '')}",
        "lead_score": int(data.get("lead_score") or 95),
        "lead_temperature": "🔥 Crítico (Link Quebrado)" if diag_cat == "quebrado" else "Alta Prioridade",
        "assigned_to": operator_name,
        "lead_origin": "instagram",
        "instagram_handle": data.get("handle") or "",
        "link_bio": data.get("link_bio") or "",
        "link_bio_status": link_diag,
        "cold_call_script": data.get("cold_call_script") or "",
        "whatsapp_script": data.get("whatsapp_script") or "",
    }

    try:
        lead_id = banco_dados.import_custom_lead(lead_data)
        banco_dados.add_lead_note(lead_id, operator_name, f"Importado via Auditor Instagram ({data.get('handle', '')} - {link_diag}).")
        broadcast_sse({
            "type": "lead_imported",
            "lead_id": lead_id,
            "origin": "instagram",
            "name": lead_data["name"],
            "operator": operator_name
        })
        return jsonify({"success": True, "lead_id": lead_id, "message": "Perfil importado para a Central de Leads com sucesso!"})
    except Exception as e:
        return jsonify({"success": False, "error": f"Erro ao importar lead: {str(e)}"}), 500


if __name__ == "__main__":
    banco_dados.init_db()
    print("Iniciando Nexus Lead Pro em http://127.0.0.1:5000 ...")
    app.run(host="127.0.0.1", port=5000, debug=False)
