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
    {
      number: 5, kind: 'wish', text: 'Call it Open.', author: '',
      marks: [{
        label: '5', x: 50, y: 30, width: 40, height: 24, image: PNG,
        element: { type: 'menu item', name: 'Edit', path: 'window "notes.txt - Notepad" > menu bar "Application" > menu item "Edit"' },
      }],
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
    assert.equal(result.content.length, 10);
    assert.match(summary.text, /^Round 2, sent 2026-11-15T13:03:12Z on "notes.txt - Notepad"/);
    assert.match(summary.text, /1180 x 720/);
    assert.match(summary.text, /^3\. Bug, from Junker: The button is cut off\.\n {3}3: 120, 80, 160 x 40$/m);
    assert.match(summary.text, /^4\. Question, from Junker: Why two scrollbars\?\n {3}4a: a pin at 400, 300\n {3}4b: 10, 20, 30 x 40$/m);
    assert.deepEqual(frame, { type: 'image', data: PNG, mimeType: 'image/png' });
    assert.deepEqual(spots.filter((part) => part.type === 'text').map((part) => part.text), ['Spot 3:', 'Spot 4a:', 'Spot 4b:', 'Spot 5:']);
    assert.equal(spots.filter((part) => part.type === 'image').length, 4);
  });
});

test('names the element a mark sits on and the way to it', async () => {
  await session(() => ROUND, async (c) => {
    const { result } = await c.call('tools/call', { name: 'pinboard', arguments: {} });
    assert.match(result.content[0].text, /^5\. Wish: Call it Open\.\n {3}5: 50, 30, 40 x 24, on window "notes\.txt - Notepad" > menu bar "Application" > menu item "Edit"$/m);
  });
});

test('puts an approval at the top, also without notes', async () => {
  const approved = { ok: true, round: 3, sent: '2026-11-18T09:00:00Z', title: 'Preview', width: 800, height: 600, image: PNG, approved: true, notes: [] };
  await session(() => approved, async (c) => {
    const { result } = await c.call('tools/call', { name: 'pinboard', arguments: {} });
    assert.match(result.content[0].text, /^Approved: everything fits\. The person looked at the preview and signed it off\.\nRound 3/);
    assert.equal(result.content.length, 2);
  });
  await session(() => ({ ...ROUND, approved: true }), async (c) => {
    const { result } = await c.call('tools/call', { name: 'pinboard', arguments: {} });
    assert.match(result.content[0].text, /^Approved: everything fits\. The person looked at the preview and signed it off, with the notes below\./);
    assert.match(result.content[0].text, /^3\. Bug, from Junker/m);
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

const SHOT = {
  ok: true, title: 'Quest Log', width: 600, height: 400, image: PNG,
  elements: [
    { ref: 'e1', role: 'edit', name: 'New quest', x: 20, y: 40, width: 400, height: 30 },
    { ref: 'e2', role: 'button', name: 'Add', x: 430, y: 40, width: 60, height: 30 },
  ],
};

test('lists the controls of a look with their refs', async () => {
  await session(() => SHOT, async (c) => {
    const { result } = await c.call('tools/call', { name: 'look', arguments: {} });
    assert.match(result.content[0].text, /^Controls:$/m);
    assert.match(result.content[0].text, /^e2 button "Add" at 430, 40, 60 x 30$/m);
    assert.equal(result.content[1].type, 'image');
  });
});

test('clicks an element by its ref', async () => {
  await session(() => ({ ok: true, message: 'Clicked.' }), async (c, seen) => {
    const { result } = await c.call('tools/call', { name: 'click', arguments: { ref: 'e2' } });
    assert.equal(result.content[0].text, 'Clicked.');
    assert.deepEqual(seen, [{ ref: 'e2', cmd: 'click' }]);
  });
});

test('says whether a refused action may have reached the window', async () => {
  await session(() => ({ ok: false, error: 'The point lies outside the share.' }), async (c) => {
    const { result } = await c.call('tools/call', { name: 'click', arguments: { x: 900, y: 10 } });
    assert.equal(result.isError, true);
    assert.match(result.content[0].text, /safe to try again/);
  });
  await session(() => ({ ok: false, error: 'The window stopped answering.', delivered: 'maybe' }), async (c) => {
    const { result } = await c.call('tools/call', { name: 'type', arguments: { text: 'hi' } });
    assert.match(result.content[0].text, /may have arrived\. Look before trying again\./);
  });
});

test('waits until a control with the text shows up', async () => {
  const answer = (request, n) => (n < 3 ? { ...SHOT, elements: [] } : SHOT);
  await session(answer, async (c, seen) => {
    const { result } = await c.call('tools/call', { name: 'wait', arguments: { text: 'add' } });
    assert.match(result.content[0].text, /^Found e2 button "Add"/);
    assert.equal(seen.length, 3);
    assert.ok(seen.every((r) => r.cmd === 'look'));
  });
});

test('gives up waiting for a control after the seconds it was given', async () => {
  await session(() => ({ ...SHOT, elements: [] }), async (c) => {
    const started = Date.now();
    const { result } = await c.call('tools/call', { name: 'wait', arguments: { text: 'Delete', seconds: 1 } });
    assert.ok(Date.now() - started < 4000);
    assert.equal(result.isError, true);
    assert.match(result.content[0].text, /within 1 second\./);
  });
});
