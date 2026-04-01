"""
Developer scripts used to build the documentation
----------
Functions:
    add_copyright   - Updates the copyright text with today's year
"""

from pathlib import Path
from datetime import date

def add_copyright():
    "Updates the copyright with the current year"

    copyright = Path(__file__).parents[1] / "docs" / "_static" / "copyright.css"
    content = (
        "/* Removes the copyright text enforced by the read-the-docs theme */\n"
        "div[class=copyright] {\n"
        "    visibility: hidden;\n"
        "    position: relative;\n"
        "}\n"
        "\n"
        "/* The desired attribution text */\n"
        "div[class=copyright]:after {\n"
        "    visibility: visible;\n"
        "    position: absolute;\n"
        "    top: 0;\n"
        "    left: 0;\n"
        f'    content: "USGS {date.today().year}, Public Domain";\n'
        "}\n"
    )
    copyright.write_text(content)
