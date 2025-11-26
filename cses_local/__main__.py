# __main__.py
#
# CLI entry point.

import sys
import colorama
import cses_local.data as data
from cses_local.browse import Browse
import cses_local.submit as submit
from cses_local.arguments import Arguments, Parser, ArgumentNamespace

_UTF8_CODEPOINT: int = 65001


def main() -> None:
    """
    Program main entry point.
    """
    _setup_console()

    # Ensure problem-set data exists.
    data.setup()
    
    args_parser: Parser = Arguments.parser()
    args: ArgumentNamespace = Arguments.parse(args_parser)
    if len(sys.argv) == 1: # No arguments provided.
        args_parser.print_help()
        sys.exit(1)
    
    _dispatch(args)

def _setup_console() -> None:
    """
    Handles console mode setup.
    """
    colorama.init()
    if sys.platform.startswith("win"):
        import win32.win32console as w32con

        w32con.SetConsoleOutputCP(_UTF8_CODEPOINT)
        w32con.SetConsoleCP(_UTF8_CODEPOINT)

def _dispatch(args: ArgumentNamespace) -> None:
    """
    Dispatches to the specified function based on
    the given arguments.
    
    :param args: Arguments given.
    """
    match args.command: # Dispatch commands.
        case "browse": Browse.browse(args.problem)
        case "submit": submit.submit(args.problem, args.file, args.online)

if __name__ == "__main__":
    main()
