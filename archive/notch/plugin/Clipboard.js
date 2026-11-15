// Pure logic for the Clipboard tab (R7). No Qt types.
//
// Source: `cliphist list` -> lines "<id>\t<preview>". Newest first. Entries are
// classified (text / link / path / image), secrets are masked for display, and
// the actions are built as argv so a clipboard string never reaches a shell:
// the id is validated as digits and passed as a positional parameter.
//
// Privacy: previews live only in memory while the tab is open; nothing here
// logs, caches or writes them anywhere. Masking happens at parse time, so a
// masked entry's text never reaches the view (the copy action decodes it from
// cliphist itself, intact).

var MAX_ENTRIES = 12
var PREVIEW_MAX = 160

// cliphist and wl-copy may live in ~/.local/bin (the shell's PATH can lack it).
var PATH_FIX = 'PATH="$HOME/.local/bin:$PATH";'

function listArgs(n) {
  var count = Math.max(1, Math.min(50, Math.floor(Number(n) || MAX_ENTRIES)))
  return ["sh", "-c", PATH_FIX + "cliphist list 2>/dev/null | head -n " + count]
}

function validId(id) { return /^[0-9]{1,18}$/.test(String(id)) }

// Copy entry `id` back to the clipboard. null when the id is not plain digits.
function copyArgs(id) {
  if (!validId(id)) return null
  return ["sh", "-c", PATH_FIX + 'cliphist decode "$1" | wl-copy', "notch-clip", String(id)]
}

// Open a link entry in the default browser.
function openArgs(id) {
  if (!validId(id)) return null
  return ["sh", "-c", PATH_FIX + 'u=$(cliphist decode "$1" | head -c 2000 | head -n1); case "$u" in http://*|https://*) exec xdg-open "$u";; esac',
          "notch-clip", String(id)]
}

// Open the folder holding a path entry (or the directory itself).
function folderArgs(id) {
  if (!validId(id)) return null
  return ["sh", "-c", PATH_FIX + 'p=$(cliphist decode "$1" | head -c 2000 | head -n1); p="${p#file://}"; case "$p" in "~"/*) p="$HOME/${p#\\~/}";; esac; [ -e "$p" ] || exit 1; [ -d "$p" ] || p=$(dirname "$p"); exec xdg-open "$p"',
          "notch-clip", String(id)]
}

var URL_RE = /^https?:\/\/[^\s]+$/i
var PATH_RE = /^(file:\/\/)?(~|\/)[^\s\u0000]*\/[^\s\u0000]*$|^~\/[^\s]+$/
var IMAGE_RE = /^\[\[\s*binary data\s+([0-9.]+\s*[KMG]?i?B)\s+(\w+)(?:\s+(\d+x\d+))?\s*\]\]$/i

var SECRET_PREFIX = /(^|[\s"'=:])(sk-[A-Za-z0-9_-]{10,}|sk_(live|test)_\S{8,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_\w{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{12,}|AIza[0-9A-Za-z_-]{20,}|eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,})/
var SECRET_WORD = /pass(word|wd|phrase)|secret|api[_-]?key|private key|bearer\s+\S{8,}|token\s*[=:]/i

// Does this text look like a credential? Conservative on purpose: a false
// positive only hides a preview (click still copies), a miss shows a secret.
function looksSecret(text) {
  var t = String(text || "")
  if (t === "") return false
  if (/^-----BEGIN [A-Z ]*PRIVATE KEY-----/.test(t)) return true
  if (SECRET_PREFIX.test(t) || SECRET_WORD.test(t)) return true
  var words = t.split(/\s+/)
  for (var i = 0; i < words.length; i++) {
    var w = words[i]
    if (w.length < 32 || w.charAt(0) === "/" || w.charAt(0) === "~") continue
    if (/^[0-9a-fA-F]{32,}$/.test(w)) return true
    if (/^[A-Za-z0-9+\/=_-]{32,}$/.test(w) && /[0-9]/.test(w) && /[A-Za-z]/.test(w)) return true
  }
  return false
}

function squash(s, max) {
  var t = String(s).replace(/[\u0000-\u001f\u007f]+/g, " ").replace(/\s+/g, " ").trim()
  return t.length > max ? t.slice(0, max - 1) + "…" : t
}

// One cliphist line -> entry, or null for a malformed / empty one.
//   { id, kind: "text"|"link"|"path"|"image", secret, text (display), canOpen, canFolder }
function parseLine(line) {
  var m = /^(\d{1,18})\t([\s\S]*)$/.exec(String(line))
  if (!m) return null
  var raw = m[2].trim()
  var img = IMAGE_RE.exec(raw)
  if (img) {
    return { id: m[1], kind: "image", secret: false, canOpen: false, canFolder: false,
             text: "Image" + (img[3] ? " " + img[3] : "") + " · " + img[2].toLowerCase() + " · " + img[1].replace(/\s+/g, " ") }
  }
  if (raw === "") return null
  var secret = looksSecret(raw)
  var kind = URL_RE.test(raw) ? "link" : (PATH_RE.test(raw) ? "path" : "text")
  return {
    id: m[1], kind: kind, secret: secret,
    text: secret ? "Hidden · " + Math.min(raw.length, 999) + " characters" : squash(raw, PREVIEW_MAX),
    canOpen: kind === "link" && !secret,
    canFolder: kind === "path" && !secret
  }
}

function parseList(text, max) {
  var cap = Math.max(1, Math.min(50, Math.floor(Number(max) || MAX_ENTRIES)))
  var out = []
  String(text || "").split("\n").forEach(function (line) {
    if (out.length >= cap) return
    var e = parseLine(line)
    if (e) out.push(e)
  })
  return out
}

if (typeof module !== "undefined") {
  module.exports = { MAX_ENTRIES: MAX_ENTRIES, listArgs: listArgs, copyArgs: copyArgs, openArgs: openArgs, folderArgs: folderArgs,
    looksSecret: looksSecret, parseLine: parseLine, parseList: parseList, validId: validId }
}
