#!/usr/bin/env python3
"""Browse Jisho API results in a TUI."""

import httpx
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Input, DataTable, Static, Button
from textual.binding import Binding


API = "https://jisho.org/api/v1/search/words"


def fetch(keyword: str) -> list[dict]:
    """Query Jisho and flatten into (word, reading, meaning, antonyms) rows."""
    resp = httpx.get(API, params={"keyword": keyword}, timeout=20)
    resp.raise_for_status()
    rows = []
    for entry in resp.json().get("data", []):
        variants = entry.get("japanese", [])
        senses = entry.get("senses", [])
        for j in variants:
            for s in senses:
                rows.append({
                    "word": j.get("word", ""),
                    "reading": j.get("reading", ""),
                    "meaning": "; ".join(s.get("english_definitions", [])),
                    "antonyms": ", ".join(s.get("antonyms", [])),
                    "pos": ", ".join(s.get("parts_of_speech", [])),
                })
    return rows



class JishoApp(App):
    CSS = """
    #search-bar { dock: top; height: 3; }
    #results { width: 70%; }
    #detail  { width: 30%; border-left: solid $accent; padding: 0 1; }
    DataTable { height: 1fr; }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+f", "focus_search", "Search"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="", id="search-bar")
        with Horizontal():
            yield DataTable(id="results")
            with VerticalScroll(id="detail", can_focus=False):
                yield Static("Select a row to see details.", id="detail-body")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results", DataTable)
        table.cursor_type = "row"
        table.add_columns("Word", "Reading", "Meaning")
        self.query_one("#search-bar", Input).focus()

    # ---- search ----
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        keyword = event.value.strip()
        if not keyword:
            return
        self.query_one("#detail-body", Static).update("Searching…")
        try:
            rows = await self.run_worker(
                lambda: fetch(keyword), thread=True, exclusive=True
            ).wait()
        except Exception as e:  # noqa: BLE001
            self.query_one("#detail-body", Static).update(f"[red]Error:[/] {e}")
            return

        table = self.query_one("#results", DataTable)
        table.clear()
        self._rows = rows
        for i, r in enumerate(rows):
            table.add_row(r["word"], r["reading"], r["meaning"], key=str(i))
        self.query_one("#detail-body", Static).update(
            f"{len(rows)} rows. Use ↑/↓ to browse, Enter to pin."
        )
        if rows:
            table.move_cursor(row=0)

    # ---- row selection ----
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key is None:
            return
        r = self._rows[int(event.row_key.value)]
        self.query_one("#detail-body", Static).update(
            f"[b]{r['word']}[/b]  ({r['reading']})\n\n"
            f"[b]Meaning:[/b] {r['meaning'] or '—'}\n\n"
            f"[b]Part of speech:[/b] {r['pos'] or '—'}\n\n"
            f"[b]Antonyms:[/b] {r['antonyms'] or '—'}"
        )

    def action_focus_search(self) -> None:
        self.query_one("#search-bar", Input).focus()



if __name__ == "__main__":
    JishoApp().run()
