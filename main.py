"""Entry point for the Claude Token Indicator.

    python main.py

Shows a slim always-on-top strip with your Claude session and weekly usage.
"""

from claude_indicator.app import App


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
