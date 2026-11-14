# Instructions for coding agents

Read `README.md` (question, data, rules, table schemas) and `docs/DEMO.md` (demo, architecture, API contracts, work packages) in full before writing code. You will be told which work package (WP-n) is yours.

- `docs/DEMO.md` is the single master file for the demo. Add to it; never create a second demo or plan document. Follow its "How to edit this file" section: update your work package's Status and Notes lines as you go, append to its changelog, and use `[demo]` or `[contract]` pull requests for anything that changes the demo or an interface.
- Work on a branch named for your work package (`wp-3/bot-model`, `wp-8/photon`) and open pull requests into `main`. Don't push to `main` directly.
- Edit only the folders your work package owns. Build against the contracts in `docs/DEMO.md` and stubs of other components; don't wait for them.
- All code is written fresh in this repo during the event. Don't copy code from other projects.
- Never commit raw data, DIDs or handles of private users, or `.env`. Hash account IDs with `src/model/schema.py`.
- Read-only API access. Never post, like or follow on any platform.
- Respect rate limits: back off on 429 and 422, and save pulls page by page.
- Each script runs from the command line (`python -m src.<stage>.<script> --help`) and writes the tables or artifacts named in the README and `docs/DEMO.md`.
- Put evaluation numbers in `eval/<area>/report.md` with the command that produced them.
