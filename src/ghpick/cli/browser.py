from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Static, Tree

from ghpick.github.client import GitHubClient, RepositoryItem
from ghpick.github.parser import GitHubTarget
from ghpick.utils.filesystem import human_size


@dataclass
class BrowserNodeData:
    path: str
    name: str
    kind: str
    size: int = 0
    loaded: bool = False


class RepositoryBrowserApp(App[list[GitHubTarget]]):
    CSS = """
    Screen {
        background: $surface;
    }

    #browser {
        height: 1fr;
        padding: 1 2;
    }

    #summary {
        height: 3;
        padding: 1 2;
        border: round $primary;
        background: $panel;
        text-style: bold;
    }

    #tree {
        height: 1fr;
        margin-top: 1;
        padding: 1 2;
        border: round $secondary;
        background: $boost;
    }
    """

    BINDINGS = [
        Binding("space", "toggle_selected", "Select", priority=True),
        Binding("enter", "open", "Expand", priority=True),
        Binding("d", "download", "Download"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        client: GitHubClient,
        owner: str,
        repo: str,
        ref: str,
        start_path: str = "",
    ) -> None:
        super().__init__()
        self.client = client
        self.owner = owner
        self.repo = repo
        self.ref = ref
        self.start_path = start_path.strip("/")
        self.selected_paths: set[str] = set()
        self.selected_kinds: dict[str, str] = {self.start_path: "dir"}

    def compose(self) -> ComposeResult:
        root_name = self.start_path.split("/")[-1] if self.start_path else self.repo
        root_data = BrowserNodeData(path=self.start_path, name=root_name, kind="dir")
        yield Header()
        with Vertical(id="browser"):
            yield Static("", id="summary")
            yield Tree(self._node_label(root_data), data=root_data, id="tree")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "GHPick"
        self.sub_title = f"{self.owner}/{self.repo}@{self.ref}"
        tree = self.query_one("#tree", Tree)
        tree.root.expand()
        self._load_tree_node(tree.root)
        self._update_summary()

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[BrowserNodeData]) -> None:
        self._load_tree_node(event.node)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[BrowserNodeData]) -> None:
        self._update_summary()

    def action_toggle_selected(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node or tree.root
        data = node.data
        if not isinstance(data, BrowserNodeData):
            return
        if data.path in self.selected_paths:
            self.selected_paths.remove(data.path)
        else:
            self.selected_paths.add(data.path)
            self.selected_kinds[data.path] = data.kind
        self._refresh_node_label(node)
        self._update_summary()

    def action_open(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node or tree.root
        data = node.data
        if not isinstance(data, BrowserNodeData) or data.kind != "dir":
            return
        self._load_tree_node(node)
        if node.is_expanded:
            node.collapse()
        else:
            node.expand()
        self._update_summary()

    def action_download(self) -> None:
        targets = [
            GitHubTarget(
                owner=self.owner,
                repo=self.repo,
                ref=self.ref,
                path=path,
                kind="directory" if self.selected_kinds.get(path) == "dir" else "file",
            )
            for path in sorted(self.selected_paths)
        ]
        if not targets:
            self.notify("Select at least one file or folder first.", severity="warning")
            return
        self.exit(targets)

    def action_refresh(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node or tree.root
        data = node.data
        if not isinstance(data, BrowserNodeData):
            return
        if data.kind != "dir":
            node = node.parent or tree.root
            data = node.data
        if isinstance(data, BrowserNodeData):
            data.loaded = False
            node.remove_children()
            self._load_tree_node(node)
            node.expand()
        self._update_summary()

    def action_quit(self) -> None:
        self.exit([])

    def _load_tree_node(self, node: object) -> None:
        data = getattr(node, "data", None)
        if not isinstance(data, BrowserNodeData) or data.kind != "dir" or data.loaded:
            return
        items = self.client.list_directory(self.owner, self.repo, data.path, self.ref)
        for item in items:
            child_data = self._data_from_item(item)
            self.selected_kinds[child_data.path] = child_data.kind
            if child_data.kind == "dir":
                node.add(
                    self._node_label(child_data),
                    data=child_data,
                    allow_expand=True,
                )
            else:
                node.add_leaf(self._node_label(child_data), data=child_data)
        data.loaded = True

    def _data_from_item(self, item: RepositoryItem) -> BrowserNodeData:
        return BrowserNodeData(
            path=item.path,
            name=item.name,
            kind="dir" if item.type == "dir" else "file",
            size=item.size,
        )

    def _node_label(self, data: BrowserNodeData) -> Text:
        checkbox = "[x]" if data.path in self.selected_paths else "[ ]"
        if data.kind == "dir":
            name = data.name or self.repo
            return Text(f"{checkbox} [DIR]  {name}/")
        return Text(f"{checkbox} [FILE] {data.name}  {human_size(data.size)}")

    def _refresh_node_label(self, node: object) -> None:
        data = getattr(node, "data", None)
        if isinstance(data, BrowserNodeData):
            node.set_label(self._node_label(data))
            node.refresh()

    def _update_summary(self) -> None:
        tree = self.query_one("#tree", Tree)
        node = tree.cursor_node or tree.root
        data = node.data
        current = "/"
        if isinstance(data, BrowserNodeData):
            current = data.path or "/"
        selected = len(self.selected_paths)
        summary = self.query_one("#summary", Static)
        summary.update(
            f"{self.owner}/{self.repo}@{self.ref}    Current: {current}    "
            f"Selected: {selected}    Space: select | Enter: expand | d: download"
        )
