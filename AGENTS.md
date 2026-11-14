# Instructions for coding agents

Read `README.md` (question, data, rules, table schemas), `docs/DEMO.md` (demo, architecture, module interfaces, work split) and `docs/COMMS.md` (messages between agents) in full before writing code. Hermes owns the H milestones and Muse the M milestones in `docs/DEMO.md`.

- `docs/DEMO.md` is the single master file for the demo. Add to it; never create a second demo or plan document. Follow its "How to edit this file" section: update your work package's Status and Notes lines as you go, append to its changelog, and use `[demo]` or `[contract]` pull requests for anything that changes the demo or an interface.
- Work on a branch named for your milestone (`muse/m2-bot-model`, `hermes/h4-api`) and open pull requests into `main`. Don't push to `main` directly; the one exception is `docs/COMMS.md`, which goes straight to `main` in its own commit.
- Post in `docs/COMMS.md` when you start a session, land a milestone, need something, or want to change an interface.
- Edit only the folders your milestones own. Build against the contracts in `docs/DEMO.md` and stubs of other components; don't wait for them.
- All code is written fresh in this repo during the event. Don't copy code from other projects.
- Never commit raw data, DIDs or handles of private users, or `.env`. Hash account IDs with `src/model/schema.py`.
- Read-only API access. Never post, like or follow on any platform.
- Respect rate limits: back off on 429 and 422, and save pulls page by page.
- Each script runs from the command line (`python -m src.<stage>.<script> --help`) and writes the tables or artifacts named in the README and `docs/DEMO.md`.
- Put evaluation numbers in `eval/<area>/report.md` with the command that produced them.
