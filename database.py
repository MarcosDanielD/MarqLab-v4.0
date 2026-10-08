"""
Database layer for Nexus Lead Pro (B2B Lead Generation & Qualification System).
Manages SQLite persistence, campaigns, leads, logs, and CRM status updates.
"""

import os
import sqlite3
import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nexus_leads.db")


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Campaigns table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            niche TEXT NOT NULL,
            city TEXT NOT NULL,
            target_count INTEGER DEFAULT 100,
            total_found INTEGER DEFAULT 0,
            without_site_count INTEGER DEFAULT 0,
            need_modernization_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Leads table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            name TEXT NOT NULL,
            phone TEXT,
            clean_phone TEXT,
            address TEXT,
            rating REAL DEFAULT 0.0,
            reviews_count INTEGER DEFAULT 0,
            website TEXT,
            maps_url TEXT,
            qualification_status TEXT NOT NULL,
            qualification_detail TEXT,
            lead_score INTEGER DEFAULT 50,
            lead_temperature TEXT DEFAULT 'Alta Prioridade',
            crm_status TEXT DEFAULT 'Novo',
            notes TEXT,
            scheduled_at TEXT,
            meeting_notes TEXT,
            cold_call_script TEXT,
            whatsapp_script TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
        )
    """)

    # Migration check for existing DB
    cursor.execute("PRAGMA table_info(leads)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    if "scheduled_at" not in existing_cols:
        cursor.execute("ALTER TABLE leads ADD COLUMN scheduled_at TEXT")
    if "meeting_notes" not in existing_cols:
        cursor.execute("ALTER TABLE leads ADD COLUMN meeting_notes TEXT")
    if "assigned_to" not in existing_cols:
        cursor.execute("ALTER TABLE leads ADD COLUMN assigned_to TEXT DEFAULT 'Jamilly'")
        cursor.execute("UPDATE leads SET assigned_to = 'Jamilly' WHERE assigned_to IS NULL")
    if "phone_type" not in existing_cols:
        cursor.execute("ALTER TABLE leads ADD COLUMN phone_type TEXT DEFAULT 'unknown'")

    # Table: Lead Notes / CRM Interaction History
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lead_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            operator_name TEXT DEFAULT 'Jamilly',
            note_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE
        )
    """)

    # Table: Operators / SDR Team
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            role TEXT DEFAULT 'SDR / Closer',
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO operators (name, role) VALUES ('Jamilly', 'SDR / Closer')")
    cursor.execute("INSERT OR IGNORE INTO operators (name, role) VALUES ('Marcos', 'Gestor de Vendas')")

    # Activity and Scraping Logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER,
            level TEXT DEFAULT 'INFO',
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Update existing phone_types if missing
    cursor.execute("SELECT id, phone FROM leads WHERE phone_type IS NULL OR phone_type = 'unknown' OR phone_type = ''")
    rows_to_update = cursor.fetchall()
    if rows_to_update:
        import pitch_generator
        for r in rows_to_update:
            ptype = pitch_generator.detect_phone_type(r["phone"])
            cursor.execute("UPDATE leads SET phone_type = ? WHERE id = ?", (ptype, r["id"]))

    conn.commit()
    conn.close()






def create_campaign(niche: str, city: str, target_count: int = 100) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO campaigns (niche, city, target_count, status, created_at, updated_at)
        VALUES (?, ?, ?, 'running', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (niche, city, target_count),
    )
    campaign_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return campaign_id


def update_campaign_status(campaign_id: int, status: str, total_found: int = None,
                           without_site: int = None, modernization: int = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = ["status = ?", "updated_at = CURRENT_TIMESTAMP"]
    params = [status]

    if total_found is not None:
        updates.append("total_found = ?")
        params.append(total_found)
    if without_site is not None:
        updates.append("without_site_count = ?")
        params.append(without_site)
    if modernization is not None:
        updates.append("need_modernization_count = ?")
        params.append(modernization)

    params.append(campaign_id)
    sql = f"UPDATE campaigns SET {', '.join(updates)} WHERE id = ?"
    cursor.execute(sql, params)
    conn.commit()
    conn.close()


def save_lead(lead_data: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if lead already exists by name and phone in the campaign or overall
    cursor.execute(
        "SELECT id FROM leads WHERE name = ? AND (phone = ? OR (phone IS NULL AND ? IS NULL))",
        (lead_data.get("name"), lead_data.get("phone"), lead_data.get("phone")),
    )
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return existing["id"]

    import pitch_generator
    phone_type = lead_data.get("phone_type") or pitch_generator.detect_phone_type(lead_data.get("phone", ""))
    assigned_to = lead_data.get("assigned_to") or "Jamilly"

    cursor.execute(
        """
        INSERT INTO leads (
            campaign_id, name, phone, clean_phone, address, rating, reviews_count,
            website, maps_url, qualification_status, qualification_detail,
            lead_score, lead_temperature, crm_status, notes,
            assigned_to, phone_type,
            cold_call_script, whatsapp_script, created_at
        ) VALUES (
            :campaign_id, :name, :phone, :clean_phone, :address, :rating, :reviews_count,
            :website, :maps_url, :qualification_status, :qualification_detail,
            :lead_score, :lead_temperature, :crm_status, :notes,
            :assigned_to, :phone_type,
            :cold_call_script, :whatsapp_script, CURRENT_TIMESTAMP
        )
        """,
        {
            "campaign_id": lead_data.get("campaign_id"),
            "name": lead_data.get("name"),
            "phone": lead_data.get("phone", ""),
            "clean_phone": lead_data.get("clean_phone", ""),
            "address": lead_data.get("address", ""),
            "rating": float(lead_data.get("rating") or 0.0),
            "reviews_count": int(lead_data.get("reviews_count") or 0),
            "website": lead_data.get("website", ""),
            "maps_url": lead_data.get("maps_url", ""),
            "qualification_status": lead_data.get("qualification_status", "Prioridade Crítica: Sem Site"),
            "qualification_detail": lead_data.get("qualification_detail", ""),
            "lead_score": int(lead_data.get("lead_score") or 50),
            "lead_temperature": lead_data.get("lead_temperature", "Alta Prioridade"),
            "crm_status": lead_data.get("crm_status", "Novo"),
            "notes": lead_data.get("notes", ""),
            "assigned_to": assigned_to,
            "phone_type": phone_type,
            "cold_call_script": lead_data.get("cold_call_script", ""),
            "whatsapp_script": lead_data.get("whatsapp_script", ""),
        },
    )
    lead_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return lead_id


def update_lead_crm_status(lead_id: int, crm_status: str, notes: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # If explicitly cancelling meeting or marking as Perdido, clear from scheduled agenda
    if crm_status in ["Cancelar Reunião", "Remover da Agenda"]:
        cursor.execute(
            "UPDATE leads SET crm_status = 'Contatado', scheduled_at = NULL, meeting_notes = NULL WHERE id = ?",
            (lead_id,)
        )
    elif crm_status in ["Perdido", "Novo"]:
        if notes is not None:
            cursor.execute("UPDATE leads SET crm_status = ?, notes = ?, scheduled_at = NULL, meeting_notes = NULL WHERE id = ?", (crm_status, notes, lead_id))
        else:
            cursor.execute("UPDATE leads SET crm_status = ?, scheduled_at = NULL, meeting_notes = NULL WHERE id = ?", (crm_status, lead_id))
    else:
        if notes is not None:
            cursor.execute("UPDATE leads SET crm_status = ?, notes = ? WHERE id = ?", (crm_status, notes, lead_id))
        else:
            cursor.execute("UPDATE leads SET crm_status = ? WHERE id = ?", (crm_status, lead_id))
            
    conn.commit()
    conn.close()



def add_log(message: str, level: str = "INFO", campaign_id: Optional[int] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO activity_logs (campaign_id, level, message, timestamp) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
        (campaign_id, level, message),
    )
    conn.commit()
    conn.close()


def get_recent_logs(limit: int = 50, campaign_id: Optional[int] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    if campaign_id:
        cursor.execute(
            "SELECT * FROM activity_logs WHERE campaign_id = ? ORDER BY id DESC LIMIT ?",
            (campaign_id, limit),
        )
    else:
        cursor.execute(
            "SELECT * FROM activity_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_leads(campaign_id: Optional[int] = None,
              status_filter: Optional[str] = None,
              operator_filter: Optional[str] = None,
              phone_type_filter: Optional[str] = None,
              search: Optional[str] = None,
              sort_by: Optional[str] = None,
              limit: int = 500) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM leads WHERE 1=1"
    params = []

    if campaign_id:
        query += " AND campaign_id = ?"
        params.append(campaign_id)

    if status_filter and status_filter != "all":
        if status_filter == "sem_site":
            query += " AND qualification_status LIKE '%Sem Site%'"
        elif status_filter == "modernizacao":
            query += " AND qualification_status LIKE '%Modernização%'"
        elif status_filter == "site_ativo":
            query += " AND qualification_status LIKE '%Site Ativo%'"
        elif status_filter == "quentes":
            query += " AND lead_score >= 80"
        elif status_filter in ["Novo", "Contatado", "Em Negociação", "Fechado (R$ 1.000)", "Perdido"]:
            query += " AND crm_status = ?"
            params.append(status_filter)

    if operator_filter and operator_filter != "all":
        if operator_filter == "unassigned":
            query += " AND (assigned_to IS NULL OR assigned_to = '')"
        else:
            query += " AND assigned_to = ?"
            params.append(operator_filter)

    if phone_type_filter and phone_type_filter != "all":
        query += " AND phone_type = ?"
        params.append(phone_type_filter)

    if search:
        search_param = f"%{search.strip()}%"
        query += " AND (name LIKE ? OR phone LIKE ? OR address LIKE ? OR website LIKE ? OR notes LIKE ?)"
        params.extend([search_param, search_param, search_param, search_param, search_param])

    # Sorting
    if sort_by == "score_desc":
        query += " ORDER BY lead_score DESC, reviews_count DESC"
    elif sort_by == "reviews_desc":
        query += " ORDER BY reviews_count DESC, rating DESC"
    elif sort_by == "rating_desc":
        query += " ORDER BY rating DESC, reviews_count DESC"
    elif sort_by == "name_asc":
        query += " ORDER BY name ASC"
    else:
        query += " ORDER BY id DESC"

    query += " LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    leads = []
    for r in rows:
        lead_dict = dict(r)
        # Fetch latest note for fast preview
        cursor.execute("SELECT note_text, operator_name, created_at FROM lead_notes WHERE lead_id = ? ORDER BY id DESC LIMIT 1", (lead_dict["id"],))
        last_note = cursor.fetchone()
        lead_dict["latest_note"] = dict(last_note) if last_note else None
        
        cursor.execute("SELECT COUNT(*) as total FROM lead_notes WHERE lead_id = ?", (lead_dict["id"],))
        lead_dict["notes_count"] = cursor.fetchone()["total"]
        leads.append(lead_dict)

    conn.close()
    return leads


def get_kpis(campaign_id: Optional[int] = None) -> Dict[str, Any]:
    conn = get_db_connection()
    cursor = conn.cursor()

    base_where = "WHERE campaign_id = ?" if campaign_id else "WHERE 1=1"
    params = [campaign_id] if campaign_id else []

    cursor.execute(f"SELECT COUNT(*) as total FROM leads {base_where}", params)
    total_leads = cursor.fetchone()["total"]

    cursor.execute(f"SELECT COUNT(*) as total FROM leads {base_where} AND qualification_status LIKE '%Sem Site%'", params)
    sem_site = cursor.fetchone()["total"]

    cursor.execute(f"SELECT COUNT(*) as total FROM leads {base_where} AND qualification_status LIKE '%Modernização%'", params)
    modernizacao = cursor.fetchone()["total"]

    cursor.execute(f"SELECT COUNT(*) as total FROM leads {base_where} AND lead_score >= 80", params)
    leads_super_quentes = cursor.fetchone()["total"]

    cursor.execute(f"SELECT COUNT(*) as total FROM leads {base_where} AND crm_status = 'Fechado (R$ 1.000)'", params)
    fechados = cursor.fetchone()["total"]

    cursor.execute(f"SELECT COUNT(*) as total FROM leads {base_where} AND phone IS NOT NULL AND phone != ''", params)
    com_telefone = cursor.fetchone()["total"]

    # Projeção de Faturamento:
    # Métrica base: 1 fechamento = R$ 1.000.
    # Taxa conservadora de conversão de leads qualificados sem site/site ruim: ~5% a 10%
    faturamento_realizado = fechados * 1000
    estimativa_fechamentos = max(1, round((sem_site + modernizacao) * 0.05)) if (sem_site + modernizacao) > 0 else 0
    projecao_faturamento = (fechados + estimativa_fechamentos) * 1000

    conn.close()

    return {
        "total_leads": total_leads,
        "sem_site": sem_site,
        "modernizacao": modernizacao,
        "leads_super_quentes": leads_super_quentes,
        "com_telefone": com_telefone,
        "fechados": fechados,
        "faturamento_realizado": faturamento_realizado,
        "projecao_faturamento": projecao_faturamento,
        "ticket_medio": 1000,
    }


def get_campaigns() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM campaigns ORDER BY id DESC LIMIT 20")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def schedule_meeting(lead_id: int, scheduled_at: str, meeting_notes: Optional[str] = None):
    """Schedules a client meeting and updates CRM status to 'Reunião Agendada'."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE leads
        SET scheduled_at = ?,
            meeting_notes = ?,
            crm_status = 'Reunião Agendada'
        WHERE id = ?
        """,
        (scheduled_at, meeting_notes or "", lead_id)
    )
    conn.commit()
    conn.close()


def get_scheduled_meetings() -> List[Dict[str, Any]]:
    """Returns all leads that have an appointment/meeting scheduled."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM leads
        WHERE scheduled_at IS NOT NULL AND scheduled_at != ''
        ORDER BY scheduled_at ASC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def unschedule_meeting(lead_id: int):
    """Removes a scheduled meeting from a lead and resets its status."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE leads
        SET scheduled_at = NULL,
            meeting_notes = NULL,
            crm_status = 'Contatado'
        WHERE id = ?
        """,
        (lead_id,)
    )
    conn.commit()
    conn.close()


def clear_all_leads():
    """Wipes all leads, activity logs and campaigns for a fresh start."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM leads")
    cursor.execute("DELETE FROM lead_notes")
    cursor.execute("DELETE FROM activity_logs")
    cursor.execute("DELETE FROM campaigns")
    conn.commit()
    conn.close()


def get_lead_by_id(lead_id: int) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads WHERE id = ?", (lead_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_lead_note(lead_id: int, note_text: str, operator_name: str = "Jamilly") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO lead_notes (lead_id, operator_name, note_text) VALUES (?, ?, ?)",
        (lead_id, operator_name, note_text.strip()),
    )
    cursor.execute(
        "UPDATE leads SET notes = ? WHERE id = ?",
        (f"[{operator_name}] {note_text.strip()}", lead_id),
    )
    note_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return note_id


def get_lead_notes(lead_id: int) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM lead_notes WHERE lead_id = ? ORDER BY id DESC",
        (lead_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_operators() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM operators WHERE active = 1 ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_operator(name: str, role: str = "SDR / Closer") -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO operators (name, role) VALUES (?, ?)", (name.strip(), role.strip()))
    op_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return op_id


def assign_lead(lead_id: int, operator_name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE leads SET assigned_to = ? WHERE id = ?", (operator_name, lead_id))
    conn.commit()
    conn.close()


def assign_leads_bulk(lead_ids: List[int], operator_name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    for lid in lead_ids:
        cursor.execute("UPDATE leads SET assigned_to = ? WHERE id = ?", (operator_name, lid))
    conn.commit()
    conn.close()


def get_todays_meetings(operator_name: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    where = "WHERE scheduled_at LIKE ? AND scheduled_at IS NOT NULL"
    params = [f"%{today_str}%"]

    if operator_name and operator_name != "all":
        where += " AND (assigned_to = ? OR assigned_to IS NULL)"
        params.append(operator_name)

    cursor.execute(f"SELECT * FROM leads {where} ORDER BY scheduled_at ASC", params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]



