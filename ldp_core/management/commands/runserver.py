from django.core.management.base import CommandError
from django.core.management.commands.runserver import Command as DjangoRunserverCommand


class Command(DjangoRunserverCommand):
    """Run the development server only on the reserved local port."""

    default_addr = "127.0.0.1"
    default_port = "8001"
    allowed_addrports = {
        "8001",
        "127.0.0.1:8001",
        "localhost:8001",
        "[::1]:8001",
    }

    @classmethod
    def fixed_addrport(cls, addrport):
        if addrport is None:
            return f"{cls.default_addr}:{cls.default_port}"
        if addrport not in cls.allowed_addrports:
            raise CommandError(
                "This application is reserved for localhost port 8001. "
                "Use 127.0.0.1:8001."
            )
        return addrport

    def handle(self, *args, **options):
        options["addrport"] = self.fixed_addrport(options.get("addrport"))
        return super().handle(*args, **options)