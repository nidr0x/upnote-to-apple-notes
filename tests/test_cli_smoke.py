from upnote_to_apple_notes.cli import build_parser


def test_build_parser_exposes_expected_subcommands():
    parser = build_parser()
    subparsers = next(
        action for action in parser._actions if getattr(action, "choices", None)
    )

    assert set(subparsers.choices) == {
        "discover",
        "extract",
        "import",
        "resume",
        "report",
    }
