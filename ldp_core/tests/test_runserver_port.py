from django.core.management.base import CommandError
from django.test import SimpleTestCase

from ldp_core.management.commands.runserver import Command


class FixedPortRunserverTests(SimpleTestCase):
    def test_defaults_to_localhost_port_8001(self):
        self.assertEqual(Command.fixed_addrport(None), "127.0.0.1:8001")

    def test_accepts_only_local_port_8001_forms(self):
        for addrport in Command.allowed_addrports:
            with self.subTest(addrport=addrport):
                self.assertEqual(Command.fixed_addrport(addrport), addrport)

    def test_rejects_an_alternate_port(self):
        with self.assertRaisesMessage(CommandError, "localhost port 8001"):
            Command.fixed_addrport("127.0.0.1:8000")

    def test_rejects_non_local_binding(self):
        with self.assertRaisesMessage(CommandError, "localhost port 8001"):
            Command.fixed_addrport("0.0.0.0:8001")