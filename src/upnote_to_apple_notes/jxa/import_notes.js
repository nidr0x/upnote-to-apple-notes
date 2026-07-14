function run() {
  ObjC.import("Foundation");

  const notesApp = Application("Notes");
  notesApp.includeStandardAdditions = true;
  const stdin = $.NSFileHandle.fileHandleWithStandardInput;
  const data = stdin.readDataToEndOfFile;
  const payload = JSON.parse(ObjC.unwrap($.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding)));
  const accounts = notesApp.accounts();
  const requestedAccountName = payload.account_name;
  const matchingAccounts = requestedAccountName
    ? accounts.filter((account) => account.name() === requestedAccountName)
    : accounts;
  const account = matchingAccounts[0];

  if (!account) {
    const suffix = requestedAccountName ? ` named ${requestedAccountName}` : "";
    throw new Error(`No Apple Notes account is available${suffix}`);
  }
  if (requestedAccountName && matchingAccounts.length > 1) {
    throw new Error(`More than one Apple Notes account is named ${requestedAccountName}`);
  }

  function readText(path) {
    const source = $.NSString.stringWithContentsOfFileEncodingError(
      $(path),
      $.NSUTF8StringEncoding,
      null
    );
    if (!source || source.js === undefined) {
      throw new Error(`Unable to read note HTML at ${path}`);
    }
    return source.js;
  }

  function childFolder(container, name) {
    const matches = container.folders.whose({ name })();
    return matches.length > 0 ? matches[0] : null;
  }

  function parseRequiredDate(value, fieldName, sourceId) {
    const numeric = typeof value === "number" || (typeof value === "string" && /^-?\\d+(?:\\.\\d+)?$/.test(value));
    const timestamp = numeric ? Number(value) : value;
    const parsed = new Date(numeric && Math.abs(timestamp) < 100000000000 ? timestamp * 1000 : timestamp);
    if (Number.isNaN(parsed.getTime())) {
      throw new Error(`Invalid ${fieldName} for note ${sourceId}: ${value}`);
    }
    return parsed;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;");
  }

  function normalizedTags(tags) {
    return (Array.isArray(tags) ? tags : [])
      .map((tag) => String(tag).trim().replace(/^#+/, "").replace(/\\s+/g, "-"))
      .filter(Boolean)
      .map((tag) => `#${tag}`);
  }

  function bodyWithMetadata(body, tags, marker) {
    const renderedTags = normalizedTags(tags);
    const tagFooter = renderedTags.length > 0
      ? `<p>${renderedTags.map(escapeHtml).join(" ")}</p>`
      : "";
    return `${body}${tagFooter}<p>UpNote source: ${escapeHtml(marker)}</p>`;
  }

  function sourceMarker(body) {
    const match = String(body).match(/UpNote source: (upnote:[^<\s]+)/);
    return match ? match[1] : null;
  }

  function collectImportedNotes(container, wantedMarkers, foundNotes) {
    for (const note of container.notes()) {
      const marker = sourceMarker(note.body());
      if (marker && wantedMarkers[marker]) {
        foundNotes[marker] = note;
      }
    }
    for (const folder of container.folders()) {
      collectImportedNotes(folder, wantedMarkers, foundNotes);
    }
  }

  function collectImportedMarkers(container, markers) {
    for (const note of container.notes()) {
      const marker = sourceMarker(note.body());
      if (marker && Object.prototype.hasOwnProperty.call(markers, marker)) {
        markers[marker] = true;
      }
    }
    for (const folder of container.folders()) {
      collectImportedMarkers(folder, markers);
    }
  }

  if (payload.operation === "accounts") {
    return JSON.stringify({ accounts: accounts.map((candidate) => candidate.name()) });
  }

  function ensureFolder(container, name) {
    const existing = childFolder(container, name);
    if (existing) {
      return existing;
    }
    return notesApp.make({
      new: "folder",
      at: container,
      withProperties: { name },
    });
  }

  function resolveContainer(folderPath) {
    if (!folderPath || folderPath.length === 0) {
      return account;
    }

    let container = account;
    for (const segment of folderPath) {
      container = ensureFolder(container, segment);
    }
    return container;
  }

  if (payload.operation === "verify") {
    const markers = {};
    for (const marker of payload.markers || []) {
      markers[marker] = false;
    }
    collectImportedMarkers(account, markers);
    return JSON.stringify({ markers });
  }

  const notes = payload.notes || [];
  const wantedMarkers = {};
  for (const note of notes) {
    wantedMarkers[note.marker] = true;
  }
  const existingNotes = {};
  collectImportedNotes(account, wantedMarkers, existingNotes);

  const results = notes.map((note) => {
    const folderPath = Array.isArray(note.folder) ? note.folder : [];
    try {
      const body = bodyWithMetadata(readText(note.html_path), note.tags, note.marker);
      const container = resolveContainer(folderPath);
      const creationDate = parseRequiredDate(note.created_at, "created_at", note.source_id);
      const modificationDate = parseRequiredDate(note.updated_at, "updated_at", note.source_id);
      const existing = existingNotes[note.marker];
      if (existing) {
        existing.name = note.title;
        existing.body = body;
        existing.modificationDate = modificationDate;
        return {
          source_id: note.source_id,
          status: "updated",
          marker: note.marker,
          folder_path: folderPath,
        };
      }
      notesApp.make({
        new: "note",
        at: container,
        withProperties: { name: note.title, body, creationDate, modificationDate },
      });
      return {
        source_id: note.source_id,
        status: "created",
        marker: note.marker,
        folder_path: folderPath,
      };
    } catch (error) {
      return {
        source_id: note.source_id,
        status: "failed",
        marker: note.marker,
        folder_path: folderPath,
        error: String(error),
      };
    }
  });

  return JSON.stringify({ notes: results });
}
