# Instructions for coding agents

Read `README.md` in full before writing code. It holds the plan, the data contract and the rules.

- Work on your lane's branch (`lane-a/...`, `lane-b/...`, and so on) and open pull requests into `main`. Don't push to `main` directly.
- Edit only your lane's folders. To change a table schema, path or JSON shape, edit the README's data contract in the same pull request and tell the other lanes.
- All code is written fresh in this repo during the event. Don't copy code from other projects.
- Never commit raw data, DIDs or handles of private users, or `.env`. Hash account IDs with `src/model/schema.py`.
- Read-only API access. Never post, like or follow on any platform.
- Respect rate limits: back off on 429 and 422, and save pulls page by page.
- Each script runs from the command line (`python -m src.<stage>.<script> --help`) and writes the Parquet tables named in the README.
- Put evaluation numbers in `eval/<area>/report.md` with the command that produced them.
