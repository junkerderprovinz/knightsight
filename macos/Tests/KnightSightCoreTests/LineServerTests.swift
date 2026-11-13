import CoreGraphics
import Darwin
import XCTest
@testable import KnightSightCore

final class LineServerTests: XCTestCase {
    func connect(to port: UInt16) throws -> Int32 {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = port.bigEndian
        address.sin_addr.s_addr = inet_addr("127.0.0.1")
        let result = withUnsafePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
                Darwin.connect(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size))
            }
        }
        XCTAssertEqual(result, 0)
        var timeout = timeval(tv_sec: 5, tv_usec: 0)
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout<timeval>.size))
        return fd
    }

    func send(_ text: String, to fd: Int32) {
        let bytes = Array(text.utf8)
        let written = bytes.withUnsafeBytes { write(fd, $0.baseAddress, $0.count) }
        XCTAssertEqual(written, bytes.count)
    }

    func receiveLine(from fd: Int32) -> String? {
        var line: [UInt8] = []
        var byte: UInt8 = 0
        while read(fd, &byte, 1) == 1 {
            if byte == 0x0A { return String(decoding: line, as: UTF8.self) }
            line.append(byte)
        }
        return nil
    }

    func testAnswersEveryLineInTurn() throws {
        let server = try LineServer(port: 0) { "seen " + $0 }
        server.start()
        let fd = try connect(to: server.port)
        defer { close(fd) }
        send("one\ntwo\r\nthr", to: fd)
        send("ee\n", to: fd)
        XCTAssertEqual(receiveLine(from: fd), "seen one")
        XCTAssertEqual(receiveLine(from: fd), "seen two")
        XCTAssertEqual(receiveLine(from: fd), "seen three")
    }

    func testServesSeveralClientsAtOnce() throws {
        let server = try LineServer(port: 0) { $0.uppercased() }
        server.start()
        let first = try connect(to: server.port), second = try connect(to: server.port)
        defer { close(first); close(second) }
        send("a\n", to: second)
        send("b\n", to: first)
        XCTAssertEqual(receiveLine(from: second), "A")
        XCTAssertEqual(receiveLine(from: first), "B")
    }

    func testOnePortHasOneListener() throws {
        let server = try LineServer(port: 0) { $0 }
        XCTAssertThrowsError(try LineServer(port: server.port) { $0 })
    }

    func testCarriesAWholeResponderReply() throws {
        let desk = FakeDesk()
        let responder = Responder(desk: desk, say: Say(german: false))
        let server = try LineServer(port: 0, answer: responder.answer)
        server.start()
        let fd = try connect(to: server.port)
        defer { close(fd) }
        send("{\"cmd\":\"click\",\"x\":4,\"y\":6}\n", to: fd)
        let line = try XCTUnwrap(receiveLine(from: fd))
        let reply = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(line.utf8)) as? [String: Any])
        XCTAssertEqual(reply["ok"] as? Bool, true)
        XCTAssertEqual(reply["message"] as? String, "Clicked.")
        XCTAssertEqual(desk.calls, [.click(CGPoint(x: 102, y: 203), right: false, double: false)])
    }
}
