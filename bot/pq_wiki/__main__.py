import sys

from pq_wiki.ingest_server import main as server_main
from pq_wiki.import_runner import main as import_main


def main():
    argv = sys.argv[1:]
    if not argv:
        print(
            "Usage: python -m pq_wiki import <dump.json> [--force] | "
            "python -m pq_wiki import-templates | "
            "python -m pq_wiki serve",
        )
        sys.exit(2)
    if argv[0] == "serve":
        server_main()
        return
    if argv[0] == "import-templates":
        from pq_wiki.template_import import main as templates_main

        sys.exit(templates_main(argv[1:]))
    if argv[0] == "import":
        sys.exit(import_main(["import", *argv[1:]]))
    sys.exit(import_main(["import", *argv]))


if __name__ == "__main__":
    main()
