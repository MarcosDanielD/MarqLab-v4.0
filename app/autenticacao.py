"""
Authentication & Authorization Module for Marq Lab.
Handles password hashing, session checking, and role-based permissions.
"""

from functools import wraps
from typing import Optional, Dict, Any
from flask import session, request, redirect, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

import banco_dados


def hash_password(password: str) -> str:
    """Returns secure hash of a password."""
    return generate_password_hash(password.strip())


def verify_password(password: str, hash_val: str) -> bool:
    """Verifies plaintext password against a hash."""
    if not hash_val:
        return False
    return check_password_hash(hash_val, password.strip())


def authenticate(identifier: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Authenticates an operator by e-mail or username.
    Returns operator dictionary if successful, None otherwise.
    """
    clean_id = (identifier or "").strip()
    if not clean_id or not password:
        return None

    # Check by email first
    op = banco_dados.get_operator_by_email(clean_id)
    # If not found by email, check by name
    if not op:
        op = banco_dados.get_operator_by_name(clean_id)

    if not op:
        return None

    pwd_hash = op.get("password_hash")
    if not pwd_hash:
        return None

    if verify_password(password, pwd_hash):
        banco_dados.touch_operator_login(op["id"])
        # Do not leak hash
        op_dict = dict(op)
        op_dict.pop("password_hash", None)
        return op_dict

    return None


def get_current_user() -> Optional[Dict[str, Any]]:
    """Retrieves current logged in user from Flask session."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    op = banco_dados.get_operator_by_id(user_id)
    if op and op.get("active") == 1:
        op_dict = dict(op)
        op_dict.pop("password_hash", None)
        return op_dict
    return None


def login_required(f):
    """Decorator to protect routes requiring authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            # If API request, return 401 JSON
            if request.path.startswith("/api/"):
                return jsonify({
                    "success": False,
                    "error": "Sessão expirada ou não autenticado.",
                    "unauthenticated": True
                }), 401
            # If web view, redirect to /login
            return redirect(url_for("login_view", next=request.path))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to protect routes requiring ADMIN privileges."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.path.startswith("/api/"):
                return jsonify({
                    "success": False,
                    "error": "Não autenticado.",
                    "unauthenticated": True
                }), 401
            return redirect(url_for("login_view"))

        if user.get("permission_level") != "ADMIN":
            if request.path.startswith("/api/"):
                return jsonify({
                    "success": False,
                    "error": "Acesso negado: Apenas administradores/gestores podem executar esta ação."
                }), 403
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated_function


def can_edit_lead(user: Dict[str, Any], lead: Dict[str, Any]) -> bool:
    """
    Checks if user is authorized to edit a lead.
    Rule: Admin can edit any lead. SDR can edit leads assigned to them or unassigned leads.
    """
    if not user:
        return False
    if user.get("permission_level") == "ADMIN":
        return True
    
    assigned = (lead.get("assigned_to") or "").strip()
    user_name = (user.get("name") or "").strip()

    # If lead is unassigned or assigned to current user
    if not assigned or assigned.lower() in ["unassigned", "sem atribuição", "ninguém"]:
        return True
    
    return assigned.lower() == user_name.lower()
