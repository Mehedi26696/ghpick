"use strict";

const API_ROOT = "https://api.github.com";

const state = {
  owner: "",
  repo: "",
  ref: "",
  startPath: "",
  targetKind: "repository",
  token: "",
  metadata: null,
  files: [],
  root: null,
  selected: new Set(),
  expanded: new Set([""]),
  filter: "all",
  busy: false,
};

const dom = Object.fromEntries(
  [
    "repo-form", "repo-url", "load-button", "advanced-toggle", "advanced-panel", "branch",
    "github-token", "form-message", "workspace", "repo-owner", "workspace-title",
    "repo-description", "repo-language", "language-dot", "repo-stars", "repo-branch",
    "file-search", "quick-filters", "include-pattern", "exclude-pattern", "rate-label", "rate-reset",
    "rate-bar", "select-all", "collapse-all", "refresh-repo", "file-tree", "empty-state",
    "selected-count", "selected-size", "clear-selection", "download-button", "download-progress",
    "progress-label", "progress-value", "progress-bar", "toast",
  ].map((id) => [id, document.getElementById(id)])
);

const categoryExtensions = {
  code: new Set(["js", "jsx", "ts", "tsx", "py", "java", "c", "cc", "cpp", "h", "hpp", "cs", "go", "rs", "rb", "php", "swift", "kt", "kts", "sh", "bash", "zsh", "fish", "sql", "vue", "svelte", "html", "css", "scss", "sass", "less"]),
  docs: new Set(["md", "mdx", "txt", "rst", "adoc", "pdf", "doc", "docx"]),
  config: new Set(["json", "yaml", "yml", "toml", "ini", "conf", "config", "xml", "env", "lock"]),
  media: new Set(["png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "mp3", "wav", "mp4", "webm", "mov"]),
};

const languageColors = {
  JavaScript: "#f1e05a", TypeScript: "#3178c6", Python: "#3572a5", Java: "#b07219",
  HTML: "#e34c26", CSS: "#563d7c", Go: "#00add8", Rust: "#dea584", Ruby: "#701516",
  PHP: "#4f5d95", "C++": "#f34b7d", C: "#555555", Shell: "#89e051",
};

dom["advanced-toggle"].addEventListener("click", () => {
  const open = dom["advanced-toggle"].getAttribute("aria-expanded") === "true";
  dom["advanced-toggle"].setAttribute("aria-expanded", String(!open));
  dom["advanced-panel"].hidden = open;
});

dom["repo-form"].addEventListener("submit", async (event) => {
  event.preventDefault();
  await loadRepository();
});

dom["refresh-repo"].addEventListener("click", loadRepository);
dom["collapse-all"].addEventListener("click", () => {
  state.expanded = new Set([""]);
  if (state.startPath) state.expanded.add(parentPath(state.startPath));
  renderTree();
});

dom["file-search"].addEventListener("input", renderTree);
dom["include-pattern"].addEventListener("input", renderTree);
dom["exclude-pattern"].addEventListener("input", renderTree);

dom["quick-filters"].addEventListener("click", (event) => {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  state.filter = button.dataset.filter;
  dom["quick-filters"].querySelectorAll("[data-filter]").forEach((item) => {
    item.classList.toggle("active", item === button);
  });
  renderTree();
});

dom["select-all"].addEventListener("change", () => {
  const visible = getVisibleFiles();
  if (dom["select-all"].checked) visible.forEach((file) => state.selected.add(file.path));
  else visible.forEach((file) => state.selected.delete(file.path));
  renderTree();
});

dom["clear-selection"].addEventListener("click", () => {
  state.selected.clear();
  renderTree();
});

dom["download-button"].addEventListener("click", downloadSelection);

document.addEventListener("keydown", (event) => {
  if (event.key === "/" && !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)) {
    event.preventDefault();
    dom["file-search"].focus();
  }
});

async function loadRepository() {
  if (state.busy) return;
  clearMessage();

  let reference;
  try {
    reference = parseGitHubUrl(dom["repo-url"].value);
  } catch (error) {
    showMessage(error.message);
    return;
  }

  setBusy(true, "Connecting…");
  state.owner = reference.owner;
  state.repo = reference.repo;
  state.startPath = reference.path;
  state.targetKind = reference.kind;
  state.token = dom["github-token"].value.trim();

  try {
    const metadata = await githubRequest(`/repos/${encodeURIComponent(state.owner)}/${encodeURIComponent(state.repo)}`);
    state.metadata = metadata;
    state.ref = dom.branch.value.trim() || reference.ref || metadata.default_branch;
    dom.branch.value = state.ref;

    const tree = await githubRequest(
      `/repos/${encodeURIComponent(state.owner)}/${encodeURIComponent(state.repo)}/git/trees/${encodeURIComponent(state.ref)}?recursive=1`
    );
    if (tree.truncated) {
      showToast("GitHub truncated this very large repository tree. Some files may be missing.", true);
    }

    state.files = tree.tree
      .filter((item) => item.type === "blob")
      .map((item) => ({
        path: item.path,
        name: item.path.split("/").pop(),
        size: Number(item.size || 0),
        sha: item.sha,
        url: item.url,
      }))
      .sort((a, b) => a.path.localeCompare(b.path));

    state.root = buildTree(state.files);
    state.selected.clear();
    state.expanded = new Set([""]);
    expandToPath(state.startPath);
    renderRepositoryHeader();
    renderFilterCounts();
    renderTree();
    dom.workspace.hidden = false;
    dom.workspace.scrollIntoView({ behavior: "smooth", block: "start" });

    if (state.targetKind === "file" && state.files.some((file) => file.path === state.startPath)) {
      state.selected.add(state.startPath);
      renderTree();
    }
  } catch (error) {
    showMessage(friendlyError(error));
  } finally {
    setBusy(false);
  }
}

function parseGitHubUrl(value) {
  const raw = value.trim();
  if (!raw) throw new Error("Enter a GitHub repository URL first.");
  let url;
  try {
    url = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`);
  } catch {
    throw new Error("That does not look like a valid URL.");
  }
  if (!["github.com", "www.github.com"].includes(url.hostname.toLowerCase())) {
    throw new Error("Use a github.com repository, folder, or file URL.");
  }
  const parts = url.pathname.split("/").filter(Boolean);
  if (parts.length < 2) throw new Error("The URL must include both an owner and repository.");
  const owner = parts[0];
  const repo = parts[1].replace(/\.git$/i, "");
  let ref = "";
  let path = "";
  let kind = "repository";
  if (["tree", "blob"].includes(parts[2]) && parts[3]) {
    ref = decodeURIComponent(parts[3]);
    path = parts.slice(4).map(decodeURIComponent).join("/");
    kind = parts[2] === "blob" ? "file" : "directory";
  }
  return { owner, repo, ref, path, kind };
}

async function githubRequest(path) {
  const headers = {
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  let response;
  try {
    response = await fetch(`${API_ROOT}${path}`, { headers });
  } catch {
    throw new Error("Could not reach GitHub. Check your internet connection and try again.");
  }
  updateRateLimit(response.headers);
  if (!response.ok) {
    let detail = "";
    try { detail = (await response.json()).message || ""; } catch { /* no JSON response */ }
    const error = new Error(detail || `GitHub returned status ${response.status}.`);
    error.status = response.status;
    throw error;
  }
  return response.json();
}

function friendlyError(error) {
  if (error.status === 404) return `Repository or branch not found. Check the URL, access token, and branch “${state.ref || dom.branch.value}”.`;
  if (error.status === 401) return "GitHub rejected the token. Remove it for a public repository or enter a valid token.";
  if (error.status === 403 && /rate limit/i.test(error.message)) return "GitHub's API rate limit has been reached. Add a token in Advanced options and try again.";
  return error.message || "Something went wrong while loading the repository.";
}

function buildTree(files) {
  const root = createNode("", "", "folder", 0);
  for (const file of files) {
    const parts = file.path.split("/");
    let node = root;
    parts.forEach((part, index) => {
      const path = parts.slice(0, index + 1).join("/");
      const isFile = index === parts.length - 1;
      if (!node.children.has(part)) {
        node.children.set(part, createNode(part, path, isFile ? "file" : "folder", index + 1));
      }
      node = node.children.get(part);
      if (isFile) node.file = file;
    });
  }
  calculateNodeStats(root);
  return root;
}

function createNode(name, path, type, depth) {
  return { name, path, type, depth, children: new Map(), files: [], size: 0, file: null };
}

function calculateNodeStats(node) {
  if (node.type === "file") {
    node.files = [node.file];
    node.size = node.file.size;
    return;
  }
  node.files = [];
  node.size = 0;
  for (const child of node.children.values()) {
    calculateNodeStats(child);
    node.files.push(...child.files);
    node.size += child.size;
  }
}

function renderRepositoryHeader() {
  const metadata = state.metadata;
  dom["repo-owner"].textContent = metadata.owner.login;
  dom["workspace-title"].textContent = metadata.name;
  dom["repo-description"].textContent = metadata.description || "No repository description provided.";
  dom["repo-language"].textContent = metadata.language || "Mixed";
  dom["language-dot"].style.background = languageColors[metadata.language] || "#78e4a6";
  dom["repo-stars"].textContent = compactNumber(metadata.stargazers_count);
  dom["repo-branch"].textContent = state.ref;
}

function renderFilterCounts() {
  document.getElementById("count-all").textContent = compactNumber(state.files.length);
  for (const category of Object.keys(categoryExtensions)) {
    const count = state.files.filter((file) => fileCategory(file) === category).length;
    document.getElementById(`count-${category}`).textContent = compactNumber(count);
  }
}

function renderTree() {
  if (!state.root) return;
  const fragment = document.createDocumentFragment();
  const hasFilter = Boolean(dom["file-search"].value.trim() || patterns("include-pattern").length || patterns("exclude-pattern").length || state.filter !== "all");

  const appendChildren = (node) => {
    const children = [...node.children.values()]
      .filter(nodeMatchesFilters)
      .sort((a, b) => (a.type === b.type ? a.name.localeCompare(b.name) : a.type === "folder" ? -1 : 1));
    for (const child of children) {
      fragment.append(createTreeRow(child));
      const shouldExpand = hasFilter || state.expanded.has(child.path);
      if (child.type === "folder" && shouldExpand) appendChildren(child);
    }
  };
  appendChildren(state.root);
  dom["file-tree"].replaceChildren(fragment);

  const visible = getVisibleFiles();
  dom["empty-state"].hidden = visible.length !== 0;
  dom["file-tree"].hidden = visible.length === 0;
  updateSelectionUi(visible);
}

function createTreeRow(node) {
  const row = document.createElement("div");
  row.className = "tree-row";
  row.style.setProperty("--depth", Math.max(0, node.depth - 1));
  row.setAttribute("role", "treeitem");
  row.setAttribute("aria-level", node.depth);
  if (node.type === "folder") row.setAttribute("aria-expanded", String(state.expanded.has(node.path)));

  const selectedCount = node.files.filter((file) => state.selected.has(file.path)).length;
  const checked = selectedCount > 0 && selectedCount === node.files.length;
  const indeterminate = selectedCount > 0 && !checked;
  if (selectedCount) row.classList.add("selected");

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = `tree-toggle ${node.type === "folder" ? "" : "spacer"} ${state.expanded.has(node.path) ? "expanded" : ""}`;
  toggle.tabIndex = node.type === "folder" ? 0 : -1;
  toggle.innerHTML = node.type === "folder" ? '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>' : "";
  if (node.type === "folder") {
    toggle.setAttribute("aria-label", `${state.expanded.has(node.path) ? "Collapse" : "Expand"} ${node.name}`);
    toggle.addEventListener("click", () => {
      if (state.expanded.has(node.path)) state.expanded.delete(node.path);
      else state.expanded.add(node.path);
      renderTree();
    });
  }

  const label = document.createElement("label");
  label.className = "tree-label";
  label.title = node.path;
  const input = document.createElement("input");
  input.type = "checkbox";
  input.className = "tree-check";
  input.checked = checked;
  input.indeterminate = indeterminate;
  input.setAttribute("aria-label", `Select ${node.path}`);
  input.addEventListener("change", () => {
    if (input.checked) node.files.forEach((file) => state.selected.add(file.path));
    else node.files.forEach((file) => state.selected.delete(file.path));
    renderTree();
  });
  const box = document.createElement("span");
  box.className = "custom-checkbox";
  const icon = document.createElement("span");
  icon.className = `tree-icon ${node.type}`;
  icon.innerHTML = node.type === "folder"
    ? '<svg viewBox="0 0 24 24"><path d="M3 6.5h7l2 2h9v10H3v-12Z" /></svg>'
    : '<svg viewBox="0 0 24 24"><path d="M6 2.5h8l4 4v15H6v-19Z" /><path d="M14 2.5v4h4" /></svg>';
  const name = document.createElement("span");
  name.className = "tree-name";
  name.textContent = node.name;
  const size = document.createElement("span");
  size.className = "tree-size";
  size.textContent = node.type === "file" ? humanSize(node.size) : `${node.files.length} item${node.files.length === 1 ? "" : "s"}`;

  label.append(input, box, icon, name, size);
  row.append(toggle, label);
  return row;
}

function nodeMatchesFilters(node) {
  if (node.type === "file") return fileMatchesFilters(node.file);
  return node.files.some(fileMatchesFilters);
}

function fileMatchesFilters(file) {
  const search = dom["file-search"].value.trim().toLowerCase();
  if (search && !file.path.toLowerCase().includes(search)) return false;
  if (state.filter !== "all" && fileCategory(file) !== state.filter) return false;
  const includes = patterns("include-pattern");
  const excludes = patterns("exclude-pattern");
  if (includes.length && !includes.some((pattern) => globMatches(file, pattern))) return false;
  if (excludes.some((pattern) => globMatches(file, pattern))) return false;
  return true;
}

function patterns(id) {
  return dom[id].value.split(",").map((value) => value.trim()).filter(Boolean);
}

function globMatches(file, pattern) {
  const normalized = pattern.replace(/\\/g, "/");
  if (!/[?*]/.test(normalized)) {
    return file.name === normalized || file.path === normalized || file.path.split("/").includes(normalized) || file.path.startsWith(`${normalized.replace(/\/$/, "")}/`);
  }
  const expression = normalized
    .replace(/[.+^${}()|[\]\\]/g, "\\$&")
    .replace(/\*\*/g, "::DOUBLE_STAR::")
    .replace(/\*/g, "[^/]*")
    .replace(/\?/g, "[^/]")
    .replace(/::DOUBLE_STAR::/g, ".*");
  const regex = new RegExp(`^${expression}$`, "i");
  return regex.test(file.path) || regex.test(file.name);
}

function fileCategory(file) {
  const lower = file.name.toLowerCase();
  const extension = lower.includes(".") ? lower.split(".").pop() : "";
  if (["readme", "license", "changelog", "contributing"].some((name) => lower.startsWith(name))) return "docs";
  if (["dockerfile", "makefile", ".gitignore", ".editorconfig"].includes(lower)) return "config";
  for (const [category, extensions] of Object.entries(categoryExtensions)) {
    if (extensions.has(extension)) return category;
  }
  return "other";
}

function getVisibleFiles() {
  return state.files.filter(fileMatchesFilters);
}

function updateSelectionUi(visible) {
  const selectedFiles = state.files.filter((file) => state.selected.has(file.path));
  const selectedVisible = visible.filter((file) => state.selected.has(file.path)).length;
  dom["select-all"].checked = visible.length > 0 && selectedVisible === visible.length;
  dom["select-all"].indeterminate = selectedVisible > 0 && selectedVisible < visible.length;
  dom["selected-count"].textContent = `${selectedFiles.length} file${selectedFiles.length === 1 ? "" : "s"} selected`;
  dom["selected-size"].textContent = `${humanSize(selectedFiles.reduce((total, file) => total + file.size, 0))} total`;
  dom["clear-selection"].disabled = selectedFiles.length === 0 || state.busy;
  dom["download-button"].disabled = selectedFiles.length === 0 || state.busy;
  dom["download-button"].querySelector("span").textContent = selectedFiles.length === 1 ? "Download file" : "Download selection";
}

async function downloadSelection() {
  if (state.busy) return;
  const files = state.files.filter((file) => state.selected.has(file.path));
  if (!files.length) return;
  setBusy(true);
  showProgress(true);

  try {
    if (files.length === 1) {
      updateProgress(0, `Downloading ${files[0].name}…`);
      const data = await fetchFile(files[0]);
      triggerDownload(new Blob([data]), files[0].name);
      updateProgress(100, "Download ready");
    } else {
      const entries = [];
      for (let index = 0; index < files.length; index += 1) {
        const file = files[index];
        updateProgress(Math.round((index / files.length) * 80), `Fetching ${index + 1} of ${files.length}: ${file.name}`);
        entries.push({ name: file.path, data: await fetchFile(file) });
      }
      updateProgress(88, "Building ZIP archive…");
      const zip = createZip(entries);
      triggerDownload(zip, `${state.repo}-selection.zip`);
      updateProgress(100, "ZIP download ready");
    }
    showToast(files.length === 1 ? "Your file is ready." : `Created a ZIP with ${files.length} files.`);
    setTimeout(() => showProgress(false), 1800);
  } catch (error) {
    showProgress(false);
    showToast(friendlyError(error), true);
  } finally {
    setBusy(false);
    updateSelectionUi(getVisibleFiles());
  }
}

async function fetchFile(file) {
  if (state.token) {
    const blob = await githubRequest(`/repos/${encodeURIComponent(state.owner)}/${encodeURIComponent(state.repo)}/git/blobs/${file.sha}`);
    if (blob.encoding !== "base64") throw new Error(`GitHub returned an unsupported encoding for ${file.path}.`);
    return base64ToBytes(blob.content.replace(/\s/g, ""));
  }
  const path = file.path.split("/").map(encodeURIComponent).join("/");
  const rawUrl = `https://raw.githubusercontent.com/${encodeURIComponent(state.owner)}/${encodeURIComponent(state.repo)}/${encodeURIComponent(state.ref)}/${path}`;
  let response;
  try { response = await fetch(rawUrl); } catch { throw new Error(`Could not download ${file.path}.`); }
  if (!response.ok) throw new Error(`Could not download ${file.path} (status ${response.status}).`);
  return new Uint8Array(await response.arrayBuffer());
}

function createZip(entries) {
  const encoder = new TextEncoder();
  const localParts = [];
  const centralParts = [];
  let offset = 0;
  const { time, date } = dosDateTime(new Date());

  for (const entry of entries) {
    const name = encoder.encode(entry.name.replace(/^\/+/, ""));
    const data = entry.data instanceof Uint8Array ? entry.data : new Uint8Array(entry.data);
    const crc = crc32(data);
    const local = new Uint8Array(30 + name.length + data.length);
    const localView = new DataView(local.buffer);
    localView.setUint32(0, 0x04034b50, true);
    localView.setUint16(4, 20, true);
    localView.setUint16(6, 0x0800, true);
    localView.setUint16(8, 0, true);
    localView.setUint16(10, time, true);
    localView.setUint16(12, date, true);
    localView.setUint32(14, crc, true);
    localView.setUint32(18, data.length, true);
    localView.setUint32(22, data.length, true);
    localView.setUint16(26, name.length, true);
    local.set(name, 30);
    local.set(data, 30 + name.length);
    localParts.push(local);

    const central = new Uint8Array(46 + name.length);
    const centralView = new DataView(central.buffer);
    centralView.setUint32(0, 0x02014b50, true);
    centralView.setUint16(4, 20, true);
    centralView.setUint16(6, 20, true);
    centralView.setUint16(8, 0x0800, true);
    centralView.setUint16(10, 0, true);
    centralView.setUint16(12, time, true);
    centralView.setUint16(14, date, true);
    centralView.setUint32(16, crc, true);
    centralView.setUint32(20, data.length, true);
    centralView.setUint32(24, data.length, true);
    centralView.setUint16(28, name.length, true);
    centralView.setUint32(42, offset, true);
    central.set(name, 46);
    centralParts.push(central);
    offset += local.length;
  }

  const centralSize = centralParts.reduce((total, part) => total + part.length, 0);
  const end = new Uint8Array(22);
  const endView = new DataView(end.buffer);
  endView.setUint32(0, 0x06054b50, true);
  endView.setUint16(8, entries.length, true);
  endView.setUint16(10, entries.length, true);
  endView.setUint32(12, centralSize, true);
  endView.setUint32(16, offset, true);
  return new Blob([...localParts, ...centralParts, end], { type: "application/zip" });
}

const crcTable = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let value = n;
    for (let bit = 0; bit < 8; bit += 1) value = (value & 1) ? (0xedb88320 ^ (value >>> 1)) : (value >>> 1);
    table[n] = value >>> 0;
  }
  return table;
})();

function crc32(data) {
  let crc = 0xffffffff;
  for (const byte of data) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function dosDateTime(value) {
  const year = Math.max(1980, value.getFullYear());
  return {
    time: (value.getHours() << 11) | (value.getMinutes() << 5) | (value.getSeconds() >> 1),
    date: ((year - 1980) << 9) | ((value.getMonth() + 1) << 5) | value.getDate(),
  };
}

function base64ToBytes(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
  return bytes;
}

function triggerDownload(blob, name) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function expandToPath(path) {
  if (!path) return;
  const parts = path.split("/");
  const limit = state.targetKind === "file" ? parts.length - 1 : parts.length;
  for (let index = 1; index <= limit; index += 1) state.expanded.add(parts.slice(0, index).join("/"));
}

function parentPath(path) {
  const parts = path.split("/");
  parts.pop();
  return parts.join("/");
}

function updateRateLimit(headers) {
  const limit = Number(headers.get("X-RateLimit-Limit"));
  const remaining = Number(headers.get("X-RateLimit-Remaining"));
  if (!Number.isFinite(limit) || !Number.isFinite(remaining)) return;
  dom["rate-label"].textContent = `${remaining.toLocaleString()} / ${limit.toLocaleString()}`;
  dom["rate-bar"].style.width = `${Math.max(0, Math.min(100, (remaining / limit) * 100))}%`;
  const reset = Number(headers.get("X-RateLimit-Reset"));
  if (Number.isFinite(reset) && reset > 0) {
    const resetTime = new Date(reset * 1000).toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
    dom["rate-reset"].textContent = `Resets at ${resetTime}`;
  }
}

function setBusy(busy, label = "Explore repository") {
  state.busy = busy;
  dom["load-button"].disabled = busy;
  dom["load-button"].querySelector("span").textContent = label;
  if (!busy) dom["load-button"].querySelector("span").textContent = "Explore repository";
  if (state.root) updateSelectionUi(getVisibleFiles());
}

function showProgress(show) {
  dom["download-progress"].hidden = !show;
  if (!show) updateProgress(0, "Preparing download…");
}

function updateProgress(percent, label) {
  dom["progress-label"].textContent = label;
  dom["progress-value"].textContent = `${percent}%`;
  dom["progress-bar"].style.width = `${percent}%`;
}

let toastTimer;
function showToast(message, isError = false) {
  clearTimeout(toastTimer);
  dom.toast.textContent = message;
  dom.toast.classList.toggle("error", isError);
  dom.toast.hidden = false;
  toastTimer = setTimeout(() => { dom.toast.hidden = true; }, 5000);
}

function showMessage(message) {
  dom["form-message"].textContent = message;
  dom["form-message"].hidden = false;
}

function clearMessage() {
  dom["form-message"].hidden = true;
  dom["form-message"].textContent = "";
}

function compactNumber(value) {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value || 0);
}

function humanSize(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const amount = bytes / (1024 ** exponent);
  return `${amount >= 10 || exponent === 0 ? amount.toFixed(0) : amount.toFixed(1)} ${units[exponent]}`;
}
