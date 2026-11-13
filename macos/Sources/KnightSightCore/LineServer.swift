import Darwin
import Foundation

/// Answers each line with one line, on a TCP port of the loopback interface only. The port is
/// reached through an SSH tunnel, never from the network.
public final class LineServer {
    public let port: UInt16
    private let listener: Int32
    private let answer: (String) -> String

    public init(port: UInt16, answer: @escaping (String) -> String) throws {
        let fd = socket(AF_INET, SOCK_STREAM, 0)
        guard fd >= 0 else { throw LineServer.failure() }
        var yes: Int32 = 1
        setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &yes, socklen_t(MemoryLayout<Int32>.size))
        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = port.bigEndian
        address.sin_addr.s_addr = inet_addr("127.0.0.1")
        var length = socklen_t(MemoryLayout<sockaddr_in>.size)
        let ready = withUnsafeMutablePointer(to: &address) { pointer in
            pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) { raw in
                bind(fd, raw, length) == 0 && listen(fd, 16) == 0 && getsockname(fd, raw, &length) == 0
            }
        }
        guard ready else {
            let error = LineServer.failure()
            close(fd)
            throw error
        }
        self.port = UInt16(bigEndian: address.sin_port)
        listener = fd
        self.answer = answer
    }

    public func start() {
        Thread { [self] in serve() }.start()
    }

    private static func failure() -> POSIXError {
        POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO)
    }

    private func serve() {
        while true {
            let client = accept(listener, nil, nil)
            if client < 0 {
                if errno == EINTR || errno == ECONNABORTED { continue }
                return
            }
            // A client that hangs up before its answer would otherwise end the whole app.
            var yes: Int32 = 1
            setsockopt(client, SOL_SOCKET, SO_NOSIGPIPE, &yes, socklen_t(MemoryLayout<Int32>.size))
            Thread { [self] in talk(client) }.start()
        }
    }

    private func talk(_ client: Int32) {
        defer { close(client) }
        var pending: [UInt8] = []
        var chunk = [UInt8](repeating: 0, count: 64 * 1024)
        while true {
            let count = chunk.withUnsafeMutableBytes { read(client, $0.baseAddress, $0.count) }
            guard count > 0 else { return }
            pending.append(contentsOf: chunk[..<count])
            while let end = pending.firstIndex(of: 0x0A) {
                var line = pending[..<end]
                if line.last == 0x0D { line = line.dropLast() }
                let reply = Array((answer(String(decoding: line, as: UTF8.self)) + "\n").utf8)
                pending.removeSubrange(...end)
                guard deliver(reply, to: client) else { return }
            }
        }
    }

    private func deliver(_ bytes: [UInt8], to client: Int32) -> Bool {
        var offset = 0
        while offset < bytes.count {
            let written = bytes[offset...].withUnsafeBytes { write(client, $0.baseAddress, $0.count) }
            guard written > 0 else { return false }
            offset += written
        }
        return true
    }
}
