![concord-mcp — looked up, never made up.](docs/banner.svg)

Maybe this has happened to you: you asked ChatGPT or another AI assistant for a
Bible verse, and it gave you one — confident, beautiful, and not actually in the
Bible. These assistants answer from memory, and their memory of Scripture is
imperfect. concord-mcp fixes that one thing: **every verse your assistant shows
you is fetched from a real Bible on your own computer**, with a reference like
*John 3:16 (KJV)* you can check for yourself.

**Are you a developer?** Everything technical is in
[docs/DEVELOPERS.md](docs/DEVELOPERS.md).


## What this actually is, in plain words

Three pieces work together:

- **Claude** is the AI assistant — the one you talk to. It's made by a company
  called Anthropic, and you use it through a free app called Claude Desktop.
- **Concord** is a real Bible that lives on your computer — several complete
  translations, plus maps, study references, and the original Greek and Hebrew,
  all stored locally.
- **concord-mcp** (this project) is the connector. It hands the assistant one
  rule: *look it up, don't recall it.*

Think of a librarian with a card catalog. A good librarian doesn't quote books
from memory — she walks to the shelf, opens the book, and reads you the line,
spine in hand. concord-mcp gives your assistant the catalog and the shelf.

Once connected, the assistant can:

- find any verse by its reference ("What does John 3:16 say?")
- find a verse by its exact wording ("the one about still waters")
- search by idea — "verses about anxiety" — even when the word never appears
- look up what the Bible says about a subject, using a century-old study index
  compiled by hand
- show the passages generations of readers have connected to a verse
- show the Greek or Hebrew behind a verse, word by word
- explain what an original-language word actually means
- tell you where a place was — and honestly say "location unknown" when no one
  knows
- walk the great journeys, like Paul's travels, stop by stop with sources
- hand you a verse at random, for a verse of the day

No menus, no commands — you just ask in plain English, and the assistant
chooses how to look it up.

## Why you might want this

- **Quotes you can check.** Every verse arrives with its reference. Open your
  own Bible to the same place — it will be there.
- **Search by meaning.** "Verses about anxiety" finds Matthew 6 even though the
  word "anxiety" isn't in it.
- **Word-study depth without seminary software.** Ask why John 21 uses two
  different Greek words for "love" and watch the answer come from the actual
  Greek text.
- **Honest unknowns.** Ask where the land of Nod was, and you'll be told the
  truth: no one knows. No invented map pins.
- **The Bible stays home.** The Scripture data sits on your machine, not on
  someone's server.

## Honest downsides

Worth knowing before you spend an evening on setup:

- **Your conversation travels.** The Bible lives on your computer, but Claude
  is an internet service — your *questions and its answers* go to the company
  that runs it, like any chat service. (Fully private setups exist, but they're
  technical — see [docs/DEVELOPERS.md](docs/DEVELOPERS.md).)
- **The guarantee covers the quotes, not the commentary.** When the assistant
  quotes a verse, that quote came off the shelf. But its *explanations* are
  still an AI talking — thoughtful-sounding, sometimes wrong. Treat it as a
  study aid, not a pastor. That's exactly why every quote carries a reference:
  so you can open the passage yourself.
- **Setup takes real effort.** This is the most involved project in the Concord
  family: three free programs and one settings file, and the first time
  through expect 30–45 minutes. The steps below assume nothing.
- **The translations are older ones.** Concord ships public-domain Bibles —
  the King James and its relatives. Faithful, beloved, and in older English;
  modern copyrighted translations (NIV, ESV) are not included.

## What you'll need

- A computer (Windows or Mac) with about 2 GB of free disk space
- An internet connection for the setup and for talking to Claude
- A free [Claude](https://claude.ai) account
- 30–45 minutes, once

## Get it running

**1. Install Docker Desktop.**
Docker is a free tool that runs a program and everything it needs in a tidy,
self-contained bundle — Concord arrives as one of those bundles. Download it
from [docker.com](https://www.docker.com/products/docker-desktop/), install,
and open it once so it's running (look for the whale icon).

**2. Get Concord running.**
Concord is the Bible itself. *(Already using songbird? You already have
Concord running — skip ahead to step 3.)*
Follow the two-step quickstart in
[Concord's README](https://github.com/kbennett2000/concord#readme): download
it, then start it with one command. When it's up, the Bible is being served on
your computer.

**3. Install uv.**
uv is a small free helper that downloads and runs this project for you.

<details>
<summary>On a Mac</summary>

Open the Terminal app, paste this line, and press Enter:

```
curl -LsSf https://astral.sh/uv/install.sh | sh
```
</details>

<details>
<summary>On Windows</summary>

Open PowerShell (search "PowerShell" in the Start menu), paste this line, and
press Enter:

```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
</details>

**4. Download this project.**
Click the green **`Code`** button near the top of this page, then
**Download ZIP**. Unzip it somewhere you'll be able to find again — your
Documents folder is fine. Remember where: you'll type that location in step 6.

**5. Install Claude Desktop.**
Download it from [claude.ai/download](https://claude.ai/download), install,
and sign in with your free account.

**6. Tell Claude Desktop about the connector.**
This is the one fiddly step — a small settings file. In Claude Desktop, open
**Settings → Developer → Edit Config**. That opens a file called
`claude_desktop_config.json`.

<details>
<summary>Where is that file, exactly?</summary>

- **Mac:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

The Settings → Developer → Edit Config button takes you straight to it either
way.
</details>

Replace the file's contents with exactly this — changing only the one marked
line to the folder where you unzipped this project in step 4:

```json
{
  "mcpServers": {
    "concord": {
      "command": "uv",
      "args": ["--directory", "REPLACE-THIS/concord-mcp", "run", "concord-mcp"]
    }
  }
}
```

<details>
<summary>What do I put instead of REPLACE-THIS?</summary>

The full location of the unzipped folder. For example:

- Mac: `/Users/yourname/Documents/concord-mcp`
- Windows: `C:\\Users\\yourname\\Documents\\concord-mcp` (in this file,
  Windows paths need doubled backslashes, exactly like that)
</details>

Save the file and **restart Claude Desktop** (fully quit it, then open it
again).

**7. The first win.**
Look for the small tools icon (a plug or sliders, near the message box) — that
means Claude can see the connector. Now ask:

> *What does Psalm 23 say?*

If the answer comes back verse by verse, each line tagged like
**Psalms 23:1 (KJV)** — it's working. Every one of those verses just came off
the shelf on your own computer.

## Trouble?

<details>
<summary>Claude says "Concord isn't reachable…"</summary>

Concord (the Bible) isn't running. Open Docker Desktop, make sure it's started
(the whale icon), and start Concord again per step 2. Then ask your question
again — no restart of Claude needed.
</details>

<details>
<summary>No tools icon after restarting Claude Desktop</summary>

Almost always the path in the settings file. Open Settings → Developer → Edit
Config again and check the `REPLACE-THIS` line: it must be the real location
of the unzipped folder, and on Windows every backslash must be doubled
(`C:\\Users\\...`). Save and fully restart Claude Desktop again.
</details>

<details>
<summary>"docker: command not found" or nothing happens in step 2</summary>

Docker Desktop isn't running. Open it (look for the whale icon) and try again.
If it was never installed, that's step 1.
</details>

Still stuck? [Open an Issue](https://github.com/kbennett2000/concord-mcp/issues)
and describe where you got to — we'll help.

## Part of the Concord family

[Concord](https://github.com/kbennett2000/concord) is the Bible on your
computer. [songbird](https://github.com/kbennett2000/songbird) is a quiet
place to read it and keep notes. concord-mcp connects it to an AI assistant —
looked up, never made up.

MIT licensed. Built with care, for one real reader.
