from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

REGISTRY_VERSION = "participant-registry-2.0"
REGISTRY_PATH = Path(__file__).resolve().parent / "participant_registry.sqlite3"

PBKDF2_ITERATIONS = 220_000
MAX_FAILED_ATTEMPTS = 5
FAILED_ATTEMPT_LOCK_MINUTES = 10
ACTIVE_SESSION_TTL_HOURS = 4

ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class RegistryError(Exception):
    pass


class InvalidCredentialsError(RegistryError):
    pass


class ParticipantInactiveError(RegistryError):
    pass


class ParticipantLockedError(RegistryError):
    pass


class ActiveSessionError(RegistryError):
    pass


@dataclass(frozen=True)
class ParticipantStatus:
    participant_id: str
    active: bool
    created_utc: str
    failed_attempts: int
    lockout_until_utc: str
    active_session_started_utc: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None) -> str:
    return dt.isoformat(timespec="seconds") if dt else ""


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def normalize_participant_id(value: str) -> str:
    value = (value or "").strip().upper()
    if not value:
        raise ValueError("Participant ID is required.")
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if len(value) < 3 or len(value) > 32 or any(ch not in allowed for ch in value):
        raise ValueError(
            "Participant ID must be 3–32 characters using only letters, numbers, '-' or '_'."
        )
    return value


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(REGISTRY_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def initialize_registry() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS participants (
                participant_id TEXT PRIMARY KEY,
                salt BLOB NOT NULL,
                access_hash BLOB NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_utc TEXT NOT NULL,
                last_code_reset_utc TEXT NOT NULL,
                failed_attempts INTEGER NOT NULL DEFAULT 0,
                lockout_until_utc TEXT NOT NULL DEFAULT '',
                active_session_token TEXT NOT NULL DEFAULT '',
                active_session_started_utc TEXT NOT NULL DEFAULT ''
            )
            """
        )


def _hash_code(code: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        (code or "").encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )


def _generate_access_code(length: int = 10) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def create_participant(participant_id: str, access_code: str | None = None) -> str:
    initialize_registry()
    pid = normalize_participant_id(participant_id)
    code = (access_code or _generate_access_code()).strip().upper()
    if len(code) < 8:
        raise ValueError("Access code must contain at least 8 characters.")

    salt = secrets.token_bytes(16)
    digest = _hash_code(code, salt)
    now = iso(utc_now())

    try:
        with _connect() as conn:
            conn.execute(
                """
                INSERT INTO participants (
                    participant_id, salt, access_hash, active, created_utc,
                    last_code_reset_utc, failed_attempts, lockout_until_utc,
                    active_session_token, active_session_started_utc
                ) VALUES (?, ?, ?, 1, ?, ?, 0, '', '', '')
                """,
                (pid, salt, digest, now, now),
            )
    except sqlite3.IntegrityError as exc:
        raise RegistryError(
            f"Participant ID {pid!r} already exists. Use a different ID; "
            "do not create a second participant with the same ID."
        ) from exc
    return code



def create_auto_participant() -> tuple[str, str]:
    """Create a collision-resistant pseudonymous Participant ID and access code.

    Returns (participant_id, plaintext_access_code). The plaintext access code is
    shown to the participant once; only its salted hash is stored.
    """
    initialize_registry()

    # Random, non-sequential IDs avoid exposing enrollment order/participant count.
    for _ in range(100):
        participant_id = "P" + "".join(secrets.choice(ALPHABET) for _ in range(7))
        access_code = _generate_access_code()
        try:
            create_participant(participant_id, access_code)
            return participant_id, access_code
        except RegistryError:
            # Extremely unlikely random collision; simply try a new ID.
            continue

    raise RegistryError("Could not allocate a unique Participant ID. Please try again.")

def reset_access_code(participant_id: str) -> str:
    initialize_registry()
    pid = normalize_participant_id(participant_id)
    code = _generate_access_code()
    salt = secrets.token_bytes(16)
    digest = _hash_code(code, salt)
    now = iso(utc_now())

    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE participants
            SET salt=?, access_hash=?, last_code_reset_utc=?,
                failed_attempts=0, lockout_until_utc=''
            WHERE participant_id=?
            """,
            (salt, digest, now, pid),
        )
        if cur.rowcount != 1:
            raise RegistryError(f"Unknown participant ID: {pid}")
    return code


def set_participant_active(participant_id: str, active: bool) -> None:
    initialize_registry()
    pid = normalize_participant_id(participant_id)
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE participants SET active=? WHERE participant_id=?",
            (1 if active else 0, pid),
        )
        if cur.rowcount != 1:
            raise RegistryError(f"Unknown participant ID: {pid}")


def force_unlock(participant_id: str) -> None:
    initialize_registry()
    pid = normalize_participant_id(participant_id)
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE participants
            SET active_session_token='', active_session_started_utc=''
            WHERE participant_id=?
            """,
            (pid,),
        )
        if cur.rowcount != 1:
            raise RegistryError(f"Unknown participant ID: {pid}")


def list_participants() -> list[ParticipantStatus]:
    initialize_registry()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT participant_id, active, created_utc, failed_attempts,
                   lockout_until_utc, active_session_started_utc
            FROM participants
            ORDER BY participant_id
            """
        ).fetchall()
    return [
        ParticipantStatus(
            participant_id=r["participant_id"],
            active=bool(r["active"]),
            created_utc=r["created_utc"],
            failed_attempts=int(r["failed_attempts"]),
            lockout_until_utc=r["lockout_until_utc"],
            active_session_started_utc=r["active_session_started_utc"],
        )
        for r in rows
    ]


def authenticate_and_acquire_session(
    participant_id: str,
    access_code: str,
    session_token: str,
) -> str:
    """Verify credentials and atomically acquire an active-session lock.

    Returns the canonical participant ID. The access code is never returned or
    written into assessment results.
    """
    initialize_registry()
    pid = normalize_participant_id(participant_id)
    code = (access_code or "").strip().upper()
    now = utc_now()

    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT * FROM participants WHERE participant_id=?",
            (pid,),
        ).fetchone()

        # Generic failure avoids confirming whether an arbitrary ID exists.
        if row is None:
            raise InvalidCredentialsError("Participant ID or access code is not recognized.")

        if not bool(row["active"]):
            raise ParticipantInactiveError(
                "This participant ID is inactive. Ask the researcher for assistance."
            )

        lockout_until = parse_iso(row["lockout_until_utc"])
        if lockout_until and lockout_until > now:
            raise ParticipantLockedError(
                f"Too many incorrect access-code attempts. Try again after "
                f"{lockout_until.astimezone(timezone.utc).strftime('%H:%M UTC')}."
            )

        expected = bytes(row["access_hash"])
        actual = _hash_code(code, bytes(row["salt"]))
        if not hmac.compare_digest(expected, actual):
            failed = int(row["failed_attempts"]) + 1
            lockout = ""
            if failed >= MAX_FAILED_ATTEMPTS:
                lockout = iso(now + timedelta(minutes=FAILED_ATTEMPT_LOCK_MINUTES))
                failed = 0
            conn.execute(
                """
                UPDATE participants
                SET failed_attempts=?, lockout_until_utc=?
                WHERE participant_id=?
                """,
                (failed, lockout, pid),
            )
            conn.commit()
            raise InvalidCredentialsError("Participant ID or access code is not recognized.")

        existing_token = row["active_session_token"] or ""
        existing_started = parse_iso(row["active_session_started_utc"])
        active_is_stale = (
            existing_token
            and existing_started is not None
            and (now - existing_started).total_seconds() >= ACTIVE_SESSION_TTL_HOURS * 3600
        )

        if existing_token and not active_is_stale:
            raise ActiveSessionError(
                "This Participant ID already has an active assessment. "
                "Check that the correct ID was entered. If a prior browser/session crashed, "
                "ask the researcher to unlock the ID."
            )

        conn.execute(
            """
            UPDATE participants
            SET failed_attempts=0, lockout_until_utc='',
                active_session_token=?, active_session_started_utc=?
            WHERE participant_id=?
            """,
            (session_token, iso(now), pid),
        )
        conn.commit()
        return pid
    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
    finally:
        conn.close()


def release_session(participant_id: str, session_token: str) -> bool:
    """Release the active-session lock only if the token matches."""
    initialize_registry()
    pid = normalize_participant_id(participant_id)
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE participants
            SET active_session_token='', active_session_started_utc=''
            WHERE participant_id=? AND active_session_token=?
            """,
            (pid, session_token),
        )
        return cur.rowcount == 1
