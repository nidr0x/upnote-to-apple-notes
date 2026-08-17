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

  function collectImportedNotes(container, wantedMarkers, foundNotes, folderPath) {
    for (const note of container.notes()) {
      const marker = sourceMarker(note.body());
      if (marker && wantedMarkers[marker]) {
        if (!foundNotes[marker]) {
          foundNotes[marker] = [];
        }
        foundNotes[marker].push({ note, folderPath });
      }
    }
    for (const folder of container.folders()) {
      collectImportedNotes(
        folder,
        wantedMarkers,
        foundNotes,
        folderPath.concat([String(folder.name())])
      );
    }
  }

  function noteSummary(record) {
    const note = record.note;
    const attachmentsById = {};
    for (const attachment of note.attachments()) {
      attachmentsById[String(attachment.id())] = String(attachment.name());
    }
    return {
      destination_id: String(note.id()),
      title: String(note.name()),
      body: String(note.body()),
      folder_path: record.folderPath,
      created_at: new Date(note.creationDate()).toISOString(),
      updated_at: new Date(note.modificationDate()).toISOString(),
      attachment_names: Object.values(attachmentsById),
    };
  }

  function ensureAttachments(note, paths) {
    const existingNames = {};
    for (const attachment of note.attachments()) {
      existingNames[String(attachment.name())] = true;
    }
    for (const path of paths || []) {
      const name = String($(path).lastPathComponent.js);
      if (!existingNames[name]) {
        notesApp.make({ new: "attachment", at: note, withData: Path(path) });
        existingNames[name] = true;
      }
    }
    return Object.keys(existingNames);
  }

  function samePath(left, right) {
    return JSON.stringify(left) === JSON.stringify(right);
  }

  function importedNoteRecords(markers) {
    const wantedMarkers = {};
    for (const marker of markers) {
      wantedMarkers[marker] = true;
    }
    const foundNotes = {};
    collectImportedNotes(account, wantedMarkers, foundNotes, []);
    const summaries = {};
    for (const marker of markers) {
      summaries[marker] = (foundNotes[marker] || []).map(noteSummary);
    }
    return summaries;
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
    return JSON.stringify({ notes: importedNoteRecords(payload.markers || []) });
  }

  if (payload.operation === "rollback") {
    const markers = (payload.notes || []).map((note) => note.marker);
    const records = importedNoteRecords(markers);
    const outcomes = (payload.notes || []).map((target) => {
      const matches = records[target.marker] || [];
      const match = matches.find(
        (candidate) => candidate.destination_id === String(target.destination_id)
      );
      if (!match) {
        return { source_id: target.source_id, status: "failed", error: "Destination note not found" };
      }
      if (
        target.expected_title && match.title !== String(target.expected_title)
      ) {
        return { source_id: target.source_id, status: "failed", error: "Destination note was edited after import" };
      }
      if (
        target.expected_updated_at &&
        Math.abs(new Date(match.updated_at).getTime() - new Date(target.expected_updated_at).getTime()) > 1000
      ) {
        return { source_id: target.source_id, status: "failed", error: "Destination note was edited after import" };
      }
      const wanted = {};
      wanted[target.marker] = true;
      const found = {};
      collectImportedNotes(account, wanted, found, []);
      const record = (found[target.marker] || []).find(
        (candidate) => String(candidate.note.id()) === String(target.destination_id)
      );
      if (!record) {
        return { source_id: target.source_id, status: "failed", error: "Destination identity changed" };
      }
      record.note.delete();
      return { source_id: target.source_id, status: "deleted" };
    });
    return JSON.stringify({ notes: outcomes });
  }

  const notes = payload.notes || [];
  const wantedMarkers = {};
  for (const note of notes) {
    wantedMarkers[note.marker] = true;
  }
  const existingNotes = {};
  collectImportedNotes(account, wantedMarkers, existingNotes, []);

  const results = notes.map((note) => {
    const folderPath = Array.isArray(note.folder) ? note.folder : [];
    try {
      const body = bodyWithMetadata(readText(note.html_path), note.tags, note.marker);
      const container = resolveContainer(folderPath);
      const creationDate = parseRequiredDate(note.created_at, "created_at", note.source_id);
      const modificationDate = parseRequiredDate(note.updated_at, "updated_at", note.source_id);
      const matches = existingNotes[note.marker] || [];
      if (matches.length > 1) {
        throw new Error(`Duplicate Apple Notes found for ${note.marker}`);
      }
      const existingRecord = matches[0];
      if (existingRecord) {
        const existing = existingRecord.note;
        if (!samePath(existingRecord.folderPath, folderPath)) {
          notesApp.move(existing, { to: container });
        }
        existing.name = note.title;
        existing.body = body;
        existing.modificationDate = modificationDate;
        const attachmentNames = ensureAttachments(existing, note.attachment_paths);
        return {
          source_id: note.source_id,
          status: "updated",
          marker: note.marker,
          folder_path: folderPath,
          destination_id: String(existing.id()),
          destination_title: String(existing.name()),
          destination_updated_at: new Date(existing.modificationDate()).toISOString(),
          attachment_names: attachmentNames,
        };
      }
      const created = notesApp.make({
        new: "note",
        at: container,
        withProperties: { name: note.title, body, creationDate, modificationDate },
      });
      const attachmentNames = ensureAttachments(created, note.attachment_paths);
      return {
        source_id: note.source_id,
        status: "created",
        marker: note.marker,
        folder_path: folderPath,
        destination_id: String(created.id()),
        destination_title: String(created.name()),
        destination_updated_at: new Date(created.modificationDate()).toISOString(),
        attachment_names: attachmentNames,
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
