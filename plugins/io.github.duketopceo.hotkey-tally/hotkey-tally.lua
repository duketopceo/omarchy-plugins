-- hotkey-tally: opt-in counting for Hyprland bindings.
--
-- Why this is a helper and not a generator: on this Omarchy build every bind
-- reports dispatcher "__lua" through `hyprctl binds -j`, with `arg` set to an
-- internal handle id. The original command string is not recoverable, so a
-- binding cannot be wrapped after the fact. Counting has to happen where the
-- bind is declared.
--
-- Usage in ~/.config/hypr/bindings.lua:
--
--   local tally = dofile(os.getenv("HOME") .. "/.config/hypr/hotkey-tally.lua")
--   tally.bind("SUPER + SHIFT + W", "Omawrite", { launch = "omawrite" })
--   tally.bind("SUPER + M", "Blip iMessage", "blip-toggle")
--
-- Only binds routed through tally.bind (or tally.wrap) are counted. Everything
-- else keeps working untouched and stays uncounted.

local M = {}

local tally_bin = os.getenv("HOME") .. "/.config/omarchy/plugins/io.github.duketopceo.hotkey-tally/bin/hotkey-tally.py"
local python = "/usr/bin/python3"

local function shq(s)
  -- single-quote for the shell; the compositor runs exec strings through sh -c
  return "'" .. tostring(s):gsub("'", "'\\''") .. "'"
end

-- Record asynchronously so the shortcut action does not wait for Python.
function M.wrap(cmd, key, label)
  local record = string.format(
    "%s %s record --key %s --label %s",
    python, shq(tally_bin), shq(key), shq(label)
  )
  return "(" .. record .. " >/dev/null 2>&1) & " .. tostring(cmd)
end

-- like o.bind, but counted. Pass the same third argument o.bind accepts:
-- either a command string or a { launch = "..." } table.
function M.bind(key, label, target, opts)
  local cmd
  if type(target) == "table" then
    if target.launch and not target.focus then
      cmd = "uwsm-app -- " .. target.launch
    else
      return o.bind(key, label, target, opts) -- not an exec target: leave alone
    end
  else
    cmd = tostring(target)
  end
  return o.bind(key, label, M.wrap(cmd, key, label), opts)
end

return M
