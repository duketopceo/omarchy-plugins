# Omarchy Plugin Marketplace Submission

Submit a public Omarchy plugin repository to the official marketplace at `omacom/omarchy-plugin-marketplace`.

## When to use

- A plugin repo is public, validates with `omarchy plugin validate`, and the owner wants it listed.
- You need to fix a failed marketplace validation on an existing submission issue.
- You are preparing a new submission body.

## Source of truth

Always fetch the current submission rules first:

```bash
gh api repos/omacom/omarchy-plugin-marketplace/contents/SUBMISSION.md --jq '.download_url'
```

Open that URL and read it. The rules below are a cached snapshot; the live file is authoritative.

## Pre-submission checklist

1. Repo is public.
2. `manifest.json` is at the repository root.
3. README has installation and removal instructions.
4. A LICENSE file is at the root.
5. External dependencies are documented.
6. Plugin ID is globally unique and not in the reserved `omarchy.*` namespace. Prefer `io.github.<user>.<name>`.
7. Run `omarchy plugin validate <repo>` and fix any errors.
8. Optional root preview: `preview.png`, `preview.jpg`, `preview.jpeg`, `preview.webp`, or `preview.avif`.

## Allowed values

### Categories (choose exactly one)

- `Appearance`
- `Desktop`
- `Developer Tools`
- `Hardware`
- `Kids`
- `Productivity`
- `System`
- `Widgets`
- `Other`

### Tags (choose one to three)

- `ai`
- `bar`
- `education`
- `games`
- `hyprland`
- `kids`
- `launcher`
- `media`
- `power-management`
- `quickshell`
- `security`
- `system`
- `workspaces`

Category and tag values are case-sensitive. Tags must be lowercase. Hyphenate `power-management`.

## Required issue body format

Create the issue body with exactly these six headings in exactly this order. Do not add extra headings. Do not remove any heading.

```markdown
### Repository URL

https://github.com/<owner>/<repo>

### Category

<exact_category>

### Tags

<tag1>, <tag2>, <tag3>

### Suggest a missing tag

_No response_

### Maintainer notes

<optional description, preview link, or other context>

### Submission checklist

- [x] The repository is public and contains installation and removal instructions.
- [x] I have documented the plugin license and any external dependencies.
- [x] I confirm that I own or have permission to submit this plugin and its preview assets.
- [x] The plugin does not overwrite user configuration without explicit consent.
- [x] I understand that approval is for listing and is not a security review.
```

Keep every checklist item checked and verbatim. Put all extra context under `Maintainer notes`. If there is no missing tag, keep `_No response_` exactly.

## Title format

```
[Plugin]: <human-readable plugin name>
```

## Create the issue

```bash
gh issue create \
  --repo omacom/omarchy-plugin-marketplace \
  --title "[Plugin]: <Plugin Name>" \
  --body-file /tmp/omarchy-plugin-submission.md
```

If the body needs changing, edit the same issue instead of opening a duplicate:

```bash
gh issue edit <issue-number> --repo omacom/omarchy-plugin-marketplace --body-file /tmp/omarchy-plugin-submission.md
```

Editing a submission issue re-runs validation.

## Common validation failures

### "Submission fields are missing, reordered, or malformed"

The six headings are not exactly in the order above, extra headings were added, or the checklist text was edited. Restore the exact headings and checklist, move any extra text into `Maintainer notes`, and re-save the issue.

### Wrong category or tag

- Category must be one of the allowed values above, copied without backticks or bullets.
- Tags must be from the allowed list, lowercase, comma-separated.
- `power-management` must be hyphenated; do not write `Power management`.

### Validation failed to publish

1. Download the validation artifact from the failing workflow run:

```bash
gh run view <run-id> --repo omacom/omarchy-plugin-marketplace
```

2. Download the `validation-reports-*` artifact and read `validation-report.md`.
3. Fix the reported issue in the repository or issue body.
4. Edit the issue to trigger re-validation.

## Approval and security baseline

- Automated validation must pass.
- The Automated Security Baseline posts `passed`, `review-required`, or `needs-fixes`.
- A maintainer must apply `approved-and-verified` before the listing is published.
- Marketplace approval is listing approval, not a security review.
