"""
Nexus Lead Pro - B2B Growth Engine & Lead Generation Dashboard.
Flask application server with SSE streaming, REST API, Chart data, and CRM actions.

"""

import os
import io
import json
import time
import queue
from datetime import datetime
from flask import Flask, render_template, request, jsonify, Response, send_file
import pandas as pd

import database
import scraper
import pitch_generator

app = Flask(__name__)
app.secret_key = "marq-lab-lead-secret-key"
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Queue for Server-Sent Events (SSE)
sse_queues = []


def sse_event_listener(data):
    """Callback for scraper events to broadcast to all open SSE connections."""
    msg = f"data: {json.dumps(data)}\n\n"
    for q in list(sse_queues):
        try:
            q.put_nowait(msg)
        except Exception:
            pass


# Register listener to active scraper
scraper.active_scraper.subscribers.append(sse_event_listener)


@app.route("/")
def index():
    database.init_db()
    return render_template("index.html")


@app.route("/api/scrape/start", methods=["POST"])
def start_scrape():
    data = request.get_json() or {}
    niche = data.get("niche", "").strip()
    city = data.get("city", "").strip()
    target_count = int(data.get("target_count") or 100)

    if not niche or not city:
        return jsonify({"success": False, "error": "Informe o Nicho e a Cidade para iniciar a busca."}), 400

    if scraper.active_scraper.is_running:
        return jsonify({"success": False, "error": "Uma extração já está em andamento. Aguarde ou clique em Parar."}), 400

    try:
        campaign_id = scraper.start_scraping(niche, city, target_count)
        return jsonify({
            "success": True,
            "campaign_id": campaign_id,
            "message": f"Mineração iniciada para '{niche}' em '{city}'. Meta: {target_count} leads."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/scrape/stop", methods=["POST"])
def stop_scrape():
    stopped = scraper.stop_scraping()
    return jsonify({"success": True, "stopped": stopped})


@app.route("/api/scrape/status", methods=["GET"])
def get_scrape_status():
    progress = 0
    if scraper.active_scraper.target_count > 0:
        progress = min(100, round((scraper.active_scraper.leads_count / scraper.active_scraper.target_count) * 100, 1))

    return jsonify({
        "is_running": scraper.active_scraper.is_running,
        "leads_count": scraper.active_scraper.leads_count,
        "target_count": scraper.active_scraper.target_count,
        "current_lead": scraper.active_scraper.current_lead_name,
        "status_message": scraper.active_scraper.status_message,
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
def list_leads():
    campaign_id = request.args.get("campaign_id", type=int)
    status_filter = request.args.get("status", "all")
    search = request.args.get("search", "")
    sort_by = request.args.get("sort_by", "score_desc")

    leads = database.get_leads(
        campaign_id=campaign_id,
        status_filter=status_filter,
        search=search,
        sort_by=sort_by,
        limit=500
    )

    # Attach dynamic whatsapp URL
    for lead in leads:
        clean_phone = lead.get("clean_phone") or pitch_generator.clean_phone_number(lead.get("phone", ""))
        lead["whatsapp_url"] = (
            f"https://wa.me/{clean_phone}?text={pitch_generator.urllib.parse.quote(lead.get('whatsapp_script') or '')}"
            if clean_phone else ""
        )

    return jsonify({"success": True, "total": len(leads), "leads": leads})


@app.route("/api/kpis", methods=["GET"])
def get_dashboard_kpis():
    campaign_id = request.args.get("campaign_id", type=int)
    kpis = database.get_kpis(campaign_id)

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
    all_leads = database.get_leads(campaign_id=campaign_id, limit=100)
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
def update_crm_status(lead_id):
    data = request.get_json() or {}
    new_status = data.get("status", "Novo")
    notes = data.get("notes")
    database.update_lead_crm_status(lead_id, new_status, notes)
    database.add_log(f"Status do Lead #{lead_id} alterado para '{new_status}'.", "INFO")
    return jsonify({"success": True, "lead_id": lead_id, "new_status": new_status})


@app.route("/api/leads/clear", methods=["POST"])
def clear_leads_api():
    database.clear_all_leads()
    database.add_log("Base de dados de leads limpa com sucesso.", "INFO")
    return jsonify({"success": True, "message": "Base de leads e histórico limpos com sucesso."})


@app.route("/api/lead/<int:lead_id>/schedule", methods=["POST"])
def schedule_lead_meeting(lead_id):
    data = request.get_json() or {}
    scheduled_at = data.get("scheduled_at", "").strip()
    meeting_notes = data.get("meeting_notes", "").strip()
    if not scheduled_at:
        return jsonify({"success": False, "error": "Informe data e horário do agendamento."}), 400

    database.schedule_meeting(lead_id, scheduled_at, meeting_notes)
    database.add_log(f"Reunião agendada para o Lead #{lead_id} em {scheduled_at}.", "INFO")
    return jsonify({"success": True, "lead_id": lead_id, "scheduled_at": scheduled_at})


@app.route("/api/meetings", methods=["GET"])
def list_meetings():
    meetings = database.get_scheduled_meetings()
    for m in meetings:
        clean_phone = m.get("clean_phone") or pitch_generator.clean_phone_number(m.get("phone", ""))
        m["whatsapp_url"] = (
            f"https://wa.me/{clean_phone}?text={pitch_generator.urllib.parse.quote(m.get('whatsapp_script') or '')}"
            if clean_phone else ""
        )
    return jsonify({"success": True, "total": len(meetings), "meetings": meetings})



@app.route("/api/lead/<int:lead_id>/script", methods=["GET"])
def get_lead_script(lead_id):
    leads = database.get_leads(limit=1000)
    lead = next((l for l in leads if l["id"] == lead_id), None)
    if not lead:
        return jsonify({"success": False, "error": "Lead não encontrado"}), 404

    clean_phone = lead.get("clean_phone") or pitch_generator.clean_phone_number(lead.get("phone", ""))
    whatsapp_url = (
        f"https://wa.me/{clean_phone}?text={pitch_generator.urllib.parse.quote(lead.get('whatsapp_script') or '')}"
        if clean_phone else ""
    )

    return jsonify({
        "success": True,
        "lead": lead,
        "cold_call_script": lead.get("cold_call_script"),
        "whatsapp_script": lead.get("whatsapp_script"),
        "whatsapp_url": whatsapp_url,
    })


@app.route("/api/logs", methods=["GET"])
def get_logs():
    logs = database.get_recent_logs(limit=40)
    return jsonify({"success": True, "logs": logs})


@app.route("/api/export/excel", methods=["GET"])
def export_excel():
    campaign_id = request.args.get("campaign_id", type=int)
    leads = database.get_leads(campaign_id=campaign_id, limit=2000)

    if not leads:
        return "Nenhum lead disponível para exportação.", 400

    df_data = []
    for l in leads:
        clean_phone = l.get("clean_phone") or pitch_generator.clean_phone_number(l.get("phone", ""))
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
    leads = database.get_leads(campaign_id=campaign_id, limit=2000)

    if not leads:
        return "Nenhum lead disponível para exportação.", 400

    df_data = []
    for l in leads:
        clean_phone = l.get("clean_phone") or pitch_generator.clean_phone_number(l.get("phone", ""))
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


if __name__ == "__main__":
    database.init_db()
    print("Iniciando Nexus Lead Pro em http://127.0.0.1:5000 ...")
    app.run(host="127.0.0.1", port=5000, debug=False)
