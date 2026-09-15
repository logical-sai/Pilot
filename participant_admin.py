from __future__ import annotations

import argparse

from participant_registry import (
    RegistryError,
    create_participant,
    force_unlock,
    list_participants,
    reset_access_code,
    set_participant_active,
)


def cmd_create(args):
    code = create_participant(args.id, args.code)
    print(f"Participant created: {args.id.upper()}")
    print(f"One-time access code: {code}")
    print("Give this code only to the intended participant. The plaintext code is not stored.")


def cmd_reset(args):
    code = reset_access_code(args.id)
    print(f"Access code reset for: {args.id.upper()}")
    print(f"New one-time access code: {code}")


def cmd_unlock(args):
    force_unlock(args.id)
    print(f"Active-session lock cleared for: {args.id.upper()}")


def cmd_active(args, active: bool):
    set_participant_active(args.id, active)
    print(f"{args.id.upper()} is now {'active' if active else 'inactive'}.")


def cmd_list(_args):
    rows = list_participants()
    if not rows:
        print("No participants are registered.")
        return
    print(
        f"{'Participant':<18} {'Active':<8} {'Failed':<8} "
        f"{'Lockout until':<28} {'Active session started'}"
    )
    print("-" * 100)
    for r in rows:
        print(
            f"{r.participant_id:<18} {str(r.active):<8} {r.failed_attempts:<8} "
            f"{(r.lockout_until_utc or '-'):28} {r.active_session_started_utc or '-'}"
        )


def build_parser():
    p = argparse.ArgumentParser(
        description="Optional researcher participant-registry administration. Normal new participants are registered automatically by the app."
    )
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("create", help="Create one new unique Participant ID.")
    c.add_argument("--id", required=True, help="Example: P001")
    c.add_argument(
        "--code",
        help="Optional researcher-selected code (minimum 8 chars). "
             "If omitted, a random code is generated.",
    )
    c.set_defaults(func=cmd_create)

    r = sub.add_parser("reset-code", help="Generate a new access code.")
    r.add_argument("--id", required=True)
    r.set_defaults(func=cmd_reset)

    u = sub.add_parser("unlock", help="Clear a stuck active-session lock.")
    u.add_argument("--id", required=True)
    u.set_defaults(func=cmd_unlock)

    a = sub.add_parser("activate", help="Allow this Participant ID to start sessions.")
    a.add_argument("--id", required=True)
    a.set_defaults(func=lambda args: cmd_active(args, True))

    d = sub.add_parser("deactivate", help="Prevent this Participant ID from starting sessions.")
    d.add_argument("--id", required=True)
    d.set_defaults(func=lambda args: cmd_active(args, False))

    l = sub.add_parser("list", help="List registry status without showing access codes.")
    l.set_defaults(func=cmd_list)
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except (RegistryError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
