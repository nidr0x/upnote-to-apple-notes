function run() {
  const app = Application.currentApplication();
  app.includeStandardAdditions = true;

  const payload = JSON.parse(app.doShellScript("cat"));
  const notes = (payload.notes || []).map((note) => ({
    source_id: note.source_id,
    marker: note.marker,
  }));

  return JSON.stringify({ notes });
}
