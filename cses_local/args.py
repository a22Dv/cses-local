# args.py

import argparse as args


class _HelpFormatter(args.HelpFormatter):
    """
    Custom help formatter that allows for a customized prefix.
    """
    def add_usage(self, usage, actions, groups, prefix=None):
        if prefix is None:
            prefix = "Usage: "
        return super().add_usage(usage, actions, groups, prefix)


def parser() -> args.ArgumentParser:
    """
    Returns the program's argument parser.
    """
    parser = args.ArgumentParser(
        prog="cses",
        description="An offline test-runner and grading utility specifically for the CSES Problem Set.",
        formatter_class=_HelpFormatter
    )
    parser._positionals.title = "Positional Arguments"
    parser._optionals.title = "Options"

    _add_subparsers(parser)
    return parser


def _add_subparsers(parser: args.ArgumentParser) -> None:
    """
    Adds sub-parsers to the passed in argument parser.
    """

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands.", metavar="Commands:"
    )

    # Submit command.
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
        "--online", "-o",
        action="store_true",
        help="Submit online",
    )

    # Browse command.
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
