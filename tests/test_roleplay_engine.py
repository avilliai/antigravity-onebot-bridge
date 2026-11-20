# -*- coding: utf-8 -*-
"""Unit tests for Roleplay Engine."""

import unittest
from pathlib import Path
from agy_onebot.roleplay_engine import RoleplayEngine


class TestRoleplayEngine(unittest.TestCase):

    def setUp(self):
        self.engine = RoleplayEngine()

    def test_list_and_get_roles(self):
        roles = self.engine.list_roles()
        self.assertIn("default", roles)
        self.assertIn("shiro", roles)

    def test_scope_filtering(self):
        group_prompt = self.engine.build_system_instructions("shiro", context_type="group")
        private_prompt = self.engine.build_system_instructions("shiro", context_type="private")

        self.assertIn("群聊", group_prompt)
        self.assertNotIn("私聊相处", group_prompt)

        self.assertIn("私聊", private_prompt)
        self.assertNotIn("群聊相处", private_prompt)


if __name__ == "__main__":
    unittest.main()
