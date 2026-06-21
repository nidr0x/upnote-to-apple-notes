function run() {
  ObjC.import("Foundation");

  const notesApp = Application("Notes");
  notesApp.includeStandardAdditions = true;
  const stdin = $.NSFileHandle.fileHandleWithStandardInput;
  const data = stdin.readDataToEndOfFile;
  const payload = JSON.parse(ObjC.unwrap($.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding)));
  const account = notesApp.accounts()[0];

  if (!account) {
    throw new Error("No Apple Notes account is available");
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

  const notes = (payload.notes || []).map((note) => {
    const folderPath = Array.isArray(note.folder) ? note.folder : [];
    try {
      const body = readText(note.html_path);
      const container = resolveContainer(folderPath);
      notesApp.make({
        new: "note",
        at: container,
        withProperties: {
          name: note.title,
          body,
        },
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

  return JSON.stringify({ notes });
}
