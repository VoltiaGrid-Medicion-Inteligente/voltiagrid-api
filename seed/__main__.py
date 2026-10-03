import argparse

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

from seed.config import VALID_MODES, build_settings


def build_parser():
    parser = argparse.ArgumentParser(description="Seed del inventario de red (F4)")
    parser.add_argument("--seed", type=int, default=None, help="semilla fija")
    parser.add_argument("--mode", choices=VALID_MODES, default=None, help="dev o full")
    parser.add_argument("--defect-rate", type=float, default=None, help="tasa de defectos, de 0 a 1")
    parser.add_argument("--database-url", default=None, help="URL de la base de datos")
    return parser


def main():
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    try:
        settings = build_settings(args)
    except ValueError as error:
        parser.error(str(error))

    safe_url = make_url(settings.database_url).render_as_string(hide_password=True)
    print("Configuración del seed")
    print(f"  seed:         {settings.seed}")
    print(f"  mode:         {settings.mode} ({settings.meter_count} medidores)")
    print(f"  defect_rate:  {settings.defect_rate}")
    print(f"  database_url: {safe_url}")


if __name__ == "__main__":
    main()