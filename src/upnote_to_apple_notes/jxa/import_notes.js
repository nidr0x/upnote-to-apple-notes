function run() {
  ObjC.import("Foundation");

  const stdin = $.NSFileHandle.fileHandleWithStandardInput;
  const data = stdin.readDataToEndOfFile;
  const payload = JSON.parse(ObjC.unwrap($.NSString.alloc.initWithDataEncoding(data, $.NSUTF8StringEncoding)));
  const notes = (payload.notes || []).map((note) => ({
    source_id: note.source_id,
    marker: note.marker,
  }));

  return JSON.stringify({ notes });
}
