// Runs the MCP server over stdio against a stand-in for the panel on the pipe or port the
// server talks to. `node --test mcp/knightsight-mcp.test.mjs` runs it.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import readline from 'node:readline';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const SERVER = fileURLToPath(new URL('./knightsight-mcp.mjs', import.meta.url));
const ENDPOINT = process.platform === 'win32' ? '\\\\.\\pipe\\knightsight' : 47613;

// Answers each request line with what answer returns for it, and keeps the requests.
async function panel(answer) {
  const seen = [];
  const server = net.createServer((socket) => {
    readline.createInterface({ input: socket }).on('line', (line) => {
      const request = JSON.parse(line);
      seen.push(request);
      socket.write(JSON.stringify(answer(request, seen.length)) + '\n');
    });
  });
  await new Promise((resolve) => server.listen(ENDPOINT, resolve));
  return { seen, close: () => new Promise((resolve) => server.close(resolve)) };
}

function client() {
  const child = spawn(process.execPath, [SERVER], { stdio: ['pipe', 'pipe', 'inherit'], env: { ...process.env, KNIGHTSIGHT_SSH: '' } });
  const waiting = new Map();
  const notices = [];
  readline.createInterface({ input: child.stdout }).on('line', (line) => {
    const msg = JSON.parse(line);
    if (msg.id === undefined) notices.push(msg);
    else waiting.get(msg.id)?.(msg);
  });
  let id = 0;
  const call = (method, params) => new Promise((resolve) => {
    waiting.set(++id, resolve);
    child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
  });
  return { call, notices, close: () => child.kill() };
}

const PNG = 'iVBORw0KGgo=';
const ROUND = {
  ok: true, round: 2, sent: '2026-11-15T13:03:12Z', title: 'notes.txt - Notepad', width: 1180, height: 720, image: PNG,
  notes: [
    { number: 3, kind: 'bug', text: 'The button is cut off.', author: 'Junker', marks: [{ label: '3', x: 120, y: 80, width: 160, height: 40, image: PNG }] },
    {
      number: 4, kind: 'question', text: 'Why two scrollbars?', author: 'Junker',
      marks: [{ label: '4a', x: 400, y: 300, pin: true, image: PNG }, { label: '4b', x: 10, y: 20, width: 30, height: 40, image: PNG }],
    },
  ],
};

async function session(answer, body) {
  const p = await panel(answer);
  const c = client();
  try {
    await body(c, p.seen);
  } finally {
    c.close();
    await p.close();
  }
}

test('lists the pinboard among the tools with a wait in seconds', async () => {
  await session(() => ({ ok: true }), async (c) => {
    const { result } = await c.call('tools/list', {});
    const pinboard = result.tools.find((t) => t.name === 'pinboard');
    assert.ok(pinboard, 'pinboard is listed');
    assert.equal(pinboard.inputSchema.properties.wait.type, 'number');
  });
});

test('says how notes get sent while none have been', async () => {
  await session(() => ({ ok: true, round: 0 }), async (c, seen) => {
    const { result } = await c.call('tools/call', { name: 'pinboard', arguments: {} });
    assert.equal(result.isError, undefined);
    assert.match(result.content[0].text, /No notes have been sent yet/);
    assert.match(result.content[0].text, /Ctrl\+Shift\+A/);
    assert.deepEqual(seen, [{ cmd: 'notes' }]);
  });
});

test('returns each note with the places of its marks, the marked picture and a crop per mark', async () => {
  await session(() => ROUND, async (c) => {
    const { result } = await c.call('tools/call', { name: 'pinboard', arguments: {} });
    const [summary, frame, ...spots] = result.content;
    assert.equal(result.content.length, 8);
    assert.match(summary.text, /^Round 2, sent 2026-11-15T13:03:12Z on "notes.txt - Notepad"/);
    assert.match(summary.text, /1180 x 720/);
    assert.match(summary.text, /^3\. Bug, from Junker: The button is cut off\.\n {3}3: 120, 80, 160 x 40$/m);
    assert.match(summary.text, /^4\. Question, from Junker: Why two scrollbars\?\n {3}4a: a pin at 400, 300\n {3}4b: 10, 20, 30 x 40$/m);
    assert.deepEqual(frame, { type: 'image', data: PNG, mimeType: 'image/png' });
    assert.deepEqual(spots.filter((part) => part.type === 'text').map((part) => part.text), ['Spot 3:', 'Spot 4a:', 'Spot 4b:']);
    assert.equal(spots.filter((part) => part.type === 'image').length, 3);
  });
});

test('waits for a round not read yet', async () => {
  const answer = (request, n) => (n < 3 ? { ok: true, round: 1 } : ROUND);
  await session(answer, async (c, seen) => {
    const { result } = await c.call('tools/call', { name: 'pinboard', arguments: { wait: 30 }, _meta: { progressToken: 'p' } });
    assert.match(result.content[0].text, /^Round 2/);
    assert.equal(seen.length, 3);
    assert.ok(seen.every((r) => r.cmd === 'notes' && r.unread === true));
    assert.ok(c.notices.some((n) => n.method === 'notifications/progress' && n.params.progressToken === 'p'));
  });
});

test('gives up waiting after the time it was given', async () => {
  await session(() => ({ ok: true, round: 1 }), async (c) => {
    const started = Date.now();
    const { result } = await c.call('tools/call', { name: 'pinboard', arguments: { wait: 1 } });
    assert.ok(Date.now() - started < 4000);
    assert.equal(result.isError, undefined);
    assert.match(result.content[0].text, /No new notes within 1 second\./);
  });
});

test('passes a refusal from the panel on as an error', async () => {
  await session(() => ({ ok: false, error: 'Something broke.' }), async (c) => {
    const { result } = await c.call('tools/call', { name: 'pinboard', arguments: { wait: 30 } });
    assert.equal(result.isError, true);
    assert.equal(result.content[0].text, 'Something broke.');
  });
});
