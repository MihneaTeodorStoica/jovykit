# Automation

The repository uses GitHub Actions for:

- Python linting, formatting, type-checking, tests when present, and dependency auditing.
- A grouped security workflow with CodeQL, Codacy SARIF upload, Trivy filesystem scanning, and dependency review.
- Docker image builds and GHCR publishing for each image variation.
- mdBook documentation build and GitHub Pages deployment.
- A grouped community automation workflow for stale cleanup, pull request labeling, first interaction greetings, and AI summaries for new issues.
