# arguments.py
#
# Definition for Arguments class.
# Handles program arguments.
#
# NOTE: "previous" option is currently not implemented for commands.

import argparse as ap

type Parser = ap.ArgumentParser
type ArgumentNamespace = ap.Namespace
type _Subparser = ap._SubParsersAction[ap.ArgumentParser]

class _HelpFormatter(ap.HelpFormatter):
    """
    Custom help formatter that allows for a customized prefix.
    Internal implementation detail.
    """

    def add_usage(self, usage, actions, groups, prefix=None):
        if prefix is None:
            prefix = "Usage: "
        return super().add_usage(usage, actions, groups, prefix)

def parse(argparser: Parser | None) -> ArgumentNamespace:
    """
    Returns the given arguments in an argument namespace.
    Handles parser creation if `argparser` is `None`.
    
    :param argparser: Optional parser.
    :return: Argument namespace. Holds given arguments.
    """
    
    parser_obj: Parser = argparser if argparser else parser()
    return parser_obj.parse_args()

def parser() -> Parser:
    """
    Returns the program's preconfigured argument parser.
    """
    parser: Parser = ap.ArgumentParser(
        prog="cses",
        description="An offline test-runner and grading utility specifically for the CSES Problem Set.",
        formatter_class=_HelpFormatter,
    )
    parser._positionals.title = "Positional Arguments"
    parser._optionals.title = "Options"

    _add_subparsers(parser)

    return parser

def _add_subparsers(parser: Parser) -> None:
    """
    Adds subparsers to the given subparser.
    Helper function to `parser()`.

    :param parser: Given argument parser to add subparsers to.
    """
    # Replaces the default "{command_1, command_2, ...}".
    subparsers: _Subparser = parser.add_subparsers(
        dest="command", help="Available commands.", metavar="Commands:"
    )
    _add_submit(subparsers)
    _add_browse(subparsers)

# NOTE: "Previous" is currently not implemented.
def _add_submit(subparsers: _Subparser) -> None:
    """
    Configures the given subparser with the submit command.
    Helper function to `_add_subparsers()`.

    :param subparsers: Subparser to add to.
    """
    parser_submit = subparsers.add_parser(
        "submit", help="Submit a solution to a testcase."
    )
    parser_submit.add_argument(
        "problem",
        type=str,
        help="Problem name or ID. Type previous to specify the previously ran test-case.",
    )
    parser_submit.add_argument(
        "file",
        type=str,
        help="Path to file to be submitted.",
    )
    parser_submit.add_argument(
        "--online",
        "-o",
        action="store_true",
        help="Submit online",
    )

# NOTE: "Previous" is currently not implemented.
def _add_browse(subparsers: _Subparser) -> None:
    """
    Configures the given subparser with the browse command.
    Helper function to `_add_subparsers()`.

    :param subparsers: Subparser to add to.
    """
    parser_browse = subparsers.add_parser(
        "browse",
        help="Browse problem descriptions via Arrow Keys or WASD. Jump to a problem by specifying a name or a number.",
    )
    parser_browse.add_argument(
        "problem",
        nargs="?",
        default=None,
        type=str,
        help="Problem name or ID. Type previous to specify the previously ran test-case.",
    )
