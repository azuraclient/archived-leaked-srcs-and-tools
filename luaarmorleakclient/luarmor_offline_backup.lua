local dir = "luarmor_cache/"
local old;
old = hookfunction(game.HttpGet, function(Self, Url, ...)
  if typeof(Url) == "string" and Url:find("https://api.luarmor") then
    local files = isfolder(dir) and listfiles(dir) or {}
    local content = old(Self, Url, ...)
    writefile(files .. `file_{#files}.lua`, content)
    return content
  end
  return old(Self, Url, ...)
end)