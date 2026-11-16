import AppKit
import ApplicationServices
import KnightSightCore

/// The controls of a window as accessibility reports them, for the list that comes with a look.
enum ControlTree {
    private static let shape = [kAXRoleAttribute, kAXSubroleAttribute, kAXPositionAttribute, kAXSizeAttribute,
                                kAXEnabledAttribute, kAXChildrenAttribute] as CFArray

    /// The window's nodes cut to the area, or nil when its tree cannot be read. The walk ends
    /// after budget seconds with what it found by then, so a slow app holds up a look only that long.
    static func read(_ window: WindowInfo, in area: CGRect, budget: TimeInterval = 1.5) -> [Node]? {
        guard let root = Foreground.axWindow(of: window) else { return nil }
        let deadline = Date().addingTimeInterval(budget)
        var nodes: [Node] = []
        var pending: [(element: AXUIElement, parent: String?, clip: CGRect, depth: Int)] = [(root, nil, area, 0)]
        while let next = pending.popLast() {
            let (element, parent, clip, depth) = next
            let left = deadline.timeIntervalSinceNow
            guard left > 0 else { break }
            AXUIElementSetMessagingTimeout(element, Float(min(left, 0.5)))
            var values: CFArray?
            guard AXUIElementCopyMultipleAttributeValues(element, shape, [], &values) == .success,
                  let v = values as? [AnyObject], v.count == 6, let role = v[0] as? String
            else { continue }
            let frame = rect(v[2], v[3])
            let seen = frame.map { $0.intersection(clip) } ?? .null
            var node = Node(role: role, subrole: v[1] as? String, parent: parent, frame: seen, enabled: v[4] as? Bool ?? true)
            if !seen.isNull, let kind = Elements.role(of: node) {
                if !Elements.isPassword(node) {
                    node.title = string(element, kAXTitleAttribute)
                    node.label = string(element, kAXDescriptionAttribute)
                    if kind == "text" { node.text = string(element, kAXValueAttribute) }
                }
                nodes.append(node)
            }
            // What a scroll area holds reaches past its edges, out of sight.
            let inner = role == kAXScrollAreaRole ? frame.map { clip.intersection($0) } ?? clip : clip
            guard depth < 40, let children = v[5] as? [AXUIElement] else { continue }
            for child in children.reversed() { pending.append((child, role, inner, depth + 1)) }
        }
        return nodes
    }

    private static func rect(_ position: AnyObject, _ size: AnyObject) -> CGRect? {
        guard CFGetTypeID(position) == AXValueGetTypeID(), CFGetTypeID(size) == AXValueGetTypeID() else { return nil }
        var origin = CGPoint.zero, extent = CGSize.zero
        guard AXValueGetValue(position as! AXValue, .cgPoint, &origin), AXValueGetValue(size as! AXValue, .cgSize, &extent) else { return nil }
        return CGRect(origin: origin, size: extent)
    }

    private static func string(_ element: AXUIElement, _ name: String) -> String? {
        var value: CFTypeRef?
        return AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success ? value as? String : nil
    }
}
