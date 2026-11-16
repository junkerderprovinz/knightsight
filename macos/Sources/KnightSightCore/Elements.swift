import CoreGraphics
import Foundation

/// One node of a window's accessibility tree as the platform reports it, in screen points.
public struct Node {
    public var role: String
    public var subrole: String?
    /// The role of the node it hangs under, which tells a tab from a radio button.
    public var parent: String?
    public var title: String?
    public var label: String?
    /// The words of static text. An edit field's value is what someone typed, so it is never read.
    public var text: String?
    public var frame: CGRect
    public var enabled: Bool

    public init(role: String, subrole: String? = nil, parent: String? = nil, title: String? = nil, label: String? = nil,
                text: String? = nil, frame: CGRect, enabled: Bool = true) {
        self.role = role
        self.subrole = subrole
        self.parent = parent
        self.title = title
        self.label = label
        self.text = text
        self.frame = frame
        self.enabled = enabled
    }
}

/// A control in a look, in the coordinates of its picture. Click and scroll take its ref.
public struct Element: Equatable, Encodable {
    public let ref: String
    public let role: String
    public let name: String?
    public let x: Int
    public let y: Int
    public let width: Int
    public let height: Int

    public var centre: (x: Double, y: Double) {
        (Double(x) + Double(width) / 2, Double(y) + Double(height) / 2)
    }
}

public enum Elements {
    public static let limit = 150
    static let longestName = 80

    /// The role a look reports for a node, or nil for panes, groups and the like, which no one clicks.
    public static func role(of node: Node) -> String? {
        switch node.role {
        case "AXButton", "AXMenuButton", "AXDisclosureTriangle": return "button"
        case "AXLink": return "link"
        case "AXTextField", "AXTextArea": return "edit"
        case "AXComboBox", "AXPopUpButton": return "combobox"
        case "AXCheckBox": return "checkbox"
        case "AXRadioButton": return node.parent == "AXTabGroup" || node.subrole == "AXTabButton" ? "tab" : "radio"
        case "AXMenuItem": return "menuitem"
        case "AXRow": return node.subrole == "AXOutlineRow" ? "treeitem" : "listitem"
        case "AXSlider": return "slider"
        case "AXStaticText": return "text"
        default: return nil
        }
    }

    public static func isPassword(_ node: Node) -> Bool {
        node.subrole == "AXSecureTextField"
    }

    /// What a node is called, on one line and cut to a length that fits a list.
    static func name(of node: Node, role: String) -> String? {
        if isPassword(node) { return nil }
        let candidates = role == "text" ? [node.text, node.title, node.label] : [node.title, node.label]
        for case let raw? in candidates {
            let name = raw.split(whereSeparator: \.isWhitespace).joined(separator: " ")
            if !name.isEmpty { return String(name.prefix(longestName)) }
        }
        return nil
    }

    /// The nodes found in a share as the elements of its look: cut to the share, top to bottom
    /// and then left to right, and numbered e1, e2 and so on in that order.
    public static func list(_ nodes: [Node], in share: Share) -> [Element] {
        let area = share.area, scale = share.scale
        func picture(_ v: CGFloat, from origin: CGFloat) -> Int { Int(((v - origin) * scale).rounded()) }
        var found: [(role: String, name: String?, x: Int, y: Int, right: Int, bottom: Int)] = []
        for node in nodes {
            guard let role = Elements.role(of: node) else { continue }
            let name = Elements.name(of: node, role: role)
            if name == nil && (role == "text" || !node.enabled) { continue }
            let seen = node.frame.intersection(area)
            guard !seen.isNull else { continue }
            let x = picture(seen.minX, from: area.minX), right = picture(seen.maxX, from: area.minX)
            let y = picture(seen.minY, from: area.minY), bottom = picture(seen.maxY, from: area.minY)
            guard right > x, bottom > y else { continue }
            found.append((role, name, x, y, right, bottom))
        }
        found.sort { ($0.y, $0.x) < ($1.y, $1.x) }
        return found.prefix(limit).enumerated().map { i, f in
            Element(ref: "e\(i + 1)", role: f.role, name: f.name, x: f.x, y: f.y, width: f.right - f.x, height: f.bottom - f.y)
        }
    }
}

/// The process a chosen window belongs to. Its id alone could by now name a later process,
/// so the start time comes along.
public struct Owner: Equatable {
    public let pid: Int32
    public let started: Int64

    public init(pid: Int32, started: Int64) {
        self.pid = pid
        self.started = started
    }

    /// Whether a window the system lists under pid still belongs to this process.
    public func owns(_ pid: Int32, startTime: (Int32) -> Int64?) -> Bool {
        pid == self.pid && startTime(pid) == started
    }
}
