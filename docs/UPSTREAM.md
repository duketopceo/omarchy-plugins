# Upstream path

This repo stays **private**. It is the authoring tree and the laptop index.

You cannot PR this umbrella into the official marketplace. Marketplace listings require a **public** GitHub repo with `manifest.json` at the repository root ([publish guide](https://plugins.omarchy.org/publish.html)). `omarchy plugin add` has the same constraint.

## Official marketplace (community plugins)

When `lukedaduke.fan` or `lukedaduke.ticker` is ready:

1. Create a **public** repo containing only that plugin directory as the git root.
2. Run `omarchy plugin validate` on a checkout.
3. Submit the public URL at [plugins.omarchy.org/publish](https://plugins.omarchy.org/publish.html).

Keep this private repo as the source of truth; push/split to the public plugin repo when cutting a release. Do not put `machine/` (restore index) in the public plugin repos.

## Omarchy first-party (stock plugins)

`lukedaduke.agents` is a fork of stock `omarchy.agents`. Extra providers belong in a PR against Omarchy itself (the packaged `shell/plugins/agents/` tree), not the community marketplace, unless you publish the fork as its own public plugin.

## What stays private forever

- `machine/` restore index
- Host-specific helpers that assume Dell fan control / local PATH
- Anything that is not a self-contained plugin
