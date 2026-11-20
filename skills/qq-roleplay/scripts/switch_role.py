# -*- coding: utf-8 -*-
"""Inspect and switch active roleplay cards."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from agy_onebot.roleplay_engine import RoleplayEngine


def main():
    parser = argparse.ArgumentParser(description="Roleplay Persona Management")
    parser.add_argument("--list", action="store_true", help="List all available persona cards")
    parser.add_argument("--show", type=str, help="Show prompt instructions for a given role")
    parser.add_argument("--scope", type=str, default="group", choices=["group", "private"], help="Context scope")
    args = parser.parse_args()

    engine = RoleplayEngine()

    if args.list:
        roles = engine.list_roles()
        print("Available Role Cards:")
        for r in roles:
            print(f" • {r}")
        return

    if args.show:
        role_card = engine.get_role(args.show)
        print(f"=== Persona: {role_card.name} (Scope: {args.scope}) ===")
        print(engine.build_system_instructions(args.show, context_type=args.scope))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
