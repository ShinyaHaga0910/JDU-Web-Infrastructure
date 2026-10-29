// Bound before buffering or parsing. A rejected stream is drained without
// destroying its socket, so the server can still return the generic 413.
export const MAX_BODY=16384;
export async function readBody(request) {
  if (['GET','HEAD'].includes(request.method)) return undefined;
  const length=request.headers['content-length'];
  if (length!==undefined && (!/^[0-9]+$/.test(length) || Number(length)>MAX_BODY)) {
    request.resume(); throw Object.assign(new Error('Payload too large'),{status:413});
  }
  let size=0; const chunks=[];
  for await (const chunk of request.iterator({destroyOnReturn:false})) {
    size+=chunk.length;
    if (size>MAX_BODY) {request.resume();throw Object.assign(new Error('Payload too large'),{status:413});}
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}
