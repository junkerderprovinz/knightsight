import Foundation

extension Round {
    /// The round as one HTML file that carries its pictures, labelled in the person's language.
    public func page(_ say: Say) -> String {
        let date = DateFormatter()
        date.locale = Locale(identifier: say.german ? "de" : "en")
        date.dateStyle = .long
        date.timeStyle = .short
        let heading = escaped(say.fileHeading(title))
        var page = """
        <!doctype html>
        <html lang="\(say.german ? "de" : "en")">
        <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>\(heading)</title>
        <style>
        :root { color-scheme: light dark; --ground: #f4f4f4; --surface: #ffffff; --text: #161616; --muted: #6f6f6f; }
        @media (prefers-color-scheme: dark) { :root { --ground: #161616; --surface: #262626; --text: #f4f4f4; --muted: #8d8d8d; } }
        body { margin: 0; padding: 32px 16px; background: var(--ground); color: var(--text); font: 15px/1.5 "Noto Sans", system-ui, sans-serif; }
        main { max-width: 1100px; margin: 0 auto; }
        h1 { font-size: 22px; font-weight: 600; margin: 0 0 4px; }
        .meta, .kind, .from { color: var(--muted); }
        .meta { margin: 0 0 24px; }
        img { display: block; max-width: 100%; height: auto; border-radius: 6px; }
        .note { background: var(--surface); border-radius: 10px; padding: 16px; margin: 16px 0; }
        .head { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; font-size: 13px; }
        .badge { box-sizing: border-box; min-width: 24px; height: 24px; padding: 0 6px; border-radius: 12px; display: grid; place-items: center; font-weight: 600; font-size: 12px; color: #161616; }
        .text { white-space: pre-wrap; margin: 0 0 12px; }
        figure { margin: 12px 0 0; }
        figcaption { display: flex; margin-bottom: 6px; }
        </style>
        </head>
        <body>
        <main>
        <h1>\(heading)</h1>
        <p class="meta">\(escaped(say.roundLabel(number))), \(escaped(date.string(from: sent)))</p>
        <img src="data:image/png;base64,\(image.base64EncodedString())" alt="">

        """
        for entry in entries {
            let note = entry.note
            let color = String(note.kind.color, radix: 16)
            page += "<section class=\"note\">\n<div class=\"head\"><span class=\"badge\" style=\"background: #\(color)\">\(note.number)</span>"
            page += "<span class=\"kind\">\(escaped(say.kind(note.kind)))</span>"
            if !note.author.isEmpty { page += "<span class=\"from\">\(escaped(say.from(note.author)))</span>" }
            page += "</div>\n<p class=\"text\">\(escaped(note.text))</p>\n"
            for mark in entry.marks {
                guard let crop = mark.image else { continue }
                let picture = "<img src=\"data:image/png;base64,\(crop.base64EncodedString())\" alt=\"\">"
                // One crop needs no label beside the note's own badge.
                if entry.marks.count == 1 {
                    page += picture + "\n"
                } else {
                    page += "<figure><figcaption><span class=\"badge\" style=\"background: #\(color)\">\(mark.label)</span></figcaption>\(picture)</figure>\n"
                }
            }
            page += "</section>\n"
        }
        return page + "</main>\n</body>\n</html>\n"
    }
}

func escaped(_ text: String) -> String {
    text.replacingOccurrences(of: "&", with: "&amp;")
        .replacingOccurrences(of: "<", with: "&lt;")
        .replacingOccurrences(of: ">", with: "&gt;")
        .replacingOccurrences(of: "\"", with: "&quot;")
}
