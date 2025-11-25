# __main__.py
#
# CLI entry point.

import sys
import argparse
import cses_local.args as args
import cses_local.data_setup as data_setup
import cses_local.browse as browse
import cses_local.submit as submit


def main() -> None:
    args_parser: argparse.ArgumentParser = args.parser()

    if sys.platform.startswith("win"):  # Set to UTF-8
        import win32.win32console as w32con

        w32con.SetConsoleOutputCP(65001)
        w32con.SetConsoleCP(65001)

    # Ensure problem-set data exists.
    data_setup.setup()

    if len(sys.argv) == 1:
        args_parser.print_help()
        sys.exit(1)

    arguments: argparse.Namespace = args_parser.parse_args()

    # Dispatch.
    match arguments.command:
        case "browse":
            browse.browse(index=arguments.problem)
        case "submit":
            submit.submit(index=arguments.problem, file=arguments.file)


if __name__ == "__main__":
    main()
