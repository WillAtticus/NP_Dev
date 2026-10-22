"""Local-only account primitives for the NeuroPulse workstation service."""
import base64
import hashlib
import hmac
import os
import secrets
from datetime import timedelta
from typing import Tuple

from sqlalchemy.orm import Session

try:
    from ..db.models import AuthSession, LocalUser
    from ..db.timeutils import utcnow_naive
except ImportError:
    from backend.app.db.models import AuthSession, LocalUser
    from backend.app.db.timeutils import utcnow_naive


ROLES = {"admin", "operator", "researcher", "reviewer", "kiosk"}
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
TOKEN_TTL_MINUTES = int(os.environ.get("NEUROPULSE_SESSION_TTL_MINUTES", "480"))
if not 5 <= TOKEN_TTL_MINUTES <= 1440:
    raise RuntimeError("NEUROPULSE_SESSION_TTL_MINUTES must be between 5 and 1440.")


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 256:
        raise ValueError("Password must contain 12 to 256 characters.")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=64)
    return "$".join(("scrypt", str(SCRYPT_N), str(SCRYPT_R), str(SCRYPT_P),
                     base64.urlsafe_b64encode(salt).decode("ascii"),
                     base64.urlsafe_b64encode(digest).decode("ascii")))


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = encoded.split("$", 5)
        if scheme != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_b64.encode("ascii"))
        actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, UnicodeError):
        return False


def issue_session(db: Session, user: LocalUser, ttl_minutes: int = TOKEN_TTL_MINUTES) -> Tuple[str, AuthSession]:
    token = secrets.token_urlsafe(32)
    now = utcnow_naive()
    session = AuthSession(
        id=secrets.token_hex(16), user_id=user.id,
        token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
        created_at=now, expires_at=now + timedelta(minutes=ttl_minutes),
    )
    db.add(session)
    db.commit()
    return token, session


def resolve_session(db: Session, token: str) -> LocalUser | None:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    session = db.query(AuthSession).filter(
        AuthSession.token_hash == token_hash,
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > utcnow_naive(),
    ).first()
    if not session:
        return None
    user = db.query(LocalUser).filter(LocalUser.id == session.user_id).first()
    return user if user and user.is_active else None


def revoke_session(db: Session, token: str) -> bool:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    session = db.query(AuthSession).filter(AuthSession.token_hash == token_hash, AuthSession.revoked_at.is_(None)).first()
    if not session:
        return False
    session.revoked_at = utcnow_naive()
    db.commit()
    return True
