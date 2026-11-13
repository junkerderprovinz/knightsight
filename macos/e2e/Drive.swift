import AppKit
import ApplicationServices

// Shares a target window through KnightSight.app the way a person does, with real clicks on
// the panel and the target, then works in the share through the MCP server the way an
// assistant does. Arguments: the app, the target program, the MCP server and the directory
// for the pictures and the log.
let args = CommandLine.arguments
let appPath = args[1], targetPath = args[2], mcpPath = args[3]
let out = URL(fileURLWithPath: args[4])
let eventsPath = out.appendingPathComponent("target-events.log").path
FileManager.default.createFile(atPath: out.appendingPathComponent("e2e.log").path, contents: nil)
FileManager.default.createFile(atPath: eventsPath, contents: nil)
let logFile = try FileHandle(forWritingTo: out.appendingPathComponent("e2e.log"))

let nothingShared = "Nothing is shared right now"

func say(_ line: String) {
    print(line)
    fflush(stdout)
    logFile.write(Data((line + "\n").utf8))
}

struct Failure: Error {
    let message: String
    init(_ message: String) { self.message = message }
}

func expect(_ ok: Bool, _ what: String, _ detail: @autoclosure () -> String = "") throws {
    guard ok else { throw Failure("\(what): \(detail())") }
    say("ok    \(what)")
}

func wait<T>(_ what: String, _ seconds: Double = 15, _ probe: () throws -> T?) throws -> T {
    let end = Date().addingTimeInterval(seconds)
    repeat {
        if let value = try probe() { return value }
        usleep(100_000)
    } while Date() < end
    throw Failure("timed out waiting for \(what)")
}

struct Win {
    let id: CGWindowID, pid: pid_t, layer: Int, bounds: CGRect, name: String, owner: String
}

/// Front to back.
func onScreen() -> [Win] {
    let entries = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
    return entries.compactMap { e in
        guard let id = e[kCGWindowNumber as String] as? CGWindowID, let pid = e[kCGWindowOwnerPID as String] as? pid_t,
              let layer = e[kCGWindowLayer as String] as? Int, let box = e[kCGWindowBounds as String] as? NSDictionary,
              let bounds = CGRect(dictionaryRepresentation: box as CFDictionary)
        else { return nil }
        return Win(id: id, pid: pid, layer: layer, bounds: bounds,
                   name: e[kCGWindowName as String] as? String ?? "", owner: e[kCGWindowOwnerName as String] as? String ?? "")
    }
}

func window(_ name: String, owner: String? = nil) throws -> Win {
    try wait("the window \(name)", 30) { onScreen().first { $0.name == name && $0.layer == 0 && (owner == nil || $0.owner == owner) } }
}

func frontmost() -> String {
    onScreen().first { $0.layer == 0 && $0.bounds.width > 50 }?.name ?? ""
}

var pointer: CGPoint { CGEvent(source: nil)!.location }

// Events from a source with the hardware's state ID count toward that state, which the
// panel reads to notice the click that picks a window.
let hardware = CGEventSource(stateID: .hidSystemState)

func mouse(_ type: CGEventType, _ p: CGPoint) {
    CGEvent(mouseEventSource: hardware, mouseType: type, mouseCursorPosition: p, mouseButton: .left)!.post(tap: .cghidEventTap)
}

func buttonStates() -> String {
    "hid \(CGEventSource.buttonState(.hidSystemState, button: .left)), session \(CGEventSource.buttonState(.combinedSessionState, button: .left)), pressedMouseButtons \(NSEvent.pressedMouseButtons)"
}

/// A slow click, so the panel's poll of the mouse button sees it go down and up.
func press(_ p: CGPoint) {
    mouse(.mouseMoved, p)
    usleep(200_000)
    mouse(.leftMouseDown, p)
    usleep(150_000)
    say("      button held at \(p): \(buttonStates())")
    mouse(.leftMouseUp, p)
    usleep(400_000)
}

func keys(_ code: CGKeyCode, _ flags: CGEventFlags) {
    for down in [true, false] {
        let event = CGEvent(keyboardEventSource: nil, virtualKey: code, keyDown: down)!
        event.flags = flags
        event.post(tap: .cghidEventTap)
        usleep(50_000)
    }
}

func attribute(_ element: AXUIElement, _ name: String) -> AnyObject? {
    var value: CFTypeRef?
    return AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success ? value : nil
}

func textArea(of pid: pid_t) -> AXUIElement? {
    func find(_ e: AXUIElement, _ depth: Int) -> AXUIElement? {
        if attribute(e, kAXRoleAttribute) as? String == kAXTextAreaRole { return e }
        guard depth < 8, let children = attribute(e, kAXChildrenAttribute) as? [AXUIElement] else { return nil }
        return children.lazy.compactMap { find($0, depth + 1) }.first
    }
    return find(AXUIElementCreateApplication(pid), 0)
}

func text(of pid: pid_t, _ name: String = kAXValueAttribute) -> String? {
    textArea(of: pid).flatMap { attribute($0, name) as? String }
}

struct Rgb: CustomStringConvertible {
    let r: Int, g: Int, b: Int
    var description: String { "(\(r), \(g), \(b))" }
    var red: Bool { r > 200 && g < 80 && b < 80 }
    var blue: Bool { b > 200 && r < 80 && g < 80 }
    var white: Bool { r > 235 && g > 235 && b > 235 }
}

func pixel(_ png: Data, _ p: CGPoint) -> Rgb {
    let rep = NSBitmapImageRep(data: png)!
    let c = rep.colorAt(x: Int(p.x), y: Int(p.y))!.usingColorSpace(.sRGB)!
    return Rgb(r: Int(c.redComponent * 255), g: Int(c.greenComponent * 255), b: Int(c.blueComponent * 255))
}

struct ToolReply {
    let text: String, image: Data?, isError: Bool
}

/// The real MCP server over stdio, one JSON-RPC line each way.
final class Mcp {
    private let process = Process(), input = Pipe(), output = Pipe()
    private var buffer = Data()
    private var n = 0

    init(_ script: String) throws {
        process.executableURL = URL(fileURLWithPath: "/usr/bin/env")
        process.arguments = ["node", script]
        process.standardInput = input
        process.standardOutput = output
        try process.run()
        _ = try call("initialize", ["protocolVersion": "2025-06-18", "capabilities": [String: Any]()])
    }

    func call(_ method: String, _ params: [String: Any]) throws -> [String: Any] {
        n += 1
        let message: [String: Any] = ["jsonrpc": "2.0", "id": n, "method": method, "params": params]
        input.fileHandleForWriting.write(try JSONSerialization.data(withJSONObject: message) + Data("\n".utf8))
        while true {
            if let end = buffer.firstIndex(of: 0x0A) {
                let line = buffer.subdata(in: buffer.startIndex..<end)
                buffer = buffer.subdata(in: buffer.index(after: end)..<buffer.endIndex)
                let reply = try JSONSerialization.jsonObject(with: line) as? [String: Any] ?? [:]
                guard let result = reply["result"] as? [String: Any] else { throw Failure("the MCP server answered \(reply)") }
                return result
            }
            let chunk = output.fileHandleForReading.availableData
            if chunk.isEmpty { throw Failure("the MCP server ended") }
            buffer.append(chunk)
        }
    }

    func tool(_ name: String, _ arguments: [String: Any] = [:]) throws -> ToolReply {
        let result = try call("tools/call", ["name": name, "arguments": arguments])
        let content = result["content"] as? [[String: Any]] ?? []
        let text = content.filter { $0["type"] as? String == "text" }.compactMap { $0["text"] as? String }.joined(separator: "\n")
        let image = content.first { $0["type"] as? String == "image" }.flatMap { $0["data"] as? String }.flatMap { Data(base64Encoded: $0) }
        let reply = ToolReply(text: text, image: image, isError: result["isError"] as? Bool ?? false)
        say("      \(name) \(arguments.isEmpty ? "" : "\(arguments) ")-> \(text.replacingOccurrences(of: "\n", with: " | "))")
        return reply
    }

    func stop() {
        process.terminate()
    }
}

var started: [Process] = []

@discardableResult
func spawn(_ path: String, _ arguments: [String]) throws -> Process {
    let p = Process()
    p.executableURL = URL(fileURLWithPath: path)
    p.arguments = arguments
    try p.run()
    started.append(p)
    return p
}

func events() -> [String] {
    (try? String(contentsOfFile: eventsPath, encoding: .utf8))?.split(separator: "\n").map(String.init) ?? []
}

func save(_ reply: ToolReply, _ name: String) throws {
    guard let png = reply.image else { throw Failure("look gave no picture: \(reply.text)") }
    try png.write(to: out.appendingPathComponent(name))
    say("      saved \(name)")
}

/// The runner's whole screen, to see what went wrong.
func snap(_ name: String) {
    try? spawn("/usr/sbin/screencapture", ["-x", out.appendingPathComponent(name).path]).waitUntilExit()
}

func run(_ mcp: Mcp) throws {
    let screen = CGDisplayBounds(CGMainDisplayID())
    say("macOS \(ProcessInfo.processInfo.operatingSystemVersionString), main display \(Int(screen.width)) x \(Int(screen.height))")
    try expect(AXIsProcessTrusted(), "the driver may read other apps through accessibility")

    try spawn("/usr/bin/open", ["--stdout", out.appendingPathComponent("app.log").path,
                                "--stderr", out.appendingPathComponent("app.log").path, appPath]).waitUntilExit()
    let panel = try window("KnightSight", owner: "KnightSight")

    // Below the panel, which opens in the middle of the screen, so neither hides the other.
    try spawn(targetPath, ["Target", "ff0000", "40", "\(Int(panel.bounds.maxY) + 20)", eventsPath])
    var shared = try window("Target")
    try expect(shared.bounds.width == 400, "the target is 400 points wide", "\(shared.bounds)")
    let titleBar = shared.bounds.height - 300
    say("      panel at \(panel.bounds), target at \(shared.bounds)")
    func onPanel(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: panel.bounds.minX + x, y: panel.bounds.minY + y) }
    func edges() -> [Win] { onScreen().filter { $0.pid == panel.pid && min($0.bounds.width, $0.bounds.height) <= 8 } }

    let before = try wait("the panel's port", 30) { () -> ToolReply? in
        let reply = try mcp.tool("look")
        return reply.text.contains("is not running") ? nil : reply
    }
    try expect(before.isError && before.text.contains(nothingShared), "look before sharing is refused", before.text)

    let band = CGPoint(x: shared.bounds.minX + 200, y: shared.bounds.minY + titleBar + 50)
    var chosen = false
    for attempt in 1...3 where !chosen {
        press(onPanel(110, 156))
        if attempt > 1 { press(onPanel(110, 156)) }
        press(band)
        snap("choose-\(attempt).png")
        chosen = (try? wait("the frame", 5) { edges().count == 4 ? true : nil }) ?? false
    }
    try expect(chosen, "choosing the target through the panel draws the frame")
    try expect(try mcp.tool("look").text.contains(nothingShared), "a chosen window is not shared yet")

    var first: ToolReply?
    for _ in 1...3 where first == nil {
        press(onPanel(456, 156))
        first = try? wait("the share to start", 5) { () -> ToolReply? in
            let reply = try mcp.tool("look")
            return reply.text.contains(nothingShared) ? nil : reply
        }
    }
    guard let look = first else { throw Failure("sharing did not start") }
    try save(look, "1-shared.png")
    try expect(!look.isError, "look works once sharing is on", look.text)

    shared = try window("Target")
    let size = NSBitmapImageRep(data: look.image!)!
    let scale = CGFloat(size.pixelsWide) / shared.bounds.width
    try expect(look.text.contains("Target, \(size.pixelsWide) x \(size.pixelsHigh)"), "the reply names the window and the picture size", look.text)
    try expect(abs(CGFloat(size.pixelsHigh) - shared.bounds.height * scale) <= 1 && (scale == 1 || scale == 2),
               "the picture has the window's size", "\(size.pixelsWide) x \(size.pixelsHigh) for \(shared.bounds)")
    func inPicture(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x * scale, y: (titleBar + y) * scale) }
    try expect(pixel(look.image!, inPicture(50, 50)).red, "the band shows red", "\(pixel(look.image!, inPicture(50, 50)))")
    try expect(pixel(look.image!, inPicture(50, 150)).white, "the text area shows white", "\(pixel(look.image!, inPicture(50, 150)))")

    let frame = edges().map(\.bounds).reduce(CGRect.null) { $0.union($1) }
    let width = shared.bounds.minX - frame.minX
    try expect((2...6).contains(width) && frame == shared.bounds.insetBy(dx: -width, dy: -width),
               "the frame lies tight around the shared window", "frame \(frame), window \(shared.bounds)")

    try spawn(targetPath, ["Other", "0000ff", "\(Int(shared.bounds.minX) + 150)", "\(Int(shared.bounds.minY) + 80)", eventsPath])
    let other = try window("Other")
    let otherBand = CGPoint(x: other.bounds.midX, y: other.bounds.minY + titleBar + 50)
    press(otherBand)
    try expect((try? wait("Other in front", 5) { frontmost() == "Other" ? true : nil }) ?? false, "the covering window comes to the front", frontmost())
    let order = onScreen().map(\.id)
    try expect(edges().allSatisfy { order.firstIndex(of: $0.id)! > order.firstIndex(of: other.id)! },
               "the frame stays below the covering window")

    let covered = try mcp.tool("look")
    try save(covered, "2-covered.png")
    for (x, y, ok, what) in [(300.0, 75.0, \Rgb.red, "band"), (300.0, 250.0, \Rgb.white, "text area")] {
        let seen = pixel(covered.image!, inPicture(x, y))
        try expect(seen[keyPath: ok], "the covered \(what) still shows the target, not the window on top", "\(seen)")
    }

    let rest = pointer
    let otherEvents = events().filter { $0.hasPrefix("Other") }.count
    say("      pointer rests at \(rest)")

    let click = try mcp.tool("click", ["x": Double(inPicture(200, 150).x), "y": Double(inPicture(200, 150).y)])
    try expect(!click.isError && click.text == "Clicked.", "click is done", click.text)
    try expect((try? wait("the click", 5) { events().contains("Target click 200 150") ? true : nil }) ?? false,
               "the click lands in the text area at the point aimed at", events().suffix(5).joined(separator: ", "))

    let hello = "Hello from KnightSight"
    let typed = try mcp.tool("type", ["text": hello])
    try expect(!typed.isError, "type is done", typed.text)
    let arrived = try? wait("the text", 5) { text(of: shared.pid) == hello ? true : nil }
    try expect(arrived ?? false, "the typed text arrives in the target", "the text area holds \(text(of: shared.pid) ?? "nothing")")
    try save(try mcp.tool("look"), "3-typed.png")

    let all = try mcp.tool("key", ["keys": "cmd+a"])
    try expect(!all.isError, "cmd+a is done", all.text)
    let selected = try? wait("the selection", 5) { text(of: shared.pid, kAXSelectedTextAttribute) == hello ? true : nil }
    try expect(selected ?? false, "cmd+a selects the whole text", "the selection is \(text(of: shared.pid, kAXSelectedTextAttribute) ?? "nothing")")
    _ = try mcp.tool("type", ["text": "Replaced"])
    let replaced = try? wait("the replacement", 5) { text(of: shared.pid) == "Replaced" ? true : nil }
    try expect(replaced ?? false, "typing over the selection replaces it", "the text area holds \(text(of: shared.pid) ?? "nothing")")
    try save(try mcp.tool("look"), "4-replaced.png")

    let outside = try mcp.tool("click", ["x": size.pixelsWide + 20, "y": 10])
    try expect(outside.isError && outside.text.contains("outside the share"), "a click outside the share is refused", outside.text)
    let windowsKey = try mcp.tool("key", ["keys": "win+r"])
    try expect(windowsKey.isError && windowsKey.text.contains("no Windows key"), "the Windows key is refused", windowsKey.text)

    try expect(pointer == rest, "the pointer did not move", "it is at \(pointer), it rested at \(rest)")
    try expect(frontmost() == "Other", "the covering window stayed in front", frontmost())
    try expect(events().filter { $0.hasPrefix("Other") }.count == otherEvents, "nothing reached the covering window",
               events().filter { $0.hasPrefix("Other") }.joined(separator: ", "))

    keys(7, [.maskControl, .maskAlternate, .maskShift])
    let ended = try? wait("the hotkey to end the share", 5) { try mcp.tool("look").text.contains(nothingShared) ? true : nil }
    try expect(ended ?? false, "ctrl+option+shift+x ends the share")
}

let mcp = try Mcp(mcpPath)
var failed = false
do {
    try run(mcp)
    say("all checks passed")
} catch let failure as Failure {
    say("fail  \(failure.message)")
    failed = true
    snap("failed.png")
}
say("target events: \(events().joined(separator: ", "))")
mcp.stop()
for p in started where p.isRunning { p.terminate() }
NSRunningApplication.runningApplications(withBundleIdentifier: "io.github.junkerderprovinz.knightsight").forEach { $0.terminate() }
exit(failed ? 1 : 0)
