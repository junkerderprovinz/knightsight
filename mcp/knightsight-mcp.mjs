// MCP server for the window or region shared through KnightSight.exe. It keeps no state
// about the share: every call goes to the panel, which refuses anything outside the share
// and everything while nothing is shared. On the same machine it talks to the panel over a
// named pipe. When the panel runs on another one, calls reach its loopback port through one
// SSH tunnel that stays open, so a click costs a round trip and not a new SSH login.
import net from 'node:net';
import readline from 'node:readline';
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const PIPE = '\\\\.\\pipe\\knightsight';
const PORT = 47613;
const ACTIONS = ['click', 'scroll', 'type', 'key'];

const point = {
  x: { type: 'number', description: 'Horizontal position in the picture from look' },
  y: { type: 'number', description: 'Vertical position in the picture from look' },
};
const after = {
  look: { type: 'boolean', description: 'Also return a picture of the share taken after the action' },
  wait: { type: 'number', description: 'Milliseconds to wait before that picture, default 300' },
};

const tools = [
  {
    name: 'look',
    description: 'Takes a picture of the shared window or region. A shared window may lie covered. Coordinates for click and scroll refer to this picture.',
    inputSchema: { type: 'object', properties: {} },
  },
  {
    name: 'click',
    description: 'Clicks a point inside the share without moving the pointer or taking the focus from the person at the PC.',
    inputSchema: {
      type: 'object',
      properties: { ...point, right: { type: 'boolean' }, double: { type: 'boolean' }, ...after },
      required: ['x', 'y'],
    },
  },
  {
    name: 'scroll',
    description: 'Scrolls at a point inside the share. Positive amounts scroll down, one unit is one notch. A browser covered at that point scrolls with the arrow keys where it was last clicked instead.',
    inputSchema: {
      type: 'object',
      properties: { ...point, amount: { type: 'number' }, ...after },
      required: ['x', 'y', 'amount'],
    },
  },
  {
    name: 'type',
    description: 'Types text into the shared window without taking the focus. In a shared region it goes to the window last clicked there.',
    inputSchema: { type: 'object', properties: { text: { type: 'string' }, ...after }, required: ['text'] },
  },
  {
    name: 'key',
    description: 'Presses a key or a combination such as enter, ctrl+l or shift+tab. The Windows key is refused.',
    inputSchema: { type: 'object', properties: { keys: { type: 'string' }, ...after }, required: ['keys'] },
  },
  {
    name: 'steps',
    description:
      'Runs several actions in one call, in order, and stops at the first one that is refused. Each step names its action ' +
      '(click, scroll, type or key) with that action\'s fields, and may set wait to pause that many milliseconds after it. ' +
      'Set look to get a picture after the last step.',
    inputSchema: {
      type: 'object',
      properties: {
        steps: {
          type: 'array',
          items: {
            type: 'object',
            properties: {
              action: { type: 'string', enum: ACTIONS },
              ...point,
              right: { type: 'boolean' },
              double: { type: 'boolean' },
              amount: { type: 'number' },
              text: { type: 'string' },
              keys: { type: 'string' },
              wait: { type: 'number' },
            },
            required: ['action'],
          },
        },
        ...after,
      },
      required: ['steps'],
    },
  },
];

const NOT_RUNNING = 'KnightSight is not running. Start KnightSight, choose a window or a region and start sharing.';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// KNIGHTSIGHT_SSH names the machine the panel runs on, the way ssh takes it: a host,
// user@host or an alias from ~/.ssh/config. KNIGHTSIGHT_SSH_MODULE names a module instead
// whose desk() returns { host, user } or null, asked before each call, for a setup where
// the person moves between machines.
const picker = process.env.KNIGHTSIGHT_SSH_MODULE
  ? await import(pathToFileURL(process.env.KNIGHTSIGHT_SSH_MODULE).href)
  : null;

function desk() {
  if (picker) return picker.desk();
  return process.env.KNIGHTSIGHT_SSH ? { host: process.env.KNIGHTSIGHT_SSH } : null;
}

// The keepalives end a dead connection, so the next call notices and opens a new one.
function tunnelArgs(d, local) {
  const login = d.user ? ['-l', d.user, d.host] : [d.host];
  return ['ssh', ['-N', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', '-o', 'ExitOnForwardFailure=yes',
    '-o', 'ServerAliveInterval=15', '-o', 'ServerAliveCountMax=2', '-L', `127.0.0.1:${local}:127.0.0.1:${PORT}`, ...login]];
}

// One line out, one line back. A connection that closes without an answer means nobody
// is listening behind it, which through the tunnel is how a stopped share shows up.
function exchange(socket, msg) {
  return new Promise((resolve, reject) => {
    let data = '';
    socket.setEncoding('utf8');
    socket.on('connect', () => socket.write(JSON.stringify(msg) + '\n'));
    socket.on('data', (chunk) => {
      data += chunk;
      const end = data.indexOf('\n');
      if (end === -1) return;
      socket.end();
      resolve(JSON.parse(data.slice(0, end)));
    });
    socket.on('close', () => resolve(null));
    socket.on('error', reject);
  });
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

function reachable(port) {
  return new Promise((resolve) => {
    const socket = net.connect(port, '127.0.0.1');
    socket.on('connect', () => { socket.destroy(); resolve(true); });
    socket.on('error', () => resolve(false));
  });
}

let tunnel = null;

function openTunnel(d) {
  if (tunnel?.host === d.host) return tunnel.ready;
  tunnel?.child?.kill();
  const t = { child: null, host: d.host };
  t.ready = (async () => {
    const port = await freePort();
    t.child = spawn(...tunnelArgs(d, port), { stdio: 'ignore', windowsHide: true });
    t.child.on('exit', () => { if (tunnel === t) tunnel = null; });
    for (let i = 0; i < 100; i++) {
      if (t.child.exitCode !== null) break;
      if (await reachable(port)) return port;
      await sleep(100);
    }
    t.child.kill();
    if (tunnel === t) tunnel = null;
    throw new Error(`${d.host} cannot be reached over SSH.`);
  })();
  tunnel = t;
  return t.ready;
}

process.on('exit', () => tunnel?.child?.kill());

async function viaDesk(msg, d) {
  let port;
  try {
    port = await openTunnel(d);
  } catch (err) {
    return { ok: false, error: err.message };
  }
  try {
    const reply = await exchange(net.connect(port, '127.0.0.1'), msg);
    return reply ?? { ok: false, error: `${NOT_RUNNING} It was looked for on ${d.host}.` };
  } catch (err) {
    return { ok: false, error: `The tunnel to ${d.host} broke off: ${err.message}` };
  }
}

// The pipe exists only on Windows. On macOS and Linux the panel listens on the loopback port.
const local = () => (process.platform === 'win32' ? net.connect(PIPE) : net.connect(PORT, '127.0.0.1'));
const absent = (err) => err.code === 'ENOENT' || err.code === 'ECONNREFUSED';

// Between two clients the panel takes a moment to open the pipe again.
async function relay(msg) {
  for (let attempt = 0; ; attempt++) {
    try {
      return (await exchange(local(), msg)) ?? { ok: false, error: NOT_RUNNING };
    } catch (err) {
      if (attempt < 20 && (absent(err) || err.code === 'EBUSY')) {
        if (absent(err) && desk()) break;
        await sleep(100);
        continue;
      }
      if (!absent(err)) throw err;
      break;
    }
  }
  const d = desk();
  return d ? viaDesk(msg, d) : { ok: false, error: NOT_RUNNING };
}

const text = (lines, isError = false) => ({ content: [{ type: 'text', text: lines.join('\n') }], ...(isError ? { isError } : {}) });

function picture(reply, note) {
  return {
    content: [
      { type: 'text', text: [note, `${reply.title}, ${reply.width} x ${reply.height}`, reply.note].filter(Boolean).join('\n') },
      { type: 'image', data: reply.image, mimeType: 'image/png' },
    ],
  };
}

async function lookAfter(wait, lines) {
  await sleep(Math.min(Math.max(wait ?? 300, 0), 10000));
  const shot = await relay({ cmd: 'look' });
  return shot.ok ? picture(shot, lines.join(' ')) : text([...lines, shot.error], true);
}

async function steps(args) {
  const done = [];
  for (const [i, step] of (args.steps ?? []).entries()) {
    const { action, wait, ...fields } = step;
    if (!ACTIONS.includes(action)) return text([...done, `Step ${i + 1}: unknown action ${action}.`], true);
    const reply = await relay({ ...fields, cmd: action });
    if (!reply.ok) return text([...done, `Step ${i + 1} (${action}): ${reply.error}`], true);
    done.push(reply.message);
    if (wait) await sleep(Math.min(wait, 10000));
  }
  return args.look ? lookAfter(args.wait, done) : text(done);
}

async function callTool(name, args) {
  if (name === 'steps') return steps(args);
  const { look, wait, ...fields } = args;
  const reply = await relay({ ...fields, cmd: name });
  if (!reply.ok) return text([reply.error], true);
  if (name === 'look') return picture(reply);
  return look ? lookAfter(wait, [reply.message]) : text([reply.message]);
}

const send = (msg) => process.stdout.write(JSON.stringify(msg) + '\n');

const input = readline.createInterface({ input: process.stdin });
input.on('close', () => process.exit(0));
input.on('line', async (line) => {
  if (!line.trim()) return;
  const msg = JSON.parse(line);
  if (msg.id === undefined) return;
  const answer = (result) => send({ jsonrpc: '2.0', id: msg.id, result });
  try {
    switch (msg.method) {
      case 'initialize':
        return answer({
          protocolVersion: msg.params?.protocolVersion ?? '2025-06-18',
          capabilities: { tools: {} },
          serverInfo: { name: 'knightsight', version: '1.0.0' },
        });
      case 'ping':
        return answer({});
      case 'tools/list':
        return answer({ tools });
      case 'tools/call':
        return answer(await callTool(msg.params.name, msg.params.arguments ?? {}));
      default:
        return send({ jsonrpc: '2.0', id: msg.id, error: { code: -32601, message: `Unknown method ${msg.method}` } });
    }
  } catch (err) {
    send({ jsonrpc: '2.0', id: msg.id, error: { code: -32603, message: String(err.message ?? err) } });
  }
});
