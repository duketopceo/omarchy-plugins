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

local tally_bin = os.getenv("HOME") .. "/.local/state/hotkey-tally/hotkey-tally.py"
local python = "/usr/bin/python3"

local function shq(s)
  -- single-quote for the shell; the compositor runs exec strings through sh -c
  return "'" .. tostring(s):gsub("'", "'\\''") .. "'"
end

local function luaq(s)
  return '"' .. tostring(s):gsub("\\", "\\\\"):gsub('"', '\\"'):gsub("\n", "\\n") .. '"'
end

local function id_for(label)
  -- Label only, and it must stay identical to binding_id() in the Python tool:
  -- key text differs between a bind written as "SUPER + SHIFT + T" and the
  -- compositor's modmask form, so the label is the only stable join key.
  local sum = 0
  for i = 1, #tostring(label) do sum = (sum * 31 + tostring(label):byte(i)) % 4294967296 end
  return string.format("%08x", sum)
end

-- wrap an exec-style command so the tally is recorded before it runs
function M.wrap(cmd, key, label)
  local id = id_for(label)
  local record = string.format(
    "%s %s record --id %s --key %s --label %s",
    python, shq(tally_bin), shq(id), shq(key), shq(label)
  )
  return record .. " 2>/dev/null; " .. tostring(cmd)
end

-- like o.bind, but counted. Pass the same third argument o.bind accepts:
-- either a command string or a { launch = "..." } table.
function M.bind(key, label, target, opts)
  local cmd
  if type(target) == "table" then
    if target.launch then
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
